#!/usr/bin/env python3
"""
Integration tests for admin access control API endpoint
"""

import sys
import os
import json
import tempfile
import unittest
from unittest.mock import patch

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


class TestAdminAccessControlAPI(unittest.TestCase):
    """Test the /api/admin/check-access endpoint with session-based auth"""

    def setUp(self):
        """Set up test client with a temporary data file"""
        self.tmpfile = tempfile.NamedTemporaryFile(
            mode='w', suffix='.json', delete=False
        )
        json.dump(
            {'instances': {}, 'settings': {'instance_creation_enabled': True}},
            self.tmpfile,
        )
        self.tmpfile.close()
        os.environ['DATA_FILE'] = self.tmpfile.name
        for v in [
            'ADMIN_PASSWORD', 'TEACHER_USERNAME', 'TEACHER_PASSWORD',
            'ADMINS', 'ADMIN_USERNAME',
        ]:
            os.environ.pop(v, None)

        import importlib
        import app as app_module
        importlib.reload(app_module)

        self.app_module = app_module
        self.app = app_module.app
        self.app.testing = True
        self.client = self.app.test_client()

    def tearDown(self):
        try:
            os.unlink(self.tmpfile.name)
        except OSError:
            pass

    # ------------------------------------------------------------------
    # Login / default admin
    # ------------------------------------------------------------------
    def test_login_default_admin(self):
        """Test login with default admin:admin credentials"""
        resp = self.client.post(
            '/api/auth/login',
            json={'username': 'admin', 'password': 'admin'},
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertEqual(data['role'], 'admin')
        self.assertTrue(data['must_change_password'])

    def test_login_wrong_password(self):
        """Test login with wrong password is rejected"""
        resp = self.client.post(
            '/api/auth/login',
            json={'username': 'admin', 'password': 'wrong'},
        )
        self.assertEqual(resp.status_code, 401)

    def test_login_nonexistent_user(self):
        """Test login with nonexistent user"""
        resp = self.client.post(
            '/api/auth/login',
            json={'username': 'nobody', 'password': 'pass'},
        )
        self.assertEqual(resp.status_code, 401)

    def test_login_missing_fields(self):
        """Test login with missing fields"""
        resp = self.client.post('/api/auth/login', json={})
        self.assertEqual(resp.status_code, 400)

    # ------------------------------------------------------------------
    # Admin session
    # ------------------------------------------------------------------
    def test_admin_session_grants_access(self):
        """Test that logged-in admin has admin access"""
        self.client.post(
            '/api/auth/login',
            json={'username': 'admin', 'password': 'admin'},
        )
        resp = self.client.get('/api/admin/check-access')
        data = resp.get_json()
        self.assertTrue(data['has_admin_access'])

    def test_unauthenticated_no_admin_access(self):
        """Test that unauthenticated user has no admin access"""
        resp = self.client.get('/api/admin/check-access')
        data = resp.get_json()
        self.assertFalse(data['has_admin_access'])

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------
    def test_register_student(self):
        """Test student registration"""
        resp = self.client.post(
            '/api/auth/register',
            json={'username': 'student1', 'password': 'pass1234'},
        )
        self.assertEqual(resp.status_code, 201)
        data = resp.get_json()
        self.assertEqual(data['role'], 'user')

    def test_register_duplicate_username(self):
        """Test duplicate username rejected"""
        self.client.post(
            '/api/auth/register',
            json={'username': 'dup', 'password': 'pass1234'},
        )
        resp = self.client.post(
            '/api/auth/register',
            json={'username': 'dup', 'password': 'other'},
        )
        self.assertEqual(resp.status_code, 409)

    # ------------------------------------------------------------------
    # Non-admin denied admin operations
    # ------------------------------------------------------------------
    def test_non_admin_denied(self):
        """Test that non-admin user cannot access admin operations"""
        self.client.post(
            '/api/auth/register',
            json={'username': 'student2', 'password': 'pass1234'},
        )
        self.client.post(
            '/api/auth/login',
            json={'username': 'student2', 'password': 'pass1234'},
        )
        resp = self.client.post('/api/instances/delete-all', json={})
        self.assertEqual(resp.status_code, 403)

    # ------------------------------------------------------------------
    # Logout
    # ------------------------------------------------------------------
    def test_logout(self):
        """Test logout clears session"""
        self.client.post(
            '/api/auth/login',
            json={'username': 'admin', 'password': 'admin'},
        )
        self.client.post('/api/auth/logout')
        resp = self.client.get('/api/auth/status')
        data = resp.get_json()
        self.assertFalse(data['logged_in'])

    # ------------------------------------------------------------------
    # Auth status
    # ------------------------------------------------------------------
    def test_auth_status_logged_in(self):
        """Test auth status when logged in"""
        self.client.post(
            '/api/auth/login',
            json={'username': 'admin', 'password': 'admin'},
        )
        resp = self.client.get('/api/auth/status')
        data = resp.get_json()
        self.assertTrue(data['logged_in'])
        self.assertEqual(data['role'], 'admin')

    def test_auth_status_not_logged_in(self):
        """Test auth status when not logged in"""
        resp = self.client.get('/api/auth/status')
        data = resp.get_json()
        self.assertFalse(data['logged_in'])


def run_tests():
    """Run the test suite"""
    suite = unittest.TestLoader().loadTestsFromTestCase(TestAdminAccessControlAPI)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    return 0 if result.wasSuccessful() else 1


if __name__ == '__main__':
    sys.exit(run_tests())
