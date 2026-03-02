#!/usr/bin/env python3
"""
Tests for the Ingress auto-authentication feature.

When HA-Edu is accessed through Home Assistant Ingress, the Supervisor
automatically injects an ``Authorization: Bearer <token>`` header.
The add-on should use this to auto-authenticate the user as admin.
"""

import sys
import os
import json
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def _setup():
    """Create a temp data file and configure the app for testing."""
    tmpfile = tempfile.NamedTemporaryFile(
        mode='w', suffix='.json', delete=False
    )
    json.dump(
        {'instances': {}, 'settings': {'instance_creation_enabled': True}},
        tmpfile,
    )
    tmpfile.close()
    os.environ['DATA_FILE'] = tmpfile.name
    # Simulate running inside HA Supervisor
    os.environ['SUPERVISOR_TOKEN'] = 'test-supervisor-token'
    # Prevent Docker import issues during testing
    os.environ.setdefault('DOCKER_HOST_IP', '127.0.0.1')
    return tmpfile.name


def _teardown(path):
    try:
        os.unlink(path)
    except OSError:
        pass
    os.environ.pop('SUPERVISOR_TOKEN', None)


def test_ingress_bearer_auto_login():
    """Requests with X-Ingress-Path + Bearer token auto-log in as admin."""
    print('Test: Ingress Bearer auto-login …')
    data_file = _setup()
    try:
        import importlib
        import app as app_mod
        importlib.reload(app_mod)
        app_mod.DATA_FILE = data_file
        # Ensure an admin account exists
        app_mod.ensure_admin_account()
        client = app_mod.app.test_client()

        with client.session_transaction() as sess:
            # Ensure no existing session
            sess.clear()

        resp = client.get(
            '/',
            headers={
                'X-Ingress-Path': '/api/hassio_ingress/abc123',
                'Authorization': 'Bearer some-supervisor-token',
            },
        )
        assert resp.status_code == 200, f'Expected 200, got {resp.status_code}'

        # Check that the session now has the admin username
        with client.session_transaction() as sess:
            username = sess.get('username')
            assert username is not None, 'Session username should be set'
            users = app_mod.load_users()
            user = users.get(username, {})
            assert user.get('role') == 'admin', f'Expected admin role, got {user.get("role")}'
        print(f'  ✓ Auto-logged in as "{username}" (admin)')
    finally:
        _teardown(data_file)


def test_no_auto_login_without_ingress_header():
    """Requests without X-Ingress-Path should NOT auto-login."""
    print('Test: No auto-login without X-Ingress-Path …')
    data_file = _setup()
    try:
        import importlib
        import app as app_mod
        importlib.reload(app_mod)
        app_mod.DATA_FILE = data_file
        app_mod.ensure_admin_account()
        client = app_mod.app.test_client()

        with client.session_transaction() as sess:
            sess.clear()

        resp = client.get(
            '/',
            headers={'Authorization': 'Bearer some-supervisor-token'},
        )
        assert resp.status_code == 200, f'Expected 200, got {resp.status_code}'

        with client.session_transaction() as sess:
            assert sess.get('username') is None, 'Session should remain empty without ingress header'
        print('  ✓ No auto-login without ingress header')
    finally:
        _teardown(data_file)


def test_auto_login_without_bearer():
    """Ingress requests without Bearer token should still auto-login.

    The presence of SUPERVISOR_TOKEN + X-Ingress-Path is sufficient proof
    that the Supervisor has already authenticated the user.
    """
    print('Test: Auto-login without Bearer token …')
    data_file = _setup()
    try:
        import importlib
        import app as app_mod
        importlib.reload(app_mod)
        app_mod.DATA_FILE = data_file
        app_mod.ensure_admin_account()
        client = app_mod.app.test_client()

        with client.session_transaction() as sess:
            sess.clear()

        resp = client.get(
            '/',
            headers={'X-Ingress-Path': '/api/hassio_ingress/abc123'},
        )
        assert resp.status_code == 200, f'Expected 200, got {resp.status_code}'

        with client.session_transaction() as sess:
            assert sess.get('username') is not None, 'Session should be set even without bearer token'
        print('  ✓ Auto-login without bearer token')
    finally:
        _teardown(data_file)


def test_already_logged_in_not_overwritten():
    """If user is already logged in, ingress auth should not overwrite."""
    print('Test: Existing session not overwritten …')
    data_file = _setup()
    try:
        import importlib
        import app as app_mod
        importlib.reload(app_mod)
        app_mod.DATA_FILE = data_file
        app_mod.ensure_admin_account()
        # Create a regular user
        users = app_mod.load_users()
        users['student1'] = {
            'password_hash': app_mod.hash_password('pass'),
            'role': 'user',
        }
        app_mod.save_users(users)

        client = app_mod.app.test_client()

        # Pre-set session to student1
        with client.session_transaction() as sess:
            sess['username'] = 'student1'

        resp = client.get(
            '/',
            headers={
                'X-Ingress-Path': '/api/hassio_ingress/abc123',
                'Authorization': 'Bearer some-supervisor-token',
            },
        )
        assert resp.status_code == 200

        with client.session_transaction() as sess:
            assert sess.get('username') == 'student1', 'Existing session should not be overwritten'
        print('  ✓ Existing session preserved')
    finally:
        _teardown(data_file)


def test_no_auto_login_without_supervisor_token():
    """Without SUPERVISOR_TOKEN env var, ingress auto-auth should be disabled."""
    print('Test: No auto-login without SUPERVISOR_TOKEN …')
    data_file = _setup()
    # Remove SUPERVISOR_TOKEN to simulate standalone (non-HA) deployment
    os.environ.pop('SUPERVISOR_TOKEN', None)
    try:
        import importlib
        import app as app_mod
        importlib.reload(app_mod)
        app_mod.DATA_FILE = data_file
        app_mod.ensure_admin_account()
        client = app_mod.app.test_client()

        with client.session_transaction() as sess:
            sess.clear()

        resp = client.get(
            '/',
            headers={
                'X-Ingress-Path': '/api/hassio_ingress/abc123',
                'Authorization': 'Bearer some-supervisor-token',
            },
        )
        assert resp.status_code == 200

        with client.session_transaction() as sess:
            assert sess.get('username') is None, 'Session should remain empty without SUPERVISOR_TOKEN'
        print('  ✓ No auto-login without SUPERVISOR_TOKEN')
    finally:
        _teardown(data_file)


def test_login_overlay_hidden_in_ingress_mode():
    """The login overlay should not appear when accessed via Ingress."""
    print('Test: Login overlay hidden in ingress mode …')
    data_file = _setup()
    try:
        import importlib
        import app as app_mod
        importlib.reload(app_mod)
        app_mod.DATA_FILE = data_file
        app_mod.ensure_admin_account()
        client = app_mod.app.test_client()

        with client.session_transaction() as sess:
            sess.clear()

        resp = client.get(
            '/',
            headers={
                'X-Ingress-Path': '/api/hassio_ingress/abc123',
                'Authorization': 'Bearer some-supervisor-token',
            },
        )
        assert resp.status_code == 200
        html = resp.data.decode()
        assert 'loginOverlay' not in html, 'Login overlay should not be present in ingress mode'
        assert 'Logga ut' not in html, 'Logout button should not be present in ingress mode'
        print('  ✓ Login overlay and logout button hidden in ingress mode')
    finally:
        _teardown(data_file)


if __name__ == '__main__':
    passed = 0
    failed = 0
    for test_fn in [
        test_ingress_bearer_auto_login,
        test_no_auto_login_without_ingress_header,
        test_auto_login_without_bearer,
        test_already_logged_in_not_overwritten,
        test_no_auto_login_without_supervisor_token,
        test_login_overlay_hidden_in_ingress_mode,
    ]:
        try:
            test_fn()
            passed += 1
        except Exception as e:
            print(f'  ✗ FAILED: {e}')
            failed += 1
    print(f'\nResults: {passed} passed, {failed} failed')
    sys.exit(1 if failed else 0)
