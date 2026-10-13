import json
import sqlite3
import time

import pytest
from fastapi.testclient import TestClient
from test_studio import FakeProvider, finished, png, submit

from asset_factory.auth import COOKIE, assign_legacy, token_hash
from asset_factory.storage import Store
from asset_factory.studio import create_app

PASSWORD = "correct-password-123"


def register(client, username):
    response = client.post('/api/auth/register', json={'username': username, 'password': PASSWORD, 'registration_pass': 'test-registration-pass'})
    assert response.status_code == 201, response.text
    return response.json()


def test_sessions_passwords_and_logout(tmp_path):
    app = create_app(tmp_path, {'demo': FakeProvider()})
    with TestClient(app) as client:
        assert client.get('/api/projects').status_code == 401
        assert client.get('/').status_code == 200
        user = register(client, 'Alice')
        assert user['username'] == 'alice'
        assert client.get('/api/auth/me').json() == user
        token = client.cookies.get(COOKIE)
        assert any(key.lower() == 'httponly' for key in client.cookies.jar._cookies['testserver.local']['/'][COOKIE]._rest)
        with app.state.store.connect() as db:
            row = db.execute('SELECT * FROM users').fetchone()
            assert PASSWORD not in row['password_hash']
            assert row['password_hash'].startswith('scrypt$')
            assert db.execute('SELECT token_hash FROM sessions').fetchone()[0] == token_hash(token)
        assert client.post('/api/auth/logout').status_code == 204
        assert client.get('/api/auth/me').status_code == 401
        client.cookies.set(COOKIE, token)
        assert client.get('/api/projects').status_code == 401
        client.cookies.clear()
        assert client.post('/api/auth/login', json={'username': 'alice', 'password': 'wrong-password'}).status_code == 401
        assert client.post('/api/auth/register', json={'username': 'ALICE', 'password': PASSWORD, 'registration_pass': 'test-registration-pass'}).status_code == 409
        assert client.post('/api/auth/login', json={'username': 'ALICE', 'password': PASSWORD, 'registration_pass': 'test-registration-pass'}).status_code == 200
        with app.state.store.connect() as db:
            db.execute('UPDATE sessions SET expires_at=?', (int(time.time()) - 1,))
        assert client.get('/api/projects').status_code == 401


def test_project_and_asset_isolation_and_generation(tmp_path):
    app = create_app(tmp_path, {'demo': FakeProvider()})
    with TestClient(app) as alice:
        owner = register(alice, 'alice')
        pid = alice.post('/api/projects', data={'name': 'private', 'provider': 'demo'}).json()['id']
        assert alice.get(f'/api/projects/{pid}').json()['owner_id'] == owner['id']
        assert submit(alice, pid).status_code == 202
        project = finished(alice, pid)
        rid = project['current']['design']
        oid = project['operations'][0]['id']
        assert alice.get(project['revisions'][0]['image_url']).status_code == 200
        with TestClient(app, client=('second-user', 50001)) as bob:
            register(bob, 'bob')
            assert bob.get('/api/projects').json() == []
            paths = [
                f'/api/projects/{pid}', f'/api/projects/{pid}/images/{rid}',
                f'/api/projects/{pid}/export', f'/api/projects/{pid}/geometry/{oid}/preview',
                f'/api/projects/{pid}/project-package',
            ]
            for path in paths:
                assert bob.get(path).status_code == 404
                assert bob.get(path + '/').status_code == 404
            assert submit(bob, pid).status_code == 404
            assert bob.post(f'/api/projects/{pid}/approve/{rid}').status_code == 404
            assert bob.post(f'/api/projects/{pid}/upload', data={'stage': 'design'},
                            files={'image': ('test.png', png(), 'image/png')}).status_code == 404
        assert alice.get(f'/api/projects/{pid}').status_code == 200


def test_legacy_migration_and_explicit_assignment(tmp_path):
    legacy = {'id': 'old-project', 'name': 'old', 'provider': 'demo', 'created_at': 'old',
              'brief': '', 'current': {}, 'revisions': []}
    db = sqlite3.connect(tmp_path / 'studio.sqlite3')
    db.execute('CREATE TABLE projects (id TEXT PRIMARY KEY, data TEXT NOT NULL)')
    db.execute('INSERT INTO projects VALUES (?,?)', (legacy['id'], json.dumps(legacy)))
    db.commit()
    db.close()
    app = create_app(tmp_path, {'demo': FakeProvider()})
    with TestClient(app) as client:
        user = register(client, 'owner')
        assert client.get('/api/projects').json() == []
        assert client.get('/api/projects/old-project').status_code == 404
        assert assign_legacy(app.state.store, 'owner', 'old-project') == 1
        assert assign_legacy(app.state.store, 'owner', 'old-project') == 0
        assert client.get('/api/projects/old-project').json()['owner_id'] == user['id']
        assert len(client.get('/api/projects').json()) == 1
    # Reopening the migrated database preserves ownership and content.
    store = Store(tmp_path)
    assert store.get('old-project')['name'] == 'old'
    assert store.owns('old-project', user['id'])


def test_csrf_validation_and_rate_limit(tmp_path):
    app = create_app(tmp_path, {'demo': FakeProvider()})
    with TestClient(app) as client:
        credentials = {'username': 'alice', 'password': PASSWORD, 'registration_pass': 'test-registration-pass'}
        assert client.post('/api/auth/register', json=credentials,
                           headers={'Origin': 'https://evil.example'}).status_code == 403
        assert client.post('/api/auth/register', json=credentials,
                           headers={'Sec-Fetch-Site': 'cross-site'}).status_code == 403
        assert client.post('/api/auth/register', json={'username': 'alice', 'password': 'short'}).status_code == 422
        register(client, 'alice')
        assert client.post('/api/projects', data={'name': 'test'},
                           headers={'Origin': 'https://evil.example'}).status_code == 403
        assert client.post('/api/projects', data={'name': 'test'},
                           headers={'Origin': 'http://testserver'}).status_code == 200
        for _ in range(9):
            assert client.post('/api/auth/login', json={'username': 'missing', 'password': PASSWORD, 'registration_pass': 'test-registration-pass'}).status_code == 401
        assert client.post('/api/auth/login', json=credentials).status_code == 429


def test_session_survives_restart_and_rejects_forged_token(tmp_path):
    with TestClient(create_app(tmp_path, {'demo': FakeProvider()})) as client:
        user = register(client, 'persistent')
        token = client.cookies.get(COOKIE)
    with TestClient(create_app(tmp_path, {'demo': FakeProvider()})) as client:
        client.cookies.set(COOKIE, token)
        assert client.get('/api/auth/me').json() == user
        client.cookies.clear()
        client.cookies.set(COOKIE, 'forged-token')
        assert client.get('/api/auth/me').status_code == 401


def test_https_cookie_and_server_selected_owner(tmp_path, monkeypatch):
    monkeypatch.setenv('STUDIO_COOKIE_SECURE', '1')
    app = create_app(tmp_path, {'demo': FakeProvider()})
    with TestClient(app, base_url='https://testserver') as client:
        response = client.post('/api/auth/register', json={'username': 'secure', 'password': PASSWORD, 'registration_pass': 'test-registration-pass'})
        assert response.status_code == 201
        cookie = response.headers['set-cookie'].lower()
        assert 'secure' in cookie and 'httponly' in cookie and 'samesite=strict' in cookie
        created = client.post('/api/projects', data={'name': 'test', 'owner_id': 'attacker'}).json()
        assert created['owner_id'] == response.json()['id']


@pytest.mark.parametrize('registration_pass', [None, '', 'invalid-pass', 'TEST-REGISTRATION-PASS'])
def test_registration_requires_backend_pass(tmp_path, monkeypatch, registration_pass):
    app = create_app(tmp_path, {'demo': FakeProvider()})
    # Invalid passes must be rejected before expensive password hashing or writes.
    monkeypatch.setattr('asset_factory.auth.password_hash', lambda *args: pytest.fail('password hashed'))
    with TestClient(app) as client:
        payload = {'username': 'blocked', 'password': PASSWORD}
        if registration_pass is not None:
            payload['registration_pass'] = registration_pass
        response = client.post('/api/auth/register', json=payload)
        assert response.status_code == 403
        assert COOKIE not in response.cookies
        with app.state.store.connect() as db:
            assert db.execute('SELECT count(*) FROM users').fetchone()[0] == 0
            assert db.execute('SELECT count(*) FROM sessions').fetchone()[0] == 0


def test_registration_passes_are_reusable_and_backend_only(tmp_path):
    app = create_app(tmp_path, {'demo': FakeProvider()})
    with TestClient(app) as client:
        for username, code in [('alice', 'test-registration-pass'),
                               ('bob', 'test-registration-pass'),
                               ('carol', '  second-test-pass  ')]:
            response = client.post('/api/auth/register', json={
                'username': username, 'password': PASSWORD, 'registration_pass': code,
            })
            assert response.status_code == 201
            assert set(response.json()) == {'id', 'username'}
        for path in ['/', '/static/auth.js']:
            content = client.get(path).text
            assert 'test-registration-pass' not in content
            assert 'second-test-pass' not in content


@pytest.mark.parametrize('configured_passes', ['', ' , , ', 'replacement-pass'])
def test_closed_or_rotated_passes_preserve_login(tmp_path, monkeypatch, configured_passes):
    with TestClient(create_app(tmp_path, {'demo': FakeProvider()})) as client:
        register(client, 'existing')
    monkeypatch.setenv('STUDIO_REGISTRATION_PASSES', configured_passes)
    app = create_app(tmp_path, {'demo': FakeProvider()})
    with TestClient(app) as client:
        assert client.post('/api/auth/register', json={
            'username': 'newuser', 'password': PASSWORD,
            'registration_pass': 'test-registration-pass',
        }).status_code == 403
        assert client.post('/api/auth/login', json={
            'username': 'existing', 'password': PASSWORD,
        }).status_code == 200
        if configured_passes == 'replacement-pass':
            assert client.post('/api/auth/register', json={
                'username': 'newuser', 'password': PASSWORD,
                'registration_pass': configured_passes,
            }).status_code == 201
