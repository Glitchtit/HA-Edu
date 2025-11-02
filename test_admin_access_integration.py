#!/usr/bin/env python3
"""
Integration tests for admin access control API endpoint
"""

import sys
import os
import unittest
from unittest.mock import Mock, patch

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

class TestAdminAccessControlAPI(unittest.TestCase):
    """Test the /api/admin/check-access endpoint"""
    
    def setUp(self):
        """Set up test client"""
        # Import app after setting up path
        import app as app_module
        self.app = app_module.app
        self.app.testing = True
        self.client = self.app.test_client()
        self.app_module = app_module
    
    def test_check_access_local_ip(self):
        """Test admin access check with local IP"""
        # Test with local IP in 192.168.50.0/24 subnet
        import importlib
        with patch.dict(os.environ, {'ADMIN_PASSWORD': 'test123', 'ADMINS': ''}):
            importlib.reload(self.app_module)
            
            response = self.client.get(
                '/api/admin/check-access',
                environ_base={'REMOTE_ADDR': '192.168.50.100'}
            )
            
            self.assertEqual(response.status_code, 200)
            data = response.get_json()
            self.assertTrue(data['has_admin_access'], 
                          "Local IP should have admin access")
            self.assertTrue(data['admin_password_enabled'])
    
    def test_check_access_remote_ip(self):
        """Test admin access check with remote IP (not in local subnet)"""
        # Need to reload the app module to pick up new env vars
        import importlib
        with patch.dict(os.environ, {'ADMIN_PASSWORD': 'test123', 'ADMINS': ''}):
            importlib.reload(self.app_module)
            
            response = self.client.get(
                '/api/admin/check-access',
                environ_base={'REMOTE_ADDR': '10.0.0.1'}
            )
            
            self.assertEqual(response.status_code, 200)
            data = response.get_json()
            self.assertFalse(data['has_admin_access'],
                           "Remote IP should not have admin access")
            self.assertTrue(data['admin_password_enabled'])
    
    def test_check_access_cloudflare_approved_email(self):
        """Test admin access check with Cloudflare authenticated user in ADMINS list"""
        with patch.dict(os.environ, {
            'ADMIN_PASSWORD': 'test123',
            'ADMINS': 'admin@example.com,teacher@example.com'
        }):
            # Need to reload the app module to pick up new env vars
            import importlib
            importlib.reload(self.app_module)
            
            response = self.client.get(
                '/api/admin/check-access',
                headers={'Cf-Access-Authenticated-User-Email': 'admin@example.com'},
                environ_base={'REMOTE_ADDR': '10.0.0.1'}
            )
            
            self.assertEqual(response.status_code, 200)
            data = response.get_json()
            self.assertTrue(data['has_admin_access'],
                          "Approved Cloudflare user should have admin access")
    
    def test_check_access_cloudflare_unapproved_email(self):
        """Test admin access check with Cloudflare authenticated user NOT in ADMINS list"""
        with patch.dict(os.environ, {
            'ADMIN_PASSWORD': 'test123',
            'ADMINS': 'admin@example.com,teacher@example.com'
        }):
            # Need to reload the app module to pick up new env vars
            import importlib
            importlib.reload(self.app_module)
            
            response = self.client.get(
                '/api/admin/check-access',
                headers={'Cf-Access-Authenticated-User-Email': 'student@example.com'},
                environ_base={'REMOTE_ADDR': '10.0.0.1'}
            )
            
            self.assertEqual(response.status_code, 200)
            data = response.get_json()
            self.assertFalse(data['has_admin_access'],
                           "Unapproved Cloudflare user should not have admin access")
    
    def test_check_access_cloudflare_email_case_insensitive(self):
        """Test that email comparison is case-insensitive"""
        with patch.dict(os.environ, {
            'ADMIN_PASSWORD': 'test123',
            'ADMINS': 'Admin@Example.COM'
        }):
            # Need to reload the app module to pick up new env vars
            import importlib
            importlib.reload(self.app_module)
            
            response = self.client.get(
                '/api/admin/check-access',
                headers={'Cf-Access-Authenticated-User-Email': 'admin@example.com'},
                environ_base={'REMOTE_ADDR': '10.0.0.1'}
            )
            
            self.assertEqual(response.status_code, 200)
            data = response.get_json()
            self.assertTrue(data['has_admin_access'],
                          "Email comparison should be case-insensitive")
    
    def test_check_access_x_forwarded_for_header(self):
        """Test that X-Forwarded-For header is checked for IP"""
        import importlib
        with patch.dict(os.environ, {'ADMIN_PASSWORD': 'test123', 'ADMINS': ''}):
            importlib.reload(self.app_module)
            
            response = self.client.get(
                '/api/admin/check-access',
                headers={'X-Forwarded-For': '192.168.50.50, 10.0.0.1'},
                environ_base={'REMOTE_ADDR': '10.0.0.1'}
            )
            
            self.assertEqual(response.status_code, 200)
            data = response.get_json()
            self.assertTrue(data['has_admin_access'],
                          "X-Forwarded-For local IP should grant admin access")
    
    def test_check_access_no_admin_password(self):
        """Test response when admin password is not configured"""
        with patch.dict(os.environ, {'ADMIN_PASSWORD': '', 'ADMINS': ''}, clear=True):
            # Need to reload the app module to pick up new env vars
            import importlib
            importlib.reload(self.app_module)
            
            response = self.client.get(
                '/api/admin/check-access',
                environ_base={'REMOTE_ADDR': '192.168.50.100'}
            )
            
            self.assertEqual(response.status_code, 200)
            data = response.get_json()
            # Even with local IP, has_admin_access may be True but admin_password_enabled is False
            self.assertFalse(data['admin_password_enabled'],
                           "Should indicate admin password is not enabled")

def run_tests():
    """Run the test suite"""
    suite = unittest.TestLoader().loadTestsFromTestCase(TestAdminAccessControlAPI)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    return 0 if result.wasSuccessful() else 1

if __name__ == '__main__':
    sys.exit(run_tests())
