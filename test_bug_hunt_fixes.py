"""Targeted unit tests for the bug-hunt fixes (Docker is mocked)."""
import json
import multiprocessing
import os
import sys
import tempfile
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest

REPO = os.environ.get('HA_EDU_REPO', os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)

_tmpdir = tempfile.mkdtemp()
os.environ['DATA_FILE'] = os.path.join(_tmpdir, 'instances.json')
os.environ['ADMIN_PASSWORD'] = 'admin'
os.environ['LOG_DIR'] = os.path.join(_tmpdir, 'logs')

import docker  # noqa: E402
with patch.object(docker, 'from_env', return_value=MagicMock()):
    import app as appmod  # noqa: E402

_TEST_ENV = {k: os.environ[k] for k in ('DATA_FILE', 'ADMIN_PASSWORD', 'LOG_DIR')}


@pytest.fixture(autouse=True)
def _intact_app():
    """Re-import app if another test file left it half-reloaded

    Some older tests call importlib.reload(app) without mocking Docker; without a
    Docker daemon that reload fails part-way and leaves an app with no routes.
    """
    global appmod
    if 'create_instance' not in appmod.app.view_functions or appmod.DATA_FILE != _TEST_ENV['DATA_FILE']:
        import importlib
        with patch.dict(os.environ, _TEST_ENV), patch.object(docker, 'from_env', return_value=MagicMock()):
            appmod = importlib.reload(appmod)
    yield

# Remote (non-admin) students arriving through the Cloudflare tunnel
STUDENT = {'Cf-Access-Authenticated-User-Email': 'a@school.fi', 'CF-Connecting-IP': '203.0.113.10'}
OTHER = {'Cf-Access-Authenticated-User-Email': 'b@school.fi', 'CF-Connecting-IP': '203.0.113.11'}
REMOTE = {'REMOTE_ADDR': '172.18.0.5'}


@pytest.fixture
def client():
    appmod.save_data({'instances': {}, 'settings': {'instance_creation_enabled': True}})
    with patch.object(appmod, 'client') as docker_client, \
         patch.object(appmod, 'copy_master_config_to_volume', return_value=True):
        docker_client.containers.list.return_value = []
        docker_client.containers.get.side_effect = appmod.docker.errors.NotFound('x')
        docker_client.volumes.get.side_effect = appmod.docker.errors.NotFound('x')
        docker_client.containers.run.return_value = MagicMock(id='cid')
        c = appmod.app.test_client()
        c.environ_base.update(REMOTE)
        yield c, docker_client


def create(c, name, headers=STUDENT, password='pw'):
    body = {'server_name': name}
    if password is not None:
        body['instance_password'] = password
    return c.post('/api/instances', json=body, headers=headers)


# --- Bug 1: name collisions / validation ---

def test_colliding_name_rejected_and_nothing_removed(client):
    c, docker_client = client
    assert create(c, 'Lab 1').status_code == 201
    assert create(c, 'lab-1', OTHER).status_code == 400
    assert set(appmod.load_instances()) == {'Lab 1'}
    docker_client.volumes.get.assert_called_once()  # only for the first create


@pytest.mark.parametrize('name', ['portal', 'Portal', 'åäö', 'a/b', "x');alert(1)//", '-lead', 'a' * 51])
def test_invalid_names_rejected(client, name):
    c, _ = client
    assert create(c, name).status_code == 400
    assert appmod.load_instances() == {}


# --- Bug 2: lost updates / atomic writes ---

def test_slow_delete_keeps_instance_created_meanwhile(client):
    c, docker_client = client
    create(c, 'Old', password='pw')

    def slow_stop(*a, **k):
        with appmod.data_lock():
            inst = appmod.load_instances()
            inst['New'] = {'container_id': 'n', 'container_name': 'ha-edu-new', 'port': 9999}
            appmod.save_instances(inst)

    container = MagicMock()
    container.stop.side_effect = slow_stop
    docker_client.containers.get.side_effect = None
    docker_client.containers.get.return_value = container
    assert c.delete('/api/instances/Old', json={'password': 'pw'}, headers=STUDENT).status_code == 200
    assert set(appmod.load_instances()) == {'New'}


def test_stop_all_keeps_instance_created_meanwhile(client):
    c, docker_client = client
    create(c, 'A')

    def slow_stop(*a, **k):
        with appmod.data_lock():
            inst = appmod.load_instances()
            inst['B'] = {'container_id': 'b', 'container_name': 'ha-edu-b', 'port': 9998}
            appmod.save_instances(inst)

    container = MagicMock(status='running')
    container.stop.side_effect = slow_stop
    docker_client.containers.get.side_effect = None
    docker_client.containers.get.return_value = container
    r = c.post('/api/instances/stop-all', json={'admin_password': 'admin'})
    assert r.status_code == 200 and r.json['stopped_count'] == 1
    inst = appmod.load_instances()
    assert set(inst) == {'A', 'B'} and inst['A']['status'] == 'exited'


def _writer(worker, n):
    for i in range(n):
        with appmod.data_lock():
            inst = appmod.load_instances()
            inst[f'w{worker}-{i}'] = {'container_id': 'x', 'container_name': f'c{worker}{i}', 'port': 1}
            appmod.save_instances(inst)


def test_cross_process_writes_not_lost():
    appmod.save_data({'instances': {}, 'settings': {}})
    ctx = multiprocessing.get_context('fork')
    procs = [ctx.Process(target=_writer, args=(w, 25)) for w in range(6)]
    for p in procs:
        p.start()
    for p in procs:
        p.join()
    assert len(appmod.load_instances()) == 150


# --- Bug 3: X-Forwarded-For spoofing ---

def test_spoofed_xff_is_not_admin(client):
    c, _ = client
    r = c.get('/api/admin/check-access', headers={'X-Forwarded-For': '127.0.0.1', 'CF-Connecting-IP': '203.0.113.9'})
    assert r.json['has_admin_access'] is False
    r = c.get('/api/admin/check-access', headers={'X-Forwarded-For': '127.0.0.1'})
    assert r.json['has_admin_access'] is False  # remote_addr 172.18.0.5 is not local


def test_local_cf_ip_and_lan_are_admin(client):
    c, _ = client
    assert c.get('/api/admin/check-access', headers={'CF-Connecting-IP': '192.168.50.20'}).json['has_admin_access']
    assert c.get('/api/admin/check-access', environ_base={'REMOTE_ADDR': '192.168.50.20'}).json['has_admin_access']


# --- Bug 4: missing authorization ---

def test_toggle_lock_and_status_require_owner(client):
    c, _ = client
    create(c, 'Mine')
    assert c.post('/api/instances/Mine/toggle-lock', headers=OTHER).status_code == 403
    assert c.get('/api/instances/Mine/status', headers=OTHER).status_code == 403
    r = c.post('/api/instances/Mine/toggle-lock', headers=STUDENT)
    assert r.status_code == 200 and r.json['locked'] is True
    assert appmod.load_instances()['Mine']['locked'] is True


def test_status_is_read_only(client):
    c, _ = client
    create(c, 'Mine')
    before = os.stat(appmod.DATA_FILE).st_mtime_ns
    assert c.get('/api/instances/Mine/status', headers=STUDENT).json['status'] == 'removed'
    assert os.stat(appmod.DATA_FILE).st_mtime_ns == before


# --- Bug 5: proxy ownership ---

def test_proxy_requires_owner(client):
    c, _ = client
    create(c, 'Mine')
    port = appmod.load_instances()['Mine']['port']
    with patch.object(appmod.requests, 'get', side_effect=appmod.requests.exceptions.ConnectionError()):
        assert c.get(f'/proxy/{port}/', headers=OTHER).status_code == 403
        assert c.get(f'/proxy/{port}/', headers={'CF-Connecting-IP': '203.0.113.12'}).status_code == 403
        # Owner gets through to the (unreachable) backend
        assert c.get(f'/proxy/{port}/', headers=STUDENT).status_code == 502
        # Fallback routes go through the same check
        assert c.get('/manifest.json', headers={**OTHER, 'Referer': f'http://x/proxy/{port}/'}).status_code == 403


# --- Bug 7 / 11: passwords ---

def test_non_ascii_password_delete(client):
    c, _ = client
    create(c, 'Mine', password='lösenord')
    assert c.delete('/api/instances/Mine', json={'password': 'fel-å'}, headers=STUDENT).status_code == 401
    assert c.delete('/api/instances/Mine', json={'password': 'lösenord'}, headers=STUDENT).status_code == 200
    assert appmod.load_instances() == {}


def test_password_whitespace_consistent(client):
    c, _ = client
    create(c, 'Mine', password='  pw  ')
    assert appmod.validate_instance_password('  pw  ', appmod.load_instances()['Mine'])
    assert appmod.validate_instance_password('pw', appmod.load_instances()['Mine'])


def test_admin_password_matches():
    assert appmod.admin_password_matches('admin')
    assert not appmod.admin_password_matches('ädmin')
    assert not appmod.admin_password_matches(123)
    assert not appmod.admin_password_matches(None)


# --- Bug 14: master config copied verbatim ---

def test_master_config_copied_with_put_archive():
    import io
    import tarfile
    temp = MagicMock()
    temp.put_archive.return_value = True
    with patch.object(appmod, 'client') as docker_client:
        docker_client.containers.create.return_value = temp
        assert appmod.copy_master_config_to_volume('vol') is True
    path, data = temp.put_archive.call_args.args
    assert path == '/config'
    with tarfile.open(fileobj=io.BytesIO(data)) as tar:
        names = tar.getnames()
        config = tar.extractfile('configuration.yaml').read().decode()
    assert sorted(n for n in names if not n.startswith('.storage')) == ['automations.yaml', 'configuration.yaml', 'scenes.yaml', 'scripts.yaml']
    # Classroom core settings are prepended to the master configuration verbatim
    assert config.endswith(open(appmod.MASTER_CONFIG_PATH).read())
    assert config.startswith(appmod.render_core_config())


# --- Bugs 12 / 13: interaction logger ---

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
    lines = 0
    for f in tmp_path.glob('interactions.log*'):
        lines += sum(1 for _ in open(f))
    rotated = sorted(int(f.name.rsplit('.', 1)[1]) for f in tmp_path.glob('interactions.log.*'))
    assert rotated == list(range(1, len(rotated) + 1))  # no gaps
    assert len(rotated) >= 2  # rotation actually happened
    assert lines == 160  # no entries lost


def test_logger_periodic_cleanup(tmp_path):
    import interaction_logger as il
    lg = il.InteractionLogger(log_dir=str(tmp_path), retention_days=90)
    old = {'timestamp': (datetime.now() - timedelta(days=100)).isoformat(), 'event_type': 'x'}
    with open(lg.log_file, 'a') as f:
        f.write(json.dumps(old) + '\n')
    lg.log_admin_operation('op', 'u')  # cleanup ran at init, not due yet
    assert sum(1 for _ in open(lg.log_file)) == 2
    lg._last_cleanup -= il.CLEANUP_INTERVAL_SECONDS + 1
    lg.log_admin_operation('op', 'u')
    entries = [json.loads(line) for line in open(lg.log_file)]
    assert len(entries) == 2 and all(e['event_type'] != 'x' for e in entries)
