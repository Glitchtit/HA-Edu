"""Unit tests for the classroom features (Docker is mocked).

Covers instance hostnames, the /proxy/ stopgaps, configuration templates and
classroom settings, teacher tools (progress, push file, export), snapshots and
undo of reset, idle stop, image pull throttling and container limits.
"""
import io
import json
import os
import re
import sys
import tarfile
import tempfile
import time
from unittest.mock import MagicMock, patch

import pytest

REPO = os.path.dirname(os.path.abspath(__file__))
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

STUDENT = {'Cf-Access-Authenticated-User-Email': 'a@school.fi', 'CF-Connecting-IP': '203.0.113.10'}
OTHER = {'Cf-Access-Authenticated-User-Email': 'b@school.fi', 'CF-Connecting-IP': '203.0.113.11'}
REMOTE = {'REMOTE_ADDR': '172.18.0.5'}


def tar_stream(files):
    """Docker-style get_archive stream: chunks of an uncompressed tar"""
    data = appmod.build_tar(files)
    return iter([data[i:i + 1000] for i in range(0, len(data), 1000)]), {}


@pytest.fixture
def docker_client():
    appmod.save_data({'instances': {}, 'settings': {'instance_creation_enabled': True}})
    appmod._progress_cache.clear()
    with patch.object(appmod, 'client') as client, \
         patch.object(appmod, 'copy_master_config_to_volume', return_value=True), \
         patch.object(appmod, 'pull_ha_image_if_due'):
        client.containers.list.return_value = []
        client.containers.get.side_effect = appmod.docker.errors.NotFound('x')
        client.volumes.get.side_effect = appmod.docker.errors.NotFound('x')
        client.containers.run.return_value = MagicMock(id='cid')
        yield client


@pytest.fixture
def c(docker_client):
    test_client = appmod.app.test_client()
    test_client.environ_base.update(REMOTE)
    return test_client


def create(c, name, headers=STUDENT, **extra):
    return c.post('/api/instances', json={'server_name': name, 'instance_password': 'pw', **extra}, headers=headers)


@pytest.fixture
def hostnames():
    template = 'https://ha-{slug}.example.com'
    with patch.object(appmod, 'INSTANCE_URL_TEMPLATE', template), \
         patch.object(appmod, 'INSTANCE_HOST_REGEX', appmod._instance_host_regex(template)):
        yield


# --- Instance hostnames -----------------------------------------------------

def test_instance_url_and_slug(hostnames):
    inst = {'container_name': 'ha-edu-elev-lab.1', 'port': 8123}
    assert appmod.instance_slug('Elev Lab.1', inst) == 'elev-lab-1'
    assert appmod.instance_url('Elev Lab.1', inst) == 'https://ha-elev-lab-1.example.com/'


def test_instance_url_without_template():
    assert appmod.instance_url('x', {'container_name': 'ha-edu-x', 'port': 8124}) == '/proxy/8124/'


def test_host_regex_requires_slug():
    with pytest.raises(ValueError):
        appmod._instance_host_regex('https://ha.example.com')


def test_hostname_requests_go_to_instance_unchanged(c, hostnames):
    create(c, 'Lab 1')
    backend = MagicMock(status_code=200, headers={'Content-Type': 'text/html'}, content=b'<html><head></head></html>')
    backend.iter_content.return_value = [b'<html><head></head></html>']
    with patch.object(appmod.requests, 'get', return_value=backend) as get:
        r = c.get('/config/automation/dashboard?x=1', headers={**STUDENT, 'Host': 'ha-lab-1.example.com'})
    assert r.status_code == 200
    assert get.call_args.args[0].endswith(':%d/config/automation/dashboard?x=1' % appmod.load_instances()['Lab 1']['port'])
    assert b'<base' not in r.data  # no rewriting needed on its own origin


def test_hostname_access_control_and_unknown_slug(c, hostnames):
    create(c, 'Lab 1')
    with patch.object(appmod.requests, 'get', side_effect=appmod.requests.exceptions.ConnectionError()):
        assert c.get('/', headers={**OTHER, 'Host': 'ha-lab-1.example.com'}).status_code == 403
        assert c.get('/', headers={**STUDENT, 'Host': 'ha-nope.example.com'}).status_code == 404
        # Portal host is unaffected
        assert c.get('/api/config-templates', headers={**STUDENT, 'Host': 'edu.example.com'}).status_code == 200


def test_hostname_redirects_not_prefixed(c, hostnames):
    create(c, 'Lab 1')
    backend = MagicMock(status_code=302, headers={'Location': '/onboarding.html'})
    backend.iter_content.return_value = []
    with patch.object(appmod.requests, 'get', return_value=backend):
        r = c.get('/', headers={**STUDENT, 'Host': 'ha-lab-1.example.com'})
    assert r.headers['Location'] == '/onboarding.html'


def test_api_lists_instance_urls(c, hostnames):
    create(c, 'Lab 1')
    assert c.get('/api/instances', headers=STUDENT).json['Lab 1']['url'] == 'https://ha-lab-1.example.com/'


def test_slug_collision_rejected(c):
    assert create(c, 'lab-1').status_code == 201
    assert create(c, 'lab.1', OTHER).status_code == 400


# --- /proxy/ stopgaps ---------------------------------------------------------

def test_onboarding_callback_redirected_to_instance(c):
    create(c, 'Lab 1')
    port = appmod.load_instances()['Lab 1']['port']
    with patch.object(appmod.requests, 'get', side_effect=appmod.requests.exceptions.ConnectionError()):
        c.get(f'/proxy/{port}/', headers=STUDENT)
    r = c.get('/?auth_callback=1&code=abc&state=xyz', headers=STUDENT)
    assert r.status_code == 302
    assert r.headers['Location'].endswith(f'/proxy/{port}/?auth_callback=1&code=abc&state=xyz')


def test_reload_of_frontend_path_goes_to_last_instance(c):
    create(c, 'Lab 1')
    port = appmod.load_instances()['Lab 1']['port']
    backend = MagicMock(status_code=200, headers={'Content-Type': 'text/html'}, content=b'<html><head></head></html>')
    with patch.object(appmod.requests, 'get', return_value=backend) as get:
        c.get(f'/proxy/{port}/', headers=STUDENT)
        r = c.get('/home/overview', headers=STUDENT)
    assert r.status_code == 200
    assert get.call_args.args[0].endswith(f':{port}/home/overview')
    assert f'<base href="/proxy/{port}/">'.encode() in r.data


def test_unknown_path_without_session_is_404(c):
    assert c.get('/home/overview', headers=STUDENT).status_code == 404


# --- Creation rules and templates -------------------------------------------

def test_password_required(c):
    r = c.post('/api/instances', json={'server_name': 'Lab 1'}, headers=STUDENT)
    assert r.status_code == 400 and 'password' in r.json['error']


def test_templates_listed_and_validated(c, docker_client):
    names = [t['name'] for t in c.get('/api/config-templates').json['templates']]
    assert names[0] == 'standard' and 'automationer' in names
    assert create(c, 'Lab 1', config_template='nope').status_code == 400
    assert create(c, 'Lab 2', config_template='automationer').status_code == 201
    assert appmod.load_instances()['Lab 2']['config_template'] == 'automationer'
    appmod.copy_master_config_to_volume.assert_called_with('ha-edu-lab-2', 'automationer')


def test_core_settings_prepended():
    files = appmod.load_config_template_files()
    config = files['configuration.yaml']
    assert config.startswith('# Classroom settings')
    assert '  time_zone: "Europe/Helsinki"' in config and '  country: "FI"' in config
    assert 'google_translate' not in config
    with patch.object(appmod, 'HA_TIME_ZONE', ''), patch.object(appmod, 'HA_COUNTRY', ''), \
         patch.object(appmod, 'HA_LANGUAGE', ''), patch.object(appmod, 'HA_CURRENCY', ''), \
         patch.object(appmod, 'HA_UNIT_SYSTEM', ''):
        assert appmod.render_core_config() == ''


def test_location_step_skipped_when_country_set():
    files = appmod.load_config_template_files()
    assert json.loads(files['.storage/onboarding'])['data']['done'] == ['core_config']
    with patch.object(appmod, 'HA_SKIP_LOCATION_STEP', False):
        assert '.storage/onboarding' not in appmod.load_config_template_files()
    with patch.object(appmod, 'HA_LATITUDE', '60.1'), patch.object(appmod, 'HA_LONGITUDE', '24.9'):
        assert '  latitude: 60.1\n  longitude: 24.9\n' in appmod.render_core_config()


def test_lesson_template_files():
    files = appmod.load_config_template_files('automationer')
    assert 'input_boolean:' in files['configuration.yaml']
    assert b'starter_welcome_home' in files['automations.yaml']
    assert files['scripts.yaml'] == '{}\n'


def test_build_tar_nested_paths():
    data = appmod.build_tar({'blueprints/automation/x/y.yaml': 'a: 1\n', 'top.yaml': b'b'})
    with tarfile.open(fileobj=io.BytesIO(data)) as tar:
        names = tar.getnames()
        assert tar.extractfile('blueprints/automation/x/y.yaml').read() == b'a: 1\n'
    assert names.index('blueprints') < names.index('blueprints/automation') < names.index('blueprints/automation/x/y.yaml')


def test_run_instance_container_limits_and_timezone():
    with patch.object(appmod, 'client') as client, patch.object(appmod, 'pull_ha_image_if_due'):
        appmod.run_instance_container('ha-edu-x', 8130)
    kwargs = client.containers.run.call_args.kwargs
    assert kwargs['mem_limit'] == '1g' and kwargs['nano_cpus'] == 1_000_000_000
    assert kwargs['environment']['TZ'] == 'Europe/Helsinki'
    assert kwargs['volumes'] == {'ha-edu-x': {'bind': '/config', 'mode': 'rw'}}


def test_image_pull_throttled(tmp_path):
    with patch.object(appmod, 'DATA_FILE', str(tmp_path / 'instances.json')), \
         patch.object(appmod, 'client') as client:
        appmod.pull_ha_image_if_due()
        appmod.pull_ha_image_if_due()
        assert client.images.pull.call_count == 1
        os.utime(tmp_path / '.last_image_pull', (0, 0))
        appmod.pull_ha_image_if_due()
        assert client.images.pull.call_count == 2


# --- Teacher tools ----------------------------------------------------------

def make_container(files, status='running'):
    container = MagicMock(status=status, id='cid')

    def get_archive(path):
        if path == '/config':
            return tar_stream({f'config/{k}': v for k, v in files.items()})
        key = path[len('/config/'):]
        if key not in files:
            raise appmod.docker.errors.NotFound('missing')
        return tar_stream({key.rsplit('/', 1)[-1]: files[key]})

    container.get_archive.side_effect = get_archive
    container.put_archive.return_value = True
    return container


def test_progress_overview(c, docker_client):
    create(c, 'Lab 1')
    docker_client.containers.get.side_effect = None
    docker_client.containers.get.return_value = make_container({
        '.storage/auth_provider.homeassistant': json.dumps({'data': {'users': [{'username': 'elev'}]}}),
        'automations.yaml': '- id: "1"\n  alias: a\n- id: "2"\n  alias: b\n',
        'scripts.yaml': 'hello:\n  sequence: []\nbye:\n  sequence: []\n',
        'scenes.yaml': '[]\n',
    })
    assert c.get('/api/admin/progress', headers=STUDENT).status_code == 403
    r = c.get('/api/admin/progress', environ_base={'REMOTE_ADDR': '127.0.0.1'})
    p = r.json['instances'][0]
    assert (p['onboarded'], p['users'], p['automations'], p['scripts'], p['scenes']) == (True, 1, 2, 2, 0)
    assert p['created_by'] == 'a@school.fi'


def test_push_file(c, docker_client):
    create(c, 'Lab 1')
    container = make_container({})
    docker_client.containers.get.side_effect = None
    docker_client.containers.get.return_value = container
    body = {'admin_password': 'admin', 'path': 'blueprints/automation/l/x.yaml', 'content': 'blueprint: {}\n'}
    assert c.post('/api/admin/push-file', json={**body, 'admin_password': 'bad'}).status_code == 401
    for bad in ['../x', '.storage/auth', '/', '']:
        assert c.post('/api/admin/push-file', json={**body, 'path': bad}).status_code == 400
    r = c.post('/api/admin/push-file', json=body)
    assert r.status_code == 200 and r.json['results'][0]['status'] == 'success'
    path, data = container.put_archive.call_args.args
    assert path == '/config'
    with tarfile.open(fileobj=io.BytesIO(data)) as tar:
        assert tar.extractfile('blueprints/automation/l/x.yaml').read() == b'blueprint: {}\n'
    container.restart.assert_not_called()


def test_export_excludes_login_data_and_history(c, docker_client):
    create(c, 'Lab 1')
    docker_client.containers.get.side_effect = None
    docker_client.containers.get.return_value = make_container({
        'configuration.yaml': 'demo:\n',
        'home-assistant_v2.db': b'big',
        '.storage/auth': '{}',
        '.storage/core.entity_registry': '{}',
    })
    assert c.get('/api/instances/Lab 1/export', headers=OTHER).status_code == 403
    r = c.get('/api/instances/Lab 1/export', headers=STUDENT)
    assert r.status_code == 200 and 'attachment' in r.headers['Content-Disposition']
    with tarfile.open(fileobj=io.BytesIO(r.data), mode='r:gz') as tar:
        names = tar.getnames()
    assert 'config/configuration.yaml' in names and 'config/.storage/core.entity_registry' in names
    assert 'config/.storage/auth' not in names and 'config/home-assistant_v2.db' not in names


def test_snapshots_kept_and_pruned(tmp_path):
    container = make_container({'configuration.yaml': 'a', '.storage/auth': '{}', 'home-assistant_v2.db': 'x'})
    with patch.object(appmod, 'SNAPSHOT_DIR', str(tmp_path)):
        paths = []
        for i in range(4):
            with patch.object(appmod, 'datetime') as dt:
                dt.now.return_value.strftime.return_value = f'2026010{i}T000000'
                paths.append(appmod.take_config_snapshot(container, 'ha-edu-x'))
        kept = appmod.snapshot_paths('ha-edu-x')
        assert kept == sorted(paths[1:], reverse=True)  # newest first, oldest pruned
        with tarfile.open(kept[0], 'r:gz') as tar:
            names = tar.getnames()
        # Login data is kept so the student can still log in after undo
        assert 'config/.storage/auth' in names and 'config/home-assistant_v2.db' not in names
        appmod.delete_snapshots('ha-edu-x')
        assert appmod.snapshot_paths('ha-edu-x') == []


def test_reset_takes_snapshot_and_undo_restores(c, docker_client, tmp_path):
    create(c, 'Lab 1')
    container = make_container({'configuration.yaml': 'mine'})
    docker_client.containers.get.side_effect = None
    docker_client.containers.get.return_value = container
    with patch.object(appmod, 'SNAPSHOT_DIR', str(tmp_path)):
        assert c.post('/api/instances/Lab 1/reset', json={'password': 'pw'}, headers=STUDENT).status_code == 200
        snapshot = appmod.load_instances()['Lab 1']['last_snapshot']
        assert snapshot and appmod.snapshot_paths('ha-edu-lab-1')

        assert c.post('/api/instances/Lab 1/undo-reset', json={'password': 'bad'}, headers=STUDENT).status_code == 401
        temp = MagicMock()
        temp.exec_run.return_value = MagicMock(exit_code=0)
        temp.put_archive.return_value = True
        docker_client.containers.create.return_value = temp
        r = c.post('/api/instances/Lab 1/undo-reset', json={'password': 'pw'}, headers=STUDENT)
        assert r.status_code == 200
        assert temp.put_archive.call_args.args[0] == '/'
        container.start.assert_called()
        assert appmod.snapshot_paths('ha-edu-lab-1') == []
        assert appmod.load_instances()['Lab 1']['last_snapshot'] is None
        assert c.post('/api/instances/Lab 1/undo-reset', json={'password': 'pw'}, headers=STUDENT).status_code == 404


def test_ready_endpoint(c):
    create(c, 'Lab 1')
    with patch.object(appmod, 'is_instance_ready', return_value=True):
        assert c.get('/api/instances/Lab 1/ready', headers=STUDENT).json == {'ready': True}
        assert c.get('/api/instances/Lab 1/ready', headers=OTHER).status_code == 403


# --- Idle stop ----------------------------------------------------------------

def test_idle_instances_stopped(tmp_path, docker_client):
    appmod.save_data({'instances': {
        'Idle': {'container_id': 'a', 'container_name': 'ha-edu-idle', 'port': 9001},
        'Active': {'container_id': 'b', 'container_name': 'ha-edu-active', 'port': 9002},
        'Locked': {'container_id': 'c', 'container_name': 'ha-edu-locked', 'port': 9003, 'locked': True},
    }, 'settings': {}})
    old_start = {'State': {'StartedAt': '2020-01-01T00:00:00.123456789Z'}}
    containers = {cid: MagicMock(status='running', attrs=old_start) for cid in 'abc'}
    docker_client.containers.get.side_effect = lambda cid: containers[cid]
    with patch.object(appmod, 'ACTIVITY_DIR', str(tmp_path)), patch.object(appmod, 'IDLE_STOP_HOURS', 4):
        appmod._activity_last_touch.clear()
        appmod.touch_activity(9002)
        appmod.stop_idle_instances()
    containers['a'].stop.assert_called_once()
    containers['b'].stop.assert_not_called()
    containers['c'].stop.assert_not_called()
    assert appmod.load_instances()['Idle']['status'] == 'exited'


def test_recently_started_instance_not_stopped(docker_client):
    appmod.save_data({'instances': {'New': {'container_id': 'a', 'container_name': 'ha-edu-new', 'port': 9011}}, 'settings': {}})
    started = time.strftime('%Y-%m-%dT%H:%M:%S.000000000Z', time.gmtime())
    container = MagicMock(status='running', attrs={'State': {'StartedAt': started}})
    docker_client.containers.get.side_effect = lambda cid: container
    with patch.object(appmod, 'IDLE_STOP_HOURS', 4):
        appmod.stop_idle_instances()
    container.stop.assert_not_called()
