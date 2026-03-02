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


# ---------------------------------------------------------------------------
# Per-user ingress tests (X-Remote-User-* headers)
# ---------------------------------------------------------------------------

def test_per_user_ingress_creates_account():
    """When X-Remote-User-Id is present, an app account is auto-created."""
    print('Test: Per-user ingress creates account …')
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
                'X-Remote-User-Id': 'ha-user-id-001',
                'X-Remote-User-Name': 'Alice',
                'X-Remote-User-Display-Name': 'Alice',
            },
        )
        assert resp.status_code == 200

        with client.session_transaction() as sess:
            username = sess.get('username')
            assert username is not None, 'Session username should be set'
            assert username != 'admin', 'Should NOT be logged in as admin'
        # Verify the user was created in the data store
        users = app_mod.load_users()
        assert username in users, f'User "{username}" should exist in users'
        assert users[username].get('ha_user_id') == 'ha-user-id-001'
        assert users[username].get('role') == 'user'
        print(f'  ✓ Auto-created app user "{username}" for HA user Alice')
    finally:
        _teardown(data_file)


def test_different_ha_users_get_different_sessions():
    """Two different HA users should be logged in as different app users."""
    print('Test: Different HA users get different sessions …')
    data_file = _setup()
    try:
        import importlib
        import app as app_mod
        importlib.reload(app_mod)
        app_mod.DATA_FILE = data_file
        app_mod.ensure_admin_account()

        client_a = app_mod.app.test_client()
        client_b = app_mod.app.test_client()

        # User A accesses the add-on
        resp_a = client_a.get(
            '/',
            headers={
                'X-Ingress-Path': '/api/hassio_ingress/abc123',
                'X-Remote-User-Id': 'ha-user-id-A',
                'X-Remote-User-Name': 'UserA',
            },
        )
        assert resp_a.status_code == 200

        # User B accesses the add-on
        resp_b = client_b.get(
            '/',
            headers={
                'X-Ingress-Path': '/api/hassio_ingress/abc123',
                'X-Remote-User-Id': 'ha-user-id-B',
                'X-Remote-User-Name': 'UserB',
            },
        )
        assert resp_b.status_code == 200

        with client_a.session_transaction() as sess_a, \
             client_b.session_transaction() as sess_b:
            user_a = sess_a.get('username')
            user_b = sess_b.get('username')
            assert user_a is not None and user_b is not None
            assert user_a != user_b, (
                f'Users should be different but both got "{user_a}"'
            )
        print(f'  ✓ HA user A → "{user_a}", HA user B → "{user_b}"')
    finally:
        _teardown(data_file)


def test_session_updates_when_ha_user_changes():
    """If the HA user header changes, the session should update."""
    print('Test: Session updates when HA user changes …')
    data_file = _setup()
    try:
        import importlib
        import app as app_mod
        importlib.reload(app_mod)
        app_mod.DATA_FILE = data_file
        app_mod.ensure_admin_account()
        client = app_mod.app.test_client()

        # First request as user A
        client.get(
            '/',
            headers={
                'X-Ingress-Path': '/api/hassio_ingress/abc123',
                'X-Remote-User-Id': 'ha-user-A',
                'X-Remote-User-Name': 'UserA',
            },
        )
        with client.session_transaction() as sess:
            first_user = sess.get('username')

        # Second request as user B (same client/browser, different HA user)
        client.get(
            '/',
            headers={
                'X-Ingress-Path': '/api/hassio_ingress/abc123',
                'X-Remote-User-Id': 'ha-user-B',
                'X-Remote-User-Name': 'UserB',
            },
        )
        with client.session_transaction() as sess:
            second_user = sess.get('username')

        assert first_user != second_user, (
            f'Session should have changed from "{first_user}" to a different user'
        )
        print(f'  ✓ Session changed from "{first_user}" to "{second_user}"')
    finally:
        _teardown(data_file)


def test_returning_ha_user_reuses_account():
    """A returning HA user should re-use their previously created account."""
    print('Test: Returning HA user reuses account …')
    data_file = _setup()
    try:
        import importlib
        import app as app_mod
        importlib.reload(app_mod)
        app_mod.DATA_FILE = data_file
        app_mod.ensure_admin_account()

        client1 = app_mod.app.test_client()
        client2 = app_mod.app.test_client()

        # First visit
        client1.get(
            '/',
            headers={
                'X-Ingress-Path': '/api/hassio_ingress/abc123',
                'X-Remote-User-Id': 'ha-user-returning',
                'X-Remote-User-Name': 'Returning',
            },
        )
        with client1.session_transaction() as sess:
            first_username = sess.get('username')

        # Second visit (new session)
        client2.get(
            '/',
            headers={
                'X-Ingress-Path': '/api/hassio_ingress/abc123',
                'X-Remote-User-Id': 'ha-user-returning',
                'X-Remote-User-Name': 'Returning',
            },
        )
        with client2.session_transaction() as sess:
            second_username = sess.get('username')

        assert first_username == second_username, (
            f'Should reuse same account, got "{first_username}" then "{second_username}"'
        )
        # Only one user entry should have been created (plus admin)
        users = app_mod.load_users()
        ha_users = [u for u in users.values() if u.get('ha_user_id') == 'ha-user-returning']
        assert len(ha_users) == 1, f'Expected 1 HA user entry, got {len(ha_users)}'
        print(f'  ✓ Returning HA user reused account "{first_username}"')
    finally:
        _teardown(data_file)


def test_fallback_admin_login_without_user_headers():
    """Without X-Remote-User-Id, fallback to admin login (legacy behaviour)."""
    print('Test: Fallback to admin login without user headers …')
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
            },
        )
        assert resp.status_code == 200

        with client.session_transaction() as sess:
            username = sess.get('username')
            assert username is not None, 'Session should be set'
            users = app_mod.load_users()
            assert users.get(username, {}).get('role') == 'admin', \
                'Fallback should log in as admin'
        print(f'  ✓ Fallback logged in as admin "{username}"')
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
        test_per_user_ingress_creates_account,
        test_different_ha_users_get_different_sessions,
        test_session_updates_when_ha_user_changes,
        test_returning_ha_user_reuses_account,
        test_fallback_admin_login_without_user_headers,
    ]:
        try:
            test_fn()
            passed += 1
        except Exception as e:
            print(f'  ✗ FAILED: {e}')
            failed += 1
    print(f'\nResults: {passed} passed, {failed} failed')
    sys.exit(1 if failed else 0)
