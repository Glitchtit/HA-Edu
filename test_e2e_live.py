#!/usr/bin/env python3
"""
End-to-end tests against a running HA-Edu Portal with real Docker.

These tests create real Home Assistant containers, so they are skipped unless
PORTAL_URL is set. Run them against a throwaway deployment, never production:
the suite deletes every unlocked instance when it finishes.

    PORTAL_URL=http://localhost:5000 ADMIN_PASSWORD=admin123 \\
    ADMIN_EMAIL=teacher@school.fi TEACHER_USERNAME=teacher TEACHER_PASSWORD='Lärare-123' \\
    DOCKER_CMD='sudo -n docker' python -m pytest -v test_e2e_live.py

The portal must be reached from an address outside the admin subnets (e.g. via
Docker's port publishing, which shows up as 172.x), so that requests without
ADMIN_EMAIL are treated as ordinary students.
"""

import json
import os
import shlex
import subprocess
import threading
import time
import uuid

import pytest
import requests

PORTAL_URL = os.getenv('PORTAL_URL', '').rstrip('/')
ADMIN_PASSWORD = os.getenv('ADMIN_PASSWORD', '')
ADMIN_EMAIL = os.getenv('ADMIN_EMAIL', '')
TEACHER_USERNAME = os.getenv('TEACHER_USERNAME', '')
TEACHER_PASSWORD = os.getenv('TEACHER_PASSWORD', '')
DOCKER_CMD = shlex.split(os.getenv('DOCKER_CMD', 'docker'))
HA_START_TIMEOUT = int(os.getenv('HA_START_TIMEOUT', '300'))

pytestmark = pytest.mark.skipif(not PORTAL_URL, reason='PORTAL_URL not set (live end-to-end tests)')

RUN_ID = uuid.uuid4().hex[:6]


def student(n):
    """Headers for a non-admin student authenticated through Cloudflare Access"""
    return {
        'Cf-Access-Authenticated-User-Email': f'student{n}-{RUN_ID}@school.fi',
        'CF-Connecting-IP': f'203.0.113.{n}',
    }


ADMIN = {'Cf-Access-Authenticated-User-Email': ADMIN_EMAIL, 'CF-Connecting-IP': '203.0.113.200'}


def api(method, path, headers=None, **kwargs):
    return requests.request(method, f'{PORTAL_URL}{path}', headers=headers or {}, timeout=600, **kwargs)


def create(name, headers, password=None):
    body = {'server_name': name}
    if password is not None:
        body['instance_password'] = password
    return api('POST', '/api/instances', headers, json=body)


def instances(headers=ADMIN):
    r = api('GET', '/api/instances', headers)
    r.raise_for_status()
    return r.json()


def docker(*args):
    return subprocess.run(DOCKER_CMD + list(args), capture_output=True, text=True, check=True).stdout


def read_volume_json(volume, path):
    out = docker('run', '--rm', '-v', f'{volume}:/config:ro', 'alpine:latest', 'cat', f'/config/{path}')
    return json.loads(out)


def wait_for_ha(port, headers):
    """Wait until Home Assistant answers through the proxy"""
    deadline = time.time() + HA_START_TIMEOUT
    while time.time() < deadline:
        try:
            r = api('GET', f'/proxy/{port}/api/onboarding', headers)
            if r.status_code == 200 and r.headers.get('Content-Type', '').startswith('application/json'):
                return r.json()
        except requests.RequestException:
            pass
        time.sleep(3)
    pytest.fail(f'Home Assistant on port {port} did not start within {HA_START_TIMEOUT}s')


def ha_login(port, headers, username, password):
    """Run Home Assistant's login flow through the proxy; returns the final step"""
    client_id = f'{PORTAL_URL}/'
    r = api('POST', f'/proxy/{port}/auth/login_flow', headers, json={
        'client_id': client_id,
        'handler': ['homeassistant', None],
        'redirect_uri': f'{PORTAL_URL}/?auth_callback=1',
    })
    r.raise_for_status()
    flow_id = r.json()['flow_id']
    r = api('POST', f'/proxy/{port}/auth/login_flow/{flow_id}', headers, json={
        'client_id': client_id, 'username': username, 'password': password,
    })
    r.raise_for_status()
    return r.json()


def ha_token(port, headers, auth_code):
    """Exchange an auth code for tokens - this makes HA write .storage/auth itself"""
    r = api('POST', f'/proxy/{port}/auth/token', headers, data={
        'grant_type': 'authorization_code', 'code': auth_code, 'client_id': f'{PORTAL_URL}/',
    })
    r.raise_for_status()
    return r.json()


@pytest.fixture(scope='module', autouse=True)
def cleanup():
    yield
    for name, inst in instances().items():
        if inst.get('locked'):
            api('POST', f'/api/instances/{name}/toggle-lock', ADMIN)
    api('POST', '/api/instances/delete-all', json={'admin_password': ADMIN_PASSWORD})


@pytest.fixture(scope='module')
def owned():
    """One instance owned by student 1, with a non-ASCII instance password"""
    r = create(f'Lab {RUN_ID}', student(1), password='lösenord-åäö')
    assert r.status_code == 201, r.text
    return {'name': f'Lab {RUN_ID}', 'port': r.json()['port'], 'container': f'ha-edu-lab-{RUN_ID}'}


# --- Access control -------------------------------------------------------

def test_admin_detection():
    assert api('GET', '/api/admin/check-access', ADMIN).json()['has_admin_access'] is True
    assert api('GET', '/api/admin/check-access', student(1)).json()['has_admin_access'] is False
    spoofed = {**student(1), 'X-Forwarded-For': '127.0.0.1'}
    assert api('GET', '/api/admin/check-access', spoofed).json()['has_admin_access'] is False
    assert api('GET', '/api/admin/check-access', {'X-Forwarded-For': '192.168.50.5'}).json()['has_admin_access'] is False


def test_students_only_see_own_instances(owned):
    assert owned['name'] in instances(student(1))
    assert owned['name'] not in instances(student(2))
    assert owned['name'] in instances(ADMIN)


def test_logs_are_admin_only():
    assert api('GET', '/api/logs', student(1)).status_code == 403
    assert api('GET', '/api/logs', ADMIN).status_code == 200


def test_status_and_lock_require_owner(owned):
    name = owned['name']
    assert api('GET', f'/api/instances/{name}/status', student(2)).status_code == 403
    assert api('POST', f'/api/instances/{name}/toggle-lock', student(2)).status_code == 403
    assert api('GET', f'/api/instances/{name}/status', student(1)).json()['status'] in ('running', 'restarting')


def test_proxy_requires_owner(owned):
    port = owned['port']
    assert api('GET', f'/proxy/{port}/', student(2)).status_code == 403
    assert api('GET', f'/proxy/{port}/', {'CF-Connecting-IP': '203.0.113.99'}).status_code == 403
    # Fallback routes (HA's absolute /api, /manifest.json, ...) are checked too
    assert api('GET', '/manifest.json', {**student(2), 'Referer': f'{PORTAL_URL}/proxy/{port}/'}).status_code == 403


def test_websocket_requires_owner(owned):
    import simple_websocket
    port = owned['port']
    wait_for_ha(port, student(1))
    url = PORTAL_URL.replace('http', 'ws', 1) + f'/proxy/{port}/api/websocket'

    ws = simple_websocket.Client(url, headers=student(1))
    try:
        assert json.loads(ws.receive(timeout=15))['type'] == 'auth_required'
    finally:
        ws.close()

    ws = simple_websocket.Client(url, headers=student(2))
    with pytest.raises(simple_websocket.ConnectionClosed):
        ws.receive(timeout=15)


def test_proxy_serves_ha_with_base_tag(owned):
    wait_for_ha(owned['port'], student(1))
    r = api('GET', f'/proxy/{owned["port"]}/', student(1))
    assert r.status_code == 200
    assert f'<base href="/proxy/{owned["port"]}/">' in r.text


# --- Instance names -------------------------------------------------------

@pytest.mark.parametrize('bad', ['portal', 'Portal', 'åäö', "x');alert(1)//", '-x', 'a' * 51])
def test_invalid_names_rejected(bad):
    assert create(bad, student(3)).status_code == 400


def test_colliding_name_does_not_destroy_existing(owned):
    container_before = docker('inspect', '-f', '{{.Id}}', owned['container']).strip()
    collision = owned['name'].lower().replace(' ', '-')
    assert create(collision, student(2)).status_code == 400
    assert docker('inspect', '-f', '{{.Id}}', owned['container']).strip() == container_before
    assert owned['name'] in instances()


def test_portal_container_survives_reserved_name():
    create('portal', student(3))
    assert docker('inspect', '-f', '{{.State.Running}}', 'ha-edu-portal').strip() == 'true'


# --- Concurrency (8 gunicorn workers) -------------------------------------

def test_concurrent_creates_get_unique_ports():
    results = {}

    def worker(n):
        results[n] = create(f'Conc {RUN_ID} {n}', student(10 + n))

    threads = [threading.Thread(target=worker, args=(n,)) for n in range(6)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert all(r.status_code == 201 for r in results.values()), [r.text for r in results.values()]
    ports = [r.json()['port'] for r in results.values()]
    assert len(set(ports)) == len(ports)
    stored = instances()
    for n in range(6):
        assert f'Conc {RUN_ID} {n}' in stored


def test_max_instances_enforced_per_student():
    s = student(30)
    codes = [create(f'Max {RUN_ID} {i}', s).status_code for i in range(3)]
    assert codes[:2] == [201, 201] and codes[2] == 403  # MAX_INSTANCES=2


def test_stop_all_does_not_lose_instance_created_meanwhile():
    created = {}

    def late_create():
        time.sleep(2)  # stop-all is busy stopping containers by now
        created['r'] = create(f'Late {RUN_ID}', student(40))

    t = threading.Thread(target=late_create)
    t.start()
    r = api('POST', '/api/instances/stop-all', json={'admin_password': ADMIN_PASSWORD})
    t.join()
    assert r.status_code == 200, r.text
    assert created['r'].status_code == 201, created['r'].text
    assert f'Late {RUN_ID}' in instances()
    # Its container must still exist (the orphan cleanup would remove untracked ones)
    docker('inspect', f'ha-edu-late-{RUN_ID}')


def test_start_after_stop(owned):
    name = owned['name']
    if api('GET', f'/api/instances/{name}/status', student(1)).json()['status'] == 'running':
        api('POST', '/api/instances/stop-all', json={'admin_password': ADMIN_PASSWORD})
    page = api('GET', '/', student(1)).text
    assert f"startInstance('{name}'" in page  # stopped card shows Starta
    r = api('POST', f'/api/instances/{name}/start', student(1))
    assert r.status_code == 200 and r.json()['status'] == 'running'
    assert api('POST', f'/api/instances/{name}/start', student(2)).status_code == 403
    page = api('GET', '/', student(1)).text
    assert f'href="/proxy/{owned["port"]}/"' in page  # running card shows Öppna


# --- Passwords --------------------------------------------------------------

def test_restart_with_non_ascii_password(owned):
    name = owned['name']
    assert api('POST', f'/api/instances/{name}/restart', student(1), json={'password': 'fel-å'}).status_code == 401
    assert api('POST', f'/api/instances/{name}/restart', student(1), json={'password': 'lösenord-åäö'}).status_code == 200


def test_admin_password_with_non_ascii_attempt():
    r = api('POST', '/api/admin/unlock', json={'admin_password': 'fel-lösen'})
    assert r.status_code == 401
    assert api('POST', '/api/admin/unlock', json={'admin_password': ADMIN_PASSWORD}).status_code == 200


# --- Teacher access ---------------------------------------------------------

@pytest.mark.skipif(not TEACHER_USERNAME, reason='TEACHER_USERNAME not set')
def test_teacher_access_is_not_duplicated(owned):
    port, name, volume = owned['port'], owned['name'], owned['container']
    s1 = student(1)

    # Student completes onboarding
    steps = wait_for_ha(port, s1)
    if not any(step['done'] for step in steps if step['step'] == 'user'):
        r = api('POST', f'/proxy/{port}/api/onboarding/users', s1, json={
            'client_id': f'{PORTAL_URL}/', 'name': 'Student', 'username': 'student',
            'password': 'student-pass', 'language': 'sv',
        })
        assert r.status_code == 200, r.text

    def add_teacher():
        r = api('POST', f'/api/instances/{name}/add-teacher-access', json={'admin_password': ADMIN_PASSWORD})
        assert r.status_code == 200, r.text
        wait_for_ha(port, s1)
        time.sleep(5)  # let HA finish loading auth after the automatic restart

    add_teacher()
    step = ha_login(port, s1, TEACHER_USERNAME, TEACHER_PASSWORD)
    assert step['type'] == 'create_entry', step
    # Exchanging the code makes HA rewrite .storage/auth (dropping our extra keys)
    ha_token(port, s1, step['result'])
    time.sleep(2)

    # Second add (reset) must not create another teacher account
    add_teacher()
    provider = read_volume_json(volume, '.storage/auth_provider.homeassistant')
    auth = read_volume_json(volume, '.storage/auth')
    teachers = [u for u in provider['data']['users'] if u['username'].casefold() == TEACHER_USERNAME.casefold()]
    teacher_users = [u for u in auth['data']['users'] if u.get('name') == TEACHER_USERNAME]
    assert len(teachers) == 1, teachers
    assert len(teacher_users) == 1, teacher_users

    step = ha_login(port, s1, TEACHER_USERNAME, TEACHER_PASSWORD)
    assert step['type'] == 'create_entry', step


def test_master_configuration_in_volume(owned):
    out = docker('run', '--rm', '-v', f'{owned["container"]}:/config:ro', 'alpine:latest',
                 'cat', '/config/configuration.yaml')
    expected = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'master_configuration.yaml')).read()
    assert out == expected


# --- Delete -----------------------------------------------------------------

def test_lock_blocks_delete_and_non_ascii_delete_works(owned):
    name = owned['name']
    assert api('POST', f'/api/instances/{name}/toggle-lock', student(1)).json()['locked'] is True
    r = api('DELETE', f'/api/instances/{name}', student(1), json={'password': 'lösenord-åäö'})
    assert r.status_code == 403
    assert api('POST', f'/api/instances/{name}/toggle-lock', student(1)).json()['locked'] is False
    r = api('DELETE', f'/api/instances/{name}', student(1), json={'password': 'lösenord-åäö'})
    assert r.status_code == 200, r.text
    assert name not in instances()
    with pytest.raises(subprocess.CalledProcessError):
        docker('volume', 'inspect', owned['container'])
