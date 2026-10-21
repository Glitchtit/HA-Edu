"""Regression tests for the bug-hunt fixes (Docker is mocked).

Runs against the standalone app.py by default; set HA_EDU_APP_DIR=ha-edu to
test the add-on copy.
"""
import io
import json
import multiprocessing
import os
import sys
import tarfile
import tempfile
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest

REPO = os.path.dirname(os.path.abspath(__file__))
APP_DIR = os.path.join(REPO, os.environ.get('HA_EDU_APP_DIR', ''))
sys.path.insert(0, APP_DIR)

_tmpdir = tempfile.mkdtemp()
os.environ['DATA_FILE'] = os.path.join(_tmpdir, 'instances.json')
os.environ['LOG_DIR'] = os.path.join(_tmpdir, 'logs')
os.environ.pop('SUPERVISOR_TOKEN', None)

import docker  # noqa: E402
with patch.object(docker, 'from_env', return_value=MagicMock()):
    import app as appmod  # noqa: E402

USERS = {
    'admin': {'role': 'admin', 'password_hash': 'x'},
    'alice': {'role': 'user', 'password_hash': 'x'},
    'bob': {'role': 'user', 'password_hash': 'x'},
}


@pytest.fixture
def docker_client():
    appmod.save_data({'instances': {}, 'settings': {'instance_creation_enabled': True}, 'users': dict(USERS)})
    with patch.object(appmod, 'client') as client, \
         patch.object(appmod, 'copy_master_config_to_volume', return_value=True), \
         patch.object(appmod, 'pull_and_retag_image', return_value='local/ha-edu-student:stable'):
        client.containers.list.return_value = []
        client.containers.get.side_effect = appmod.docker.errors.NotFound('x')
        client.volumes.get.side_effect = appmod.docker.errors.NotFound('x')
        client.containers.run.return_value = MagicMock(id='cid')
        yield client


def login(username):
    c = appmod.app.test_client()
    with c.session_transaction() as sess:
        sess['username'] = username
    return c


@pytest.fixture
def alice(docker_client):
    return login('alice')


@pytest.fixture
def bob(docker_client):
    return login('bob')


@pytest.fixture
def admin(docker_client):
    return login('admin')


def create(c, name, password='pw'):
    return c.post('/api/instances', json={'server_name': name, 'instance_password': password})


# --- Instance names --------------------------------------------------------

def test_colliding_name_rejected_and_nothing_removed(alice, bob, docker_client):
    assert create(alice, 'Lab 1').status_code == 201
    assert create(bob, 'lab-1').status_code == 400
    assert set(appmod.load_instances()) == {'Lab 1'}
    docker_client.volumes.get.assert_called_once()  # only for the first create


@pytest.mark.parametrize('name', ['portal', 'Portal', 'åäö', 'a/b', "x');alert(1)//", '-lead', 'a' * 51])
def test_invalid_names_rejected(alice, name):
    assert create(alice, name).status_code == 400
    assert appmod.load_instances() == {}


# --- Lost updates and atomic writes -----------------------------------------

def test_slow_delete_keeps_instance_created_meanwhile(alice, docker_client):
    create(alice, 'Old')

    def slow_stop(*a, **k):
        with appmod.data_lock():
            inst = appmod.load_instances()
            inst['New'] = {'container_id': 'n', 'container_name': 'ha-edu-new', 'port': 9999}
            appmod.save_instances(inst)

    container = MagicMock()
    container.stop.side_effect = slow_stop
    docker_client.containers.get.side_effect = None
    docker_client.containers.get.return_value = container
    assert alice.delete('/api/instances/Old', json={'password': 'pw'}).status_code == 200
    assert set(appmod.load_instances()) == {'New'}


def test_stop_all_keeps_instance_created_meanwhile(alice, admin, docker_client):
    create(alice, 'A')

    def slow_stop(*a, **k):
        with appmod.data_lock():
            inst = appmod.load_instances()
            inst['B'] = {'container_id': 'b', 'container_name': 'ha-edu-b', 'port': 9998}
            appmod.save_instances(inst)

    container = MagicMock(status='running')
    container.stop.side_effect = slow_stop
    docker_client.containers.get.side_effect = None
    docker_client.containers.get.return_value = container
    assert admin.post('/api/instances/stop-all', json={}).status_code == 200
    inst = appmod.load_instances()
    assert set(inst) == {'A', 'B'} and inst['A']['status'] == 'exited'


def test_users_survive_instance_writes(alice):
    create(alice, 'Lab 1')
    assert set(appmod.load_users()) == set(USERS)


def _writer(worker, n):
    for i in range(n):
        with appmod.data_lock():
            inst = appmod.load_instances()
            inst[f'w{worker}-{i}'] = {'container_id': 'x', 'container_name': f'c{worker}{i}', 'port': 1}
            appmod.save_instances(inst)


def test_cross_process_writes_not_lost():
    appmod.save_data({'instances': {}, 'settings': {}, 'users': {}})
    ctx = multiprocessing.get_context('fork')
    procs = [ctx.Process(target=_writer, args=(w, 25)) for w in range(6)]
    for p in procs:
        p.start()
    for p in procs:
        p.join()
    assert len(appmod.load_instances()) == 150


def _resolve(n):
    for _ in range(n):
        appmod._resolve_ha_user('ha-id-1', 'elev', 'Elev')


def test_concurrent_ha_user_resolution_creates_one_account():
    appmod.save_data({'instances': {}, 'settings': {}, 'users': {}})
    with patch.object(appmod, '_fetch_ha_user_role', return_value='user'):
        ctx = multiprocessing.get_context('fork')
        procs = [ctx.Process(target=_resolve, args=(5,)) for _ in range(6)]
        for p in procs:
            p.start()
        for p in procs:
            p.join()
    linked = [u for u, data in appmod.load_users().items() if data.get('ha_user_id') == 'ha-id-1']
    assert linked == ['Elev']


# --- Authorization -----------------------------------------------------------

def test_toggle_lock_and_status_require_owner(alice, bob):
    create(alice, 'Mine')
    assert bob.post('/api/instances/Mine/toggle-lock').status_code == 403
    assert bob.get('/api/instances/Mine/status').status_code == 403
    r = alice.post('/api/instances/Mine/toggle-lock')
    assert r.status_code == 200 and r.json['locked'] is True


def test_status_is_read_only(alice):
    create(alice, 'Mine')
    before = os.stat(appmod.DATA_FILE).st_mtime_ns
    assert alice.get('/api/instances/Mine/status').json['status'] == 'removed'
    assert os.stat(appmod.DATA_FILE).st_mtime_ns == before


def test_proxy_requires_owner(alice, bob, docker_client):
    create(alice, 'Mine')
    port = appmod.load_instances()['Mine']['port']
    anonymous = appmod.app.test_client()
    with patch.object(appmod.requests, 'get', side_effect=appmod.requests.exceptions.ConnectionError()):
        assert bob.get(f'/proxy/{port}/').status_code == 403
        assert anonymous.get(f'/proxy/{port}/').status_code == 403
        assert alice.get(f'/proxy/{port}/').status_code == 502  # reaches the (unreachable) backend
        assert bob.get('/manifest.json', headers={'Referer': f'http://x/proxy/{port}/'}).status_code == 403


# --- Passwords ---------------------------------------------------------------

def test_password_whitespace_and_non_ascii(alice):
    create(alice, 'Mine', password='  lösenord  ')
    inst = appmod.load_instances()['Mine']
    assert appmod.validate_instance_password('lösenord', inst)
    assert appmod.validate_instance_password('  lösenord  ', inst)
    assert not appmod.validate_instance_password('fel', inst)
    assert alice.delete('/api/instances/Mine', json={'password': 'lösenord'}).status_code == 200


# --- Master configuration ----------------------------------------------------

def test_master_config_copied_with_put_archive():
    temp = MagicMock()
    temp.put_archive.return_value = True
    with patch.object(appmod, 'client') as client:
        client.containers.create.return_value = temp
        assert appmod.copy_master_config_to_volume('vol') is True
    path, data = temp.put_archive.call_args.args
    with tarfile.open(fileobj=io.BytesIO(data)) as tar:
        config = tar.extractfile('configuration.yaml').read().decode()
    assert path == '/config' and config == open(appmod.MASTER_CONFIG_PATH).read()


# --- Interaction logger --------------------------------------------------------

def _log_writer(log_dir, n):
    import interaction_logger as il
    lg = il.InteractionLogger(log_dir=log_dir, retention_days=90)
    for i in range(n):
        lg.log_admin_operation('op', 'u', {'i': i})


def test_logger_cross_process_rotation_keeps_entries(tmp_path):
    import interaction_logger as il
    with patch.object(il, 'MAX_LOG_SIZE', 4000):
        ctx = multiprocessing.get_context('fork')
        procs = [ctx.Process(target=_log_writer, args=(str(tmp_path), 40)) for _ in range(4)]
        for p in procs:
            p.start()
        for p in procs:
            p.join()
    lines = sum(sum(1 for _ in open(f)) for f in tmp_path.glob('interactions.log*'))
    rotated = sorted(int(f.name.rsplit('.', 1)[1]) for f in tmp_path.glob('interactions.log.*'))
    assert rotated == list(range(1, len(rotated) + 1)) and len(rotated) >= 2
    assert lines == 160


def test_logger_periodic_cleanup(tmp_path):
    import interaction_logger as il
    lg = il.InteractionLogger(log_dir=str(tmp_path), retention_days=90)
    old = {'timestamp': (datetime.now() - timedelta(days=100)).isoformat(), 'event_type': 'x'}
    with open(lg.log_file, 'a') as f:
        f.write(json.dumps(old) + '\n')
    lg._last_cleanup -= il.CLEANUP_INTERVAL_SECONDS + 1
    lg.log_admin_operation('op', 'u')
    entries = [json.loads(line) for line in open(lg.log_file)]
    assert len(entries) == 1 and entries[0]['event_type'] != 'x'
