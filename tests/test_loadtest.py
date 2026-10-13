import asyncio
import runpy
import sys
import time
import types
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient
from test_studio import approve, finished, submit

from asset_factory.mock_providers import MockImageProvider, MockSettings
from asset_factory.provider import OpenAIProvider, ProviderError
from asset_factory.review import VisualReviewer
from asset_factory.studio import create_app
from asset_factory.tripo import TripoProvider
from asset_factory.views import split_views


@pytest.fixture
def offline(monkeypatch):
    monkeypatch.setenv("STUDIO_LOAD_TEST", "1")
    monkeypatch.setenv("STUDIO_MOCK_DELAY_MS", "0")
    monkeypatch.setenv("STUDIO_MOCK_FAILURE_RATE", "0")
    monkeypatch.setenv("OPENAI_API_KEY", "not-a-real-key")
    monkeypatch.setenv("TRIPO_API_KEY", "not-a-real-key")

    async def forbidden(*args, **kwargs):
        pytest.fail("Mock mode attempted external HTTP")

    monkeypatch.setattr(httpx.AsyncClient, "send", forbidden)


def login(client):
    response = client.post('/api/auth/register', json={
        'username': 'loaduser', 'password': 'load-test-password-123',
        'registration_pass': 'test-registration-pass',
    })
    assert response.status_code == 201, response.text


def test_mock_full_workflow_never_calls_network_or_blender(tmp_path, monkeypatch, offline):
    def forbidden(*args, **kwargs):
        pytest.fail("Mock mode constructed a real provider")

    for name in ['OpenAIProvider', 'VisualReviewer', 'TripoProvider']:
        monkeypatch.setattr('asset_factory.studio.' + name, forbidden)
    with TestClient(create_app(tmp_path)) as client:
        assert client.get('/load-test/status').json() == {'load_test': True, 'external_api_calls': False}
        login(client)
        config = client.get('/api/config').json()
        assert config['providers'] == ['mock'] and config['default_provider'] == 'mock'
        assert config['external_api_calls'] is False
        assert client.post('/api/projects', data={'name': 'bad', 'provider': 'openai'}).status_code == 400
        pid = client.post('/api/projects', data={'name': 'mock-only', 'provider': 'mock'}).json()['id']
        for stage in ['design', 'turnaround', 'head', 'body', 'hair']:
            assert submit(client, pid, stage).status_code == 202
            approve(client, pid, stage)
        project = finished(client, pid)
        geometry = [op for op in project['operations'] if op.get('kind') == 'geometry']
        assert len(geometry) == 3
        for op in geometry:
            assert op['status'] == 'succeeded', op
            assert op['quad'] is True
            assert op['face_limit'] == (5000 if op['stage'] == 'head' else 20000)
            base = f"/api/projects/{pid}/geometry/{op['id']}"
            assert client.get(base + '/download').content.startswith(b'; FBX')
            assert client.get(base + '/preview').content.startswith(b'glTF')
            assert client.get(base + '/info').json()['quad_faces'] == 6
            assert client.get(base + '/blend').status_code == 503
        parent = next(op for op in geometry if op['stage'] == 'head')
        original = client.get(f"/api/projects/{pid}/geometry/{parent['id']}/download").content
        response = client.post(f"/api/projects/{pid}/geometry/{parent['id']}/texture", json={'checked': True})
        assert response.status_code == 202, response.text
        textured = finished(client, pid)
        child = next(op for op in textured['operations'] if op.get('parent_model_id') == parent['id'])
        assert child['status'] == 'succeeded' and child['texture'] is True
        assert child['consumed_credit'] == 0
        assert client.get(f"/api/projects/{pid}/geometry/{parent['id']}/download").content == original
        assert client.get('/api/services/tripo/balance').json()['mock'] is True
        head = next(r for r in project['revisions'] if r['id'] == project['current']['head'])
        deadline = time.monotonic() + 3
        while head.get('quality_review', {}).get('status') != 'completed' and time.monotonic() < deadline:
            project = client.get(f'/api/projects/{pid}').json()
            head = next(r for r in project['revisions'] if r['id'] == project['current']['head'])
        assert head['quality_review']['mock'] is True


def test_mock_overrides_injected_providers_and_uses_separate_data(tmp_path, monkeypatch, offline):
    monkeypatch.setattr('asset_factory.studio.ROOT', tmp_path)
    app = create_app(providers={'openai': object()}, reviewer=object(), tripo=object())
    assert list(app.state.providers) == ['mock']
    assert app.state.store.root == tmp_path / 'load-test-data'
    assert not (tmp_path / 'data').exists()


def test_real_provider_entrypoints_are_blocked_before_http(tmp_path, offline):
    calls = [
        OpenAIProvider('unused', 'unused').generate('design', '', []),
        VisualReviewer('unused').review('head', b'', b''),
        TripoProvider('unused').request('POST', '/task'),
        TripoProvider('unused').download({'model': 'https://example.com/model.fbx'}, tmp_path / 'x.fbx'),
    ]
    for call in calls:
        with pytest.raises(RuntimeError, match='禁止真实'):
            asyncio.run(call)


def test_invalid_mode_fails_closed(tmp_path, monkeypatch):
    monkeypatch.setenv('STUDIO_LOAD_TEST', 'true')
    with pytest.raises(ValueError, match='exactly 0 or 1'):
        create_app(tmp_path)


def test_mock_images_split_and_failures_are_explicit(monkeypatch, offline):
    provider = MockImageProvider(MockSettings())
    result = asyncio.run(provider.generate('turnaround', '', []))
    assert len(split_views(result.image)) == 4
    assert result.usage['cost'] == 0
    monkeypatch.setenv('STUDIO_MOCK_FAILURE_RATE', '1')
    with pytest.raises(ProviderError, match='Mock'):
        asyncio.run(MockImageProvider(MockSettings()).generate('design', '', []))


@pytest.mark.parametrize('name,value', [('STUDIO_MOCK_DELAY_MS', '-1'),
                                        ('STUDIO_MOCK_DELAY_MS', 'nan'),
                                        ('STUDIO_MOCK_FAILURE_RATE', '1.1')])
def test_invalid_mock_settings_rejected(name, value, monkeypatch, offline):
    monkeypatch.setenv(name, value)
    with pytest.raises(ValueError):
        MockSettings()


@pytest.mark.parametrize('status', [{}, {'load_test': False, 'external_api_calls': False},
                                   {'load_test': True, 'external_api_calls': True},
                                   {'load_test': '1', 'external_api_calls': False}])
def test_locust_refuses_non_mock_before_login_or_business_requests(monkeypatch, status):
    class Event:
        def add_listener(self, function):
            return function

    locust = types.ModuleType('locust')
    locust.HttpUser = type('HttpUser', (), {})
    locust.between = lambda *args: None
    locust.task = lambda *args: (lambda function: function)
    locust.events = types.SimpleNamespace(test_start=Event())
    exception = types.ModuleType('locust.exception')
    exception.StopUser = type('StopUser', (Exception,), {})
    runners = types.ModuleType('locust.runners')
    runners.MasterRunner = type('MasterRunner', (), {})
    gevent = types.ModuleType('gevent')
    gevent.sleep = lambda *args: None
    for name, module in [('locust', locust), ('locust.exception', exception),
                         ('locust.runners', runners), ('gevent', gevent)]:
        monkeypatch.setitem(sys.modules, name, module)
    calls = []

    class Session:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def get(self, url, **kwargs):
            calls.append(url)
            return types.SimpleNamespace(raise_for_status=lambda: None, json=lambda: status)

        def post(self, *args, **kwargs):
            pytest.fail('Locust attempted login or registration against a non-Mock target')

    monkeypatch.setattr('requests.Session', Session)
    script = Path(__file__).resolve().parents[1] / 'loadtests' / 'locustfile.py'
    namespace = runpy.run_path(str(script))
    stopped = []
    env = types.SimpleNamespace(host='http://example.invalid',
                                runner=types.SimpleNamespace(quit=lambda: stopped.append(True)))
    with pytest.raises(RuntimeError, match='没有发起业务负载'):
        namespace['prepare'](env)
    assert stopped == [True]
    assert calls == ['http://example.invalid/load-test/status']
    assert env.mock_cookie is None
