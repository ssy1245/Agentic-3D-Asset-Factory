"""Only targets an explicitly offline Mock app. No automatic real-API fallback."""
import os
import time
import uuid

import gevent
import requests
from locust import HttpUser, between, events, task
from locust.exception import StopUser
from locust.runners import MasterRunner

COOKIE = "studio_session"


def verify_mock_status(status):
    if status.get("load_test") is not True or status.get("external_api_calls") is not False:
        raise RuntimeError("拒绝压测：目标没有明确启用无真实 API 的 Mock 模式。")


@events.test_start.add_listener
def prepare(environment, **kwargs):
    environment.mock_cookie = None
    if isinstance(environment.runner, MasterRunner):
        return
    try:
        if not environment.host:
            raise RuntimeError("必须明确设置 --host")
        base = environment.host.rstrip("/")
        with requests.Session() as session:
            status = session.get(base + "/load-test/status", timeout=10)
            status.raise_for_status()
            verify_mock_status(status.json())
            credentials = {"username": os.getenv("LOADTEST_USERNAME", "loadtester"),
                           "password": os.getenv("LOADTEST_PASSWORD", "load-test-password-123")}
            response = session.post(base + "/api/auth/register", json={
                **credentials, "registration_pass": "load-test-local-only",
            }, timeout=15)
            if response.status_code == 409:
                response = session.post(base + "/api/auth/login", json=credentials, timeout=15)
            response.raise_for_status()
            config = session.get(base + "/api/config", timeout=10)
            config.raise_for_status()
            verify_mock_status(config.json())
            if config.json().get("providers") != ["mock"]:
                raise RuntimeError("目标出图服务不是仅 Mock")
            environment.mock_cookie = session.cookies.get(COOKIE)
            if not environment.mock_cookie:
                raise RuntimeError("没有取得测试会话")
    except Exception as error:
        environment.runner.quit()
        raise RuntimeError("压测启动检查失败；没有发起业务负载。") from error


class StudioUser(HttpUser):
    wait_time = between(1, 3)

    def on_start(self):
        if not getattr(self.environment, "mock_cookie", None):
            raise StopUser()
        self.client.cookies.set(COOKIE, self.environment.mock_cookie)
        with self.client.post('/api/projects', data={
            'name': 'loadtest-' + uuid.uuid4().hex[:8], 'provider': 'mock',
        }, name='create project', catch_response=True) as response:
            if response.status_code != 200:
                response.failure('创建测试项目失败')
                raise StopUser()
            self.pid = response.json()['id']

    @task(3)
    def read_project(self):
        self.client.get(f'/api/projects/{self.pid}', name='read project')

    @task(1)
    def mock_generation(self):
        started = time.perf_counter()
        error = None
        try:
            with self.client.post(f'/api/projects/{self.pid}/generate', json={
                'stage': 'design', 'request_id': uuid.uuid4().hex,
            }, name='submit mock image', catch_response=True) as response:
                if response.status_code != 202:
                    response.failure('任务提交失败')
                    raise RuntimeError('任务提交失败')
                oid = response.json()['id']
            deadline = time.monotonic() + 90
            while time.monotonic() < deadline:
                response = self.client.get(f'/api/projects/{self.pid}', name='poll project')
                if response.status_code != 200:
                    raise RuntimeError('任务查询失败')
                operation = next((op for op in response.json()['operations'] if op['id'] == oid), None)
                if operation and operation['status'] == 'succeeded':
                    return
                if operation and operation['status'] in ('failed', 'unknown'):
                    raise RuntimeError('Mock 任务失败')
                gevent.sleep(0.25)
            raise RuntimeError('Mock 任务完成超时')
        except (requests.RequestException, RuntimeError, ValueError, KeyError) as failure:
            error = failure
        finally:
            # Report task completion separately from the fast HTTP 202 response.
            self.environment.events.request.fire(
                request_type='TASK', name='mock image completion',
                response_time=(time.perf_counter() - started) * 1000,
                response_length=0, exception=error,
            )
