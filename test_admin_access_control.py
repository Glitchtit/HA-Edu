#!/usr/bin/env python3
"""
Test script for admin access control with session-based authentication.
"""

import sys
import os
import json
import tempfile

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def test_imports():
    """Test that all required modules can be imported"""
    print("Testing imports...")
    try:
        import flask
        from flask import Flask, request, session
        print("✓ All dependencies imported successfully")
        return True
    except ImportError as e:
        print(f"✗ Import error: {e}")
        return False


def test_is_admin_user_function():
    """Test that is_admin_user function exists and checks session role"""
    print("\nTesting is_admin_user function...")
    try:
        import app

        if hasattr(app, 'is_admin_user'):
            print("✓ is_admin_user function exists")

            # Check function signature
            import inspect
            sig = inspect.signature(app.is_admin_user)
            if 'request' in sig.parameters:
                print("✓ Function has correct signature (accepts request)")
            else:
                print("✗ Function signature incorrect")
                return False

            return True
        else:
            print("✗ is_admin_user function not found")
            return False
    except Exception as e:
        print(f"✗ Function test error: {e}")
        return False


def test_admin_check_access_route():
    """Test that admin check-access route is registered"""
    print("\nTesting /api/admin/check-access route...")
    try:
        import app

        routes = [rule.rule for rule in app.app.url_map.iter_rules()]

        if '/api/admin/check-access' in routes:
            print("✓ Route registered: /api/admin/check-access")
            return True
        else:
            print("✗ Route /api/admin/check-access not found")
            return False
    except Exception as e:
        print(f"✗ Route test error: {e}")
        return False


def test_auth_routes_registered():
    """Test that auth routes are registered"""
    print("\nTesting auth routes...")
    try:
        import app

        routes = [rule.rule for rule in app.app.url_map.iter_rules()]

        expected = [
            '/api/auth/login',
            '/api/auth/register',
            '/api/auth/logout',
            '/api/auth/status',
            '/api/auth/change-password',
        ]

        all_found = True
        for route in expected:
            if route in routes:
                print(f"✓ Route registered: {route}")
            else:
                print(f"✗ Route missing: {route}")
                all_found = False

        return all_found
    except Exception as e:
        print(f"✗ Auth routes test error: {e}")
        return False


def test_ensure_admin_account():
    """Test that ensure_admin_account creates a default admin user"""
    print("\nTesting ensure_admin_account...")
    try:
        import app

        if hasattr(app, 'ensure_admin_account'):
            print("✓ ensure_admin_account function exists")
        else:
            print("✗ ensure_admin_account function not found")
            return False

        users = app.load_users()
        has_admin = any(u.get('role') == 'admin' for u in users.values())
        if has_admin:
            print("✓ Admin account exists")
        else:
            print("✗ No admin account found")
            return False

        return True
    except Exception as e:
        print(f"✗ ensure_admin_account test error: {e}")
        return False


def test_no_old_env_vars():
    """Test that old env var attributes are gone"""
    print("\nTesting that old env vars are removed...")
    try:
        import app

        old_vars = ['ADMIN_PASSWORD', 'ADMINS', 'ADMIN_USERNAME']
        all_gone = True
        for var in old_vars:
            if hasattr(app, var):
                print(f"✗ Old attribute still present: {var}")
                all_gone = False
            else:
                print(f"✓ {var} not present (removed)")

        return all_gone
    except Exception as e:
        print(f"✗ Env var test error: {e}")
        return False


def test_frontend_updated():
    """Test that index.html has login overlay and auth endpoints"""
    print("\nTesting frontend updates...")
    template_path = os.path.join(os.path.dirname(__file__), 'templates', 'index.html')

    if os.path.exists(template_path):
        print(f"✓ Template exists at {template_path}")

        with open(template_path, 'r', encoding='utf-8') as f:
            content = f.read()

            checks = [
                ('loginOverlay', 'Login overlay element'),
                ('/api/auth/login', 'Login API call'),
                ('/api/auth/register', 'Register API call'),
                ('logged_in', 'logged_in template variable'),
            ]

            all_passed = True
            for check, desc in checks:
                if check in content:
                    print(f"✓ Found: {desc}")
                else:
                    print(f"✗ Missing: {desc}")
                    all_passed = False

            return all_passed
    else:
        print(f"✗ Template not found at {template_path}")
        return False


def main():
    """Run all tests"""
    # Setup temp data file
    tmpfile = tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False)
    json.dump({'instances': {}, 'settings': {'instance_creation_enabled': True}}, tmpfile)
    tmpfile.close()
    os.environ['DATA_FILE'] = tmpfile.name
    for v in ['ADMIN_PASSWORD', 'TEACHER_USERNAME', 'TEACHER_PASSWORD', 'ADMINS', 'ADMIN_USERNAME']:
        os.environ.pop(v, None)

    print("=" * 70)
    print("HA-Edu Admin Access Control Tests (Session-Based Auth)")
    print("=" * 70)

    tests = [
        test_imports,
        test_is_admin_user_function,
        test_admin_check_access_route,
        test_auth_routes_registered,
        test_ensure_admin_account,
        test_no_old_env_vars,
        test_frontend_updated,
    ]

    results = [test() for test in tests]

    passed = sum(1 for r in results if r)
    total = len(results)

    print("\n" + "=" * 70)
    print(f"Tests passed: {passed}/{total}")
    print("=" * 70)

    try:
        os.unlink(tmpfile.name)
    except OSError:
        pass

    if passed == total:
        print("\n✓ All tests passed!")
        return 0
    else:
        print(f"\n✗ {total - passed} test(s) failed")
        return 1


if __name__ == '__main__':
    sys.exit(main())
