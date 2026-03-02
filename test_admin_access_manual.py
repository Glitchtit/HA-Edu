#!/usr/bin/env python3
"""
Manual test script to verify session-based admin access control.
"""

import sys
import os
import json
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def setup_app():
    tmpfile = tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False)
    json.dump({'instances': {}, 'settings': {'instance_creation_enabled': True}}, tmpfile)
    tmpfile.close()
    os.environ['DATA_FILE'] = tmpfile.name
    for v in ['ADMIN_PASSWORD', 'TEACHER_USERNAME', 'TEACHER_PASSWORD', 'ADMINS', 'ADMIN_USERNAME']:
        os.environ.pop(v, None)

    import importlib
    import app as app_module
    importlib.reload(app_module)
    app_module.app.testing = True
    return app_module.app.test_client(), tmpfile.name


def run_scenario(client, name, steps):
    print(f"\n{'='*60}")
    print(f"Scenario: {name}")
    print(f"{'='*60}")
    for desc, method, url, kwargs, check_fn in steps:
        resp = client.post(url, **kwargs) if method == 'POST' else client.get(url, **kwargs)
        ok = check_fn(resp)
        print(f"  {'✓' if ok else '✗'} {desc} (HTTP {resp.status_code})")
        if not ok:
            print(f"    Response: {resp.get_json()}")
            return False
    return True


def main():
    print("=" * 60)
    print("HA-Edu Session-Based Auth - Manual Tests")
    print("=" * 60)

    client, tmpfile = setup_app()
    results = []

    ok = run_scenario(client, "Admin login/logout", [
        ("Login as admin", 'POST', '/api/auth/login',
         {'json': {'username': 'admin', 'password': 'admin'}},
         lambda r: r.status_code == 200 and r.get_json()['role'] == 'admin'),
        ("Admin has access", 'GET', '/api/admin/check-access', {},
         lambda r: r.get_json().get('has_admin_access') is True),
        ("Logout", 'POST', '/api/auth/logout', {},
         lambda r: r.status_code == 200),
        ("No access after logout", 'GET', '/api/admin/check-access', {},
         lambda r: r.get_json().get('has_admin_access') is False),
    ])
    results.append(ok)

    ok = run_scenario(client, "Wrong password rejected", [
        ("Wrong password", 'POST', '/api/auth/login',
         {'json': {'username': 'admin', 'password': 'wrong'}},
         lambda r: r.status_code == 401),
    ])
    results.append(ok)

    ok = run_scenario(client, "Student no admin access", [
        ("Register student", 'POST', '/api/auth/register',
         {'json': {'username': 'student1', 'password': 'pass1234'}},
         lambda r: r.status_code == 201),
        ("Student denied admin", 'GET', '/api/admin/check-access', {},
         lambda r: r.get_json().get('has_admin_access') is False),
    ])
    results.append(ok)

    passed = sum(results)
    total = len(results)
    print(f"\n{'='*60}")
    print(f"Results: {passed}/{total} passed")
    print("=" * 60)

    try:
        os.unlink(tmpfile)
    except OSError:
        pass
    return 0 if passed == total else 1


if __name__ == '__main__':
    sys.exit(main())
