import json
import io
import contextlib
import types
import sys

from unittest.mock import patch

import pytest
import docker


_initial_client = types.SimpleNamespace(containers=None, images=None)
with patch('docker.from_env', return_value=_initial_client):
    import app


class FakeExecResult:
    def __init__(self, exit_code=0, output=b''):
        self.exit_code = exit_code
        self.output = output


class FakeContainer:
    def __init__(self, storage_root):
        self.storage_root = storage_root
        self.script_content = None
        self.started = False
        self.stopped = False

    def start(self):
        self.started = True

    def stop(self):
        self.stopped = True

    def remove(self, force=False):
        pass

    def exec_run(self, cmd):
        # Normalize command to easily match patterns
        if isinstance(cmd, (list, tuple)):
            command = cmd
        else:
            command = [cmd]

        if command[0] == 'sh' and '-c' in command:
            shell_cmd = command[-1]
            if 'apk add' in shell_cmd:
                return FakeExecResult(0, b'')
            if 'pip3 install' in shell_cmd:
                return FakeExecResult(0, b'')
            if 'cat > /tmp/create_user.py' in shell_cmd:
                script = shell_cmd.split("<< 'EOF'\n", 1)[1].rsplit("\nEOF", 1)[0]
                self.script_content = script
                return FakeExecResult(0, b'')

        if command[0] == 'python3' and command[-1] == '/tmp/create_user.py':
            assert self.script_content, 'Script content should be set before execution'
            script_to_run = self.script_content.replace("'/config", f"'{self.storage_root}")
            script_to_run = script_to_run.replace('"/config', f'"{self.storage_root}')
            if 'bcrypt' not in sys.modules:
                def _gensalt(rounds=12):
                    return f'$2b${rounds:02}$stubhashstubhashstubhashstu'.encode('utf-8')

                def _hashpw(password, salt):
                    if isinstance(password, str):
                        password = password.encode('utf-8')
                    if isinstance(salt, str):
                        salt = salt.encode('utf-8')
                    return salt + password

                sys.modules['bcrypt'] = types.SimpleNamespace(
                    gensalt=_gensalt,
                    hashpw=_hashpw
                )
            buffer = io.StringIO()
            with contextlib.redirect_stdout(buffer):
                exec(compile(script_to_run, '<create_user>', 'exec'), {})
            output = buffer.getvalue().encode('utf-8')
            return FakeExecResult(0, output)

        return FakeExecResult(0, b'')


class FakeContainers:
    def __init__(self, container):
        self.container = container

    def create(self, *args, **kwargs):
        return self.container


class FakeImages:
    def get(self, name):
        return object()


class FakeDockerClient:
    def __init__(self, container):
        self.containers = FakeContainers(container)
        self.images = FakeImages()


@pytest.fixture
def sample_storage(tmp_path):
    storage_root = tmp_path / 'config'
    storage_root.mkdir()
    storage_dir = storage_root / '.storage'
    storage_dir.mkdir()

    auth = {
        'data': {
            'users': [
                {
                    'id': 'existinguser',
                    'group_ids': ['system-admin'],
                    'is_owner': True,
                    'is_active': True,
                    'name': 'Student',
                    'system_generated': False,
                    'local_only': False,
                    'username': 'student',
                    'created_at': '2024-01-01T00:00:00Z'
                }
            ],
            'credentials': [
                {
                    'id': 'existingcred',
                    'user_id': 'existinguser',
                    'auth_provider_type': 'homeassistant',
                    'auth_provider_id': None,
                    'data': {'username': 'student'},
                    'is_active': True,
                    'created_at': '2024-01-01T00:00:00Z',
                    'last_used_at': '2024-01-02T00:00:00Z',
                    'last_used_version': '2024.1.0'
                }
            ]
        }
    }

    auth_provider = {
        'data': {
            'users': [
                {
                    'id': 'provideruser',
                    'user_id': 'existinguser',
                    'username': 'student',
                    'password': '$2b$12$existinghash',
                    'name': 'Student',
                    'is_active': True,
                    'system_generated': False,
                    'local_only': False,
                    'created_at': '2024-01-01T00:00:00Z',
                    'last_used_at': '2024-01-02T00:00:00Z',
                    'last_used_version': '2024.1.0'
                }
            ]
        }
    }

    person = {
        'data': {
            'items': [
                {
                    'id': 'person_existing',
                    'name': 'Student',
                    'user_id': 'existinguser',
                    'device_trackers': [],
                    'picture': None,
                    'type': 'user'
                }
            ]
        }
    }

    auth_file = storage_dir / 'auth'
    auth_provider_file = storage_dir / 'auth_provider.homeassistant'
    person_file = storage_dir / 'person'
    auth_file.write_text(json.dumps(auth))
    auth_provider_file.write_text(json.dumps(auth_provider))
    person_file.write_text(json.dumps(person))

    return types.SimpleNamespace(
        root=str(storage_root),
        auth_path=auth_file,
        provider_path=auth_provider_file,
        person_path=person_file,
    )


def test_teacher_account_contains_required_fields(monkeypatch, sample_storage):
    fake_container = FakeContainer(sample_storage.root)
    fake_client = FakeDockerClient(fake_container)

    original_client = app.client
    app.client = fake_client

    try:
        success, message = app.create_teacher_account('volume', 'admin', 'adminpass')
    finally:
        app.client = original_client

    assert success, message
    assert message == 'Teacher account created successfully'

    updated_auth = json.loads(sample_storage.auth_path.read_text())
    updated_provider = json.loads(sample_storage.provider_path.read_text())
    updated_person = json.loads(sample_storage.person_path.read_text())

    assert len(updated_auth['data']['users']) == 2
    new_user = updated_auth['data']['users'][-1]
    assert new_user['username'] == 'admin'
    assert 'system-admin' in new_user['group_ids']
    assert new_user['is_active'] is True
    assert new_user['id']

    new_credential = updated_auth['data']['credentials'][-1]
    assert new_credential['user_id'] == new_user['id']
    assert new_credential['is_active'] is True
    assert 'last_used_version' in new_credential

    assert len(updated_provider['data']['users']) == 2
    provider_entry = updated_provider['data']['users'][-1]
    assert provider_entry['user_id'] == new_user['id']
    assert provider_entry['id']
    assert provider_entry['is_active'] is True
    assert provider_entry['password'].startswith('$2')
    assert provider_entry.get('last_used_version') is None

    assert len(updated_person['data']['items']) == 2
    person_entry = next(
        item for item in updated_person['data']['items']
        if item['user_id'] == new_user['id']
    )
    assert person_entry['name'] == 'admin'
    assert person_entry['device_trackers'] == []
    assert person_entry.get('type') == 'user'


def test_teacher_account_creates_person_file_when_missing(monkeypatch, sample_storage):
    sample_storage.person_path.unlink()

    fake_container = FakeContainer(sample_storage.root)
    fake_client = FakeDockerClient(fake_container)

    original_client = app.client
    app.client = fake_client

    try:
        success, message = app.create_teacher_account('volume', 'admin', 'adminpass')
    finally:
        app.client = original_client

    assert success, message
    assert message == 'Teacher account created successfully'

    updated_person = json.loads(sample_storage.person_path.read_text())
    updated_auth = json.loads(sample_storage.auth_path.read_text())

    assert len(updated_person['data']['items']) == 1
    new_user = next(
        item for item in updated_auth['data']['users']
        if item['username'] == 'admin'
    )
    person_entry = updated_person['data']['items'][0]
    assert person_entry['user_id'] == new_user['id']
    assert person_entry['name'] == 'admin'
