import json
import io
import contextlib
import types
import sys
import base64

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
            exit_code = 0
            try:
                with contextlib.redirect_stdout(buffer):
                    exec(compile(script_to_run, '<create_user>', 'exec'), {})
            except SystemExit as e:
                # Script calls exit(0), which is normal
                exit_code = e.code if e.code is not None else 0
            output = buffer.getvalue().encode('utf-8')
            return FakeExecResult(exit_code, output)

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
def sample_storage_with_teacher(tmp_path):
    """Storage with both student and teacher accounts already created"""
    storage_root = tmp_path / 'config'
    storage_root.mkdir()
    storage_dir = storage_root / '.storage'
    storage_dir.mkdir()

    # Create initial password hash for teacher
    old_password_hash = base64.b64encode(b'$2b$12$oldpasswordhash').decode('utf-8')

    auth = {
        'data': {
            'users': [
                {
                    'id': 'student_user_id',
                    'group_ids': ['system-admin'],
                    'is_owner': True,
                    'is_active': True,
                    'name': 'Student',
                    'system_generated': False,
                    'local_only': False,
                    'username': 'student',
                    'created_at': '2024-01-01T00:00:00Z'
                },
                {
                    'id': 'teacher_user_id',
                    'group_ids': ['system-admin'],
                    'is_owner': False,
                    'is_active': True,
                    'name': 'admin',
                    'system_generated': False,
                    'local_only': False,
                    'username': 'admin',
                    'created_at': '2024-01-02T00:00:00Z'
                }
            ],
            'credentials': [
                {
                    'id': 'student_cred_id',
                    'user_id': 'student_user_id',
                    'auth_provider_type': 'homeassistant',
                    'auth_provider_id': None,
                    'data': {'username': 'student'},
                    'is_active': True,
                    'created_at': '2024-01-01T00:00:00Z',
                    'last_used_at': '2024-01-02T00:00:00Z',
                    'last_used_version': '2024.1.0'
                },
                {
                    'id': 'teacher_cred_id',
                    'user_id': 'teacher_user_id',
                    'auth_provider_type': 'homeassistant',
                    'auth_provider_id': None,
                    'data': {'username': 'admin'},
                    'is_active': True,
                    'created_at': '2024-01-02T00:00:00Z',
                    'last_used_at': None,
                    'last_used_version': None
                }
            ]
        }
    }

    auth_provider = {
        'data': {
            'users': [
                {
                    'id': 'student_provider_id',
                    'user_id': 'student_user_id',
                    'username': 'student',
                    'password': '$2b$12$studenthash',
                    'name': 'Student',
                    'is_active': True,
                    'system_generated': False,
                    'local_only': False,
                    'created_at': '2024-01-01T00:00:00Z',
                    'last_used_at': '2024-01-02T00:00:00Z',
                    'last_used_version': '2024.1.0'
                },
                {
                    'id': 'teacher_provider_id',
                    'user_id': 'teacher_user_id',
                    'username': 'admin',
                    'password': old_password_hash,
                    'name': 'admin',
                    'is_active': True,
                    'system_generated': False,
                    'local_only': False,
                    'created_at': '2024-01-02T00:00:00Z',
                    'last_used_at': None,
                    'last_used_version': None
                }
            ]
        }
    }

    person = {
        'data': {
            'items': [
                {
                    'id': 'person_student',
                    'name': 'Student',
                    'user_id': 'student_user_id',
                    'device_trackers': [],
                    'picture': None,
                    'type': 'user'
                },
                {
                    'id': 'person_teacher',
                    'name': 'admin',
                    'user_id': 'teacher_user_id',
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
        old_password_hash=old_password_hash,
    )


def test_teacher_account_reset_updates_password(monkeypatch, sample_storage_with_teacher):
    """Test that calling create_teacher_account with reset_if_exists=True updates the password"""
    fake_container = FakeContainer(sample_storage_with_teacher.root)
    fake_client = FakeDockerClient(fake_container)

    original_client = app.client
    app.client = fake_client

    try:
        success, message = app.create_teacher_account('volume', 'admin', 'newpassword', reset_if_exists=True)
    finally:
        app.client = original_client

    assert success, message
    assert message == 'Teacher account password reset successfully'

    updated_provider = json.loads(sample_storage_with_teacher.provider_path.read_text())
    
    # Find the teacher's provider entry
    teacher_provider = next(
        u for u in updated_provider['data']['users']
        if u['username'] == 'admin'
    )
    
    # Password should have changed
    assert teacher_provider['password'] != sample_storage_with_teacher.old_password_hash
    
    # Should still be base64-encoded bcrypt hash
    decoded_password = base64.b64decode(teacher_provider['password'])
    assert decoded_password.startswith(b'$2')
    
    # Should still have 2 users (no duplicates)
    updated_auth = json.loads(sample_storage_with_teacher.auth_path.read_text())
    assert len(updated_auth['data']['users']) == 2


def test_teacher_account_without_reset_returns_exists(monkeypatch, sample_storage_with_teacher):
    """Test that calling create_teacher_account without reset_if_exists returns 'exists' error"""
    fake_container = FakeContainer(sample_storage_with_teacher.root)
    fake_client = FakeDockerClient(fake_container)

    original_client = app.client
    app.client = fake_client

    try:
        success, message = app.create_teacher_account('volume', 'admin', 'newpassword', reset_if_exists=False)
    finally:
        app.client = original_client

    assert not success
    assert message == 'Teacher account already exists'

    # Password should NOT have changed
    updated_provider = json.loads(sample_storage_with_teacher.provider_path.read_text())
    teacher_provider = next(
        u for u in updated_provider['data']['users']
        if u['username'] == 'admin'
    )
    assert teacher_provider['password'] == sample_storage_with_teacher.old_password_hash
