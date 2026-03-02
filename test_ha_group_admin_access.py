#!/usr/bin/env python3
"""
Tests for HA group-based admin access.

When an HA user belongs to the Owner or Administrators (system-admin) group,
they should automatically receive the 'admin' role in the app.
"""

import sys
import os
import json
import tempfile
from unittest.mock import patch, MagicMock

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
    os.environ['SUPERVISOR_TOKEN'] = 'test-supervisor-token'
    os.environ.setdefault('DOCKER_HOST_IP', '127.0.0.1')
    return tmpfile.name


def _teardown(path):
    try:
        os.unlink(path)
    except OSError:
        pass
    os.environ.pop('SUPERVISOR_TOKEN', None)


def _mock_supervisor_response(users):
    """Create a mock response for the Supervisor /auth/list endpoint."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {'data': {'users': users}}
    return mock_resp


def test_owner_gets_admin_role():
    """An HA user who is_owner should get the admin role."""
    print('Test: HA Owner gets admin role …')
    data_file = _setup()
    try:
        import importlib
        import app as app_mod
        importlib.reload(app_mod)
        app_mod.DATA_FILE = data_file
        app_mod.ensure_admin_account()
        # Clear role cache
        app_mod._ha_role_cache.clear()

        supervisor_users = [
            {'username': 'OwnerUser', 'is_owner': True, 'is_active': True,
             'group_ids': ['system-admin'], 'name': 'Owner User'},
        ]

        with patch('app.requests.get', return_value=_mock_supervisor_response(supervisor_users)):
            client = app_mod.app.test_client()
            resp = client.get(
                '/',
                headers={
                    'X-Ingress-Path': '/api/hassio_ingress/abc123',
                    'X-Remote-User-Id': 'ha-owner-001',
                    'X-Remote-User-Name': 'OwnerUser',
                    'X-Remote-User-Display-Name': 'Owner User',
                },
            )
            assert resp.status_code == 200

        users = app_mod.load_users()
        owner_user = next(
            (u for u in users.values() if u.get('ha_user_id') == 'ha-owner-001'),
            None,
        )
        assert owner_user is not None, 'Owner user should exist'
        assert owner_user['role'] == 'admin', (
            f'Owner should have admin role, got "{owner_user["role"]}"'
        )
        print('  ✓ HA Owner gets admin role')
    finally:
        _teardown(data_file)


def test_administrator_gets_admin_role():
    """An HA user in the system-admin group should get the admin role."""
    print('Test: HA Administrator gets admin role …')
    data_file = _setup()
    try:
        import importlib
        import app as app_mod
        importlib.reload(app_mod)
        app_mod.DATA_FILE = data_file
        app_mod.ensure_admin_account()
        app_mod._ha_role_cache.clear()

        supervisor_users = [
            {'username': 'AdminUser', 'is_owner': False, 'is_active': True,
             'group_ids': ['system-admin'], 'name': 'Admin User'},
        ]

        with patch('app.requests.get', return_value=_mock_supervisor_response(supervisor_users)):
            client = app_mod.app.test_client()
            resp = client.get(
                '/',
                headers={
                    'X-Ingress-Path': '/api/hassio_ingress/abc123',
                    'X-Remote-User-Id': 'ha-admin-001',
                    'X-Remote-User-Name': 'AdminUser',
                    'X-Remote-User-Display-Name': 'Admin User',
                },
            )
            assert resp.status_code == 200

        users = app_mod.load_users()
        admin_user = next(
            (u for u in users.values() if u.get('ha_user_id') == 'ha-admin-001'),
            None,
        )
        assert admin_user is not None, 'Admin user should exist'
        assert admin_user['role'] == 'admin', (
            f'Administrator should have admin role, got "{admin_user["role"]}"'
        )
        print('  ✓ HA Administrator (system-admin group) gets admin role')
    finally:
        _teardown(data_file)


def test_regular_user_gets_user_role():
    """An HA user not in Owner/Administrators should get the user role."""
    print('Test: Regular HA user gets user role …')
    data_file = _setup()
    try:
        import importlib
        import app as app_mod
        importlib.reload(app_mod)
        app_mod.DATA_FILE = data_file
        app_mod.ensure_admin_account()
        app_mod._ha_role_cache.clear()

        supervisor_users = [
            {'username': 'RegularUser', 'is_owner': False, 'is_active': True,
             'group_ids': ['system-users'], 'name': 'Regular User'},
        ]

        with patch('app.requests.get', return_value=_mock_supervisor_response(supervisor_users)):
            client = app_mod.app.test_client()
            resp = client.get(
                '/',
                headers={
                    'X-Ingress-Path': '/api/hassio_ingress/abc123',
                    'X-Remote-User-Id': 'ha-user-001',
                    'X-Remote-User-Name': 'RegularUser',
                    'X-Remote-User-Display-Name': 'Regular User',
                },
            )
            assert resp.status_code == 200

        users = app_mod.load_users()
        regular_user = next(
            (u for u in users.values() if u.get('ha_user_id') == 'ha-user-001'),
            None,
        )
        assert regular_user is not None, 'Regular user should exist'
        assert regular_user['role'] == 'user', (
            f'Regular user should have user role, got "{regular_user["role"]}"'
        )
        print('  ✓ Regular HA user gets user role')
    finally:
        _teardown(data_file)


def test_role_updated_on_subsequent_login():
    """If an existing user's HA group changes, their role should update."""
    print('Test: Role updated on subsequent login …')
    data_file = _setup()
    try:
        import importlib
        import app as app_mod
        importlib.reload(app_mod)
        app_mod.DATA_FILE = data_file
        app_mod.ensure_admin_account()
        app_mod._ha_role_cache.clear()

        # First login: regular user
        supervisor_users_regular = [
            {'username': 'ChangingUser', 'is_owner': False, 'is_active': True,
             'group_ids': ['system-users'], 'name': 'Changing User'},
        ]
        with patch('app.requests.get', return_value=_mock_supervisor_response(supervisor_users_regular)):
            client = app_mod.app.test_client()
            client.get(
                '/',
                headers={
                    'X-Ingress-Path': '/api/hassio_ingress/abc123',
                    'X-Remote-User-Id': 'ha-changing-001',
                    'X-Remote-User-Name': 'ChangingUser',
                    'X-Remote-User-Display-Name': 'Changing User',
                },
            )

        users = app_mod.load_users()
        changing_user = next(
            (u for u in users.values() if u.get('ha_user_id') == 'ha-changing-001'),
            None,
        )
        assert changing_user['role'] == 'user', 'Should start as user'

        # Second login: now promoted to admin
        app_mod._ha_role_cache.clear()
        supervisor_users_admin = [
            {'username': 'ChangingUser', 'is_owner': False, 'is_active': True,
             'group_ids': ['system-admin'], 'name': 'Changing User'},
        ]
        with patch('app.requests.get', return_value=_mock_supervisor_response(supervisor_users_admin)):
            client2 = app_mod.app.test_client()
            client2.get(
                '/',
                headers={
                    'X-Ingress-Path': '/api/hassio_ingress/abc123',
                    'X-Remote-User-Id': 'ha-changing-001',
                    'X-Remote-User-Name': 'ChangingUser',
                    'X-Remote-User-Display-Name': 'Changing User',
                },
            )

        users = app_mod.load_users()
        changing_user = next(
            (u for u in users.values() if u.get('ha_user_id') == 'ha-changing-001'),
            None,
        )
        assert changing_user['role'] == 'admin', (
            f'Role should be updated to admin, got "{changing_user["role"]}"'
        )
        print('  ✓ Role updated from user to admin on subsequent login')
    finally:
        _teardown(data_file)


def test_api_failure_defaults_to_user_role():
    """If the Supervisor API call fails, default to user role."""
    print('Test: API failure defaults to user role …')
    data_file = _setup()
    try:
        import importlib
        import app as app_mod
        importlib.reload(app_mod)
        app_mod.DATA_FILE = data_file
        app_mod.ensure_admin_account()
        app_mod._ha_role_cache.clear()

        with patch('app.requests.get', side_effect=Exception('Connection refused')):
            client = app_mod.app.test_client()
            resp = client.get(
                '/',
                headers={
                    'X-Ingress-Path': '/api/hassio_ingress/abc123',
                    'X-Remote-User-Id': 'ha-error-001',
                    'X-Remote-User-Name': 'ErrorUser',
                    'X-Remote-User-Display-Name': 'Error User',
                },
            )
            assert resp.status_code == 200

        users = app_mod.load_users()
        error_user = next(
            (u for u in users.values() if u.get('ha_user_id') == 'ha-error-001'),
            None,
        )
        assert error_user is not None, 'User should still be created'
        assert error_user['role'] == 'user', (
            f'On API failure, should default to user, got "{error_user["role"]}"'
        )
        print('  ✓ API failure gracefully defaults to user role')
    finally:
        _teardown(data_file)


def test_no_supervisor_token_defaults_to_user():
    """Without SUPERVISOR_TOKEN, _fetch_ha_user_role returns user."""
    print('Test: No SUPERVISOR_TOKEN defaults to user …')
    data_file = _setup()
    try:
        import importlib
        import app as app_mod
        importlib.reload(app_mod)
        app_mod.DATA_FILE = data_file
        app_mod._ha_role_cache.clear()

        # Remove SUPERVISOR_TOKEN temporarily
        os.environ.pop('SUPERVISOR_TOKEN', None)
        role = app_mod._fetch_ha_user_role('SomeUser')
        assert role == 'user', f'Expected user, got {role}'

        # Restore for teardown
        os.environ['SUPERVISOR_TOKEN'] = 'test-supervisor-token'
        print('  ✓ No SUPERVISOR_TOKEN defaults to user role')
    finally:
        _teardown(data_file)


if __name__ == '__main__':
    passed = 0
    failed = 0
    for test_fn in [
        test_owner_gets_admin_role,
        test_administrator_gets_admin_role,
        test_regular_user_gets_user_role,
        test_role_updated_on_subsequent_login,
        test_api_failure_defaults_to_user_role,
        test_no_supervisor_token_defaults_to_user,
    ]:
        try:
            test_fn()
            passed += 1
        except Exception as exc:
            print(f'  ✗ FAILED: {exc}')
            failed += 1

    print(f'\nResults: {passed} passed, {failed} failed')
    raise SystemExit(1 if failed else 0)
