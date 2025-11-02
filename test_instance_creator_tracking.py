#!/usr/bin/env python3
"""
Test script for instance creator tracking and filtering functionality
"""

import sys
import os
import json
import unittest
from unittest.mock import Mock, patch, mock_open

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

class TestInstanceCreatorTracking(unittest.TestCase):
    """Test instance creator tracking and filtering"""
    
    def setUp(self):
        """Set up test environment"""
        import app as app_module
        self.app = app_module.app
        self.app.testing = True
        self.client = self.app.test_client()
        self.app_module = app_module
    
    def test_get_user_identifier_with_email(self):
        """Test getting user identifier from Cloudflare email"""
        from app import get_user_identifier
        
        request = Mock()
        request.headers = {'Cf-Access-Authenticated-User-Email': 'student@example.com'}
        request.remote_addr = '10.0.0.1'
        
        user_id = get_user_identifier(request)
        self.assertEqual(user_id, 'student@example.com')
    
    def test_get_user_identifier_with_ip(self):
        """Test getting user identifier from IP when no email"""
        from app import get_user_identifier
        
        request = Mock()
        request.headers = {}
        request.remote_addr = '192.168.50.100'
        
        user_id = get_user_identifier(request)
        self.assertEqual(user_id, 'IP: 192.168.50.100')
    
    def test_get_user_identifier_with_x_forwarded_for(self):
        """Test getting user identifier from X-Forwarded-For"""
        from app import get_user_identifier
        
        request = Mock()
        request.headers = {'X-Forwarded-For': '203.0.113.50, 10.0.0.1'}
        request.remote_addr = '10.0.0.1'
        
        user_id = get_user_identifier(request)
        self.assertEqual(user_id, 'IP: 203.0.113.50')
    
    def test_can_view_instance_admin(self):
        """Test that admins can view all instances"""
        from app import can_view_instance
        import importlib
        
        # Set up admin environment
        with patch.dict(os.environ, {'ADMIN_PASSWORD': 'test123', 'ADMINS': 'admin@example.com'}):
            importlib.reload(self.app_module)
            
            # Admin viewing someone else's instance
            request = Mock()
            request.headers = {}
            request.remote_addr = '192.168.50.100'
            
            instance = {'created_by': 'student@example.com'}
            
            can_view = can_view_instance(request, instance)
            self.assertTrue(can_view, "Admin should be able to view all instances")
    
    def test_can_view_instance_owner(self):
        """Test that users can view their own instances"""
        from app import can_view_instance
        import importlib
        
        with patch.dict(os.environ, {'ADMIN_PASSWORD': 'test123', 'ADMINS': 'admin@example.com'}):
            importlib.reload(self.app_module)
            
            # User viewing own instance
            request = Mock()
            request.headers = {'Cf-Access-Authenticated-User-Email': 'student@example.com'}
            request.remote_addr = '10.0.0.1'
            
            instance = {'created_by': 'student@example.com'}
            
            can_view = can_view_instance(request, instance)
            self.assertTrue(can_view, "User should be able to view own instance")
    
    def test_can_view_instance_not_owner(self):
        """Test that users cannot view others' instances"""
        from app import can_view_instance
        import importlib
        
        with patch.dict(os.environ, {'ADMIN_PASSWORD': 'test123', 'ADMINS': 'admin@example.com'}):
            importlib.reload(self.app_module)
            
            # User trying to view someone else's instance
            request = Mock()
            request.headers = {'Cf-Access-Authenticated-User-Email': 'student1@example.com'}
            request.remote_addr = '10.0.0.1'
            
            instance = {'created_by': 'student2@example.com'}
            
            can_view = can_view_instance(request, instance)
            self.assertFalse(can_view, "User should not be able to view others' instances")
    
    def test_instance_filtering_for_non_admin(self):
        """Test that non-admin users only see their own instances"""
        import importlib
        
        with patch.dict(os.environ, {'ADMIN_PASSWORD': 'test123', 'ADMINS': 'admin@example.com'}):
            importlib.reload(self.app_module)
            
            # Mock instance data
            mock_instances = {
                'Instance1': {'created_by': 'student1@example.com', 'port': 8123, 'status': 'running'},
                'Instance2': {'created_by': 'student2@example.com', 'port': 8124, 'status': 'running'},
                'Instance3': {'created_by': 'student1@example.com', 'port': 8125, 'status': 'running'},
            }
            
            with patch('app.load_instances', return_value=mock_instances):
                with patch('app.update_instances_status'):
                    # Request as student1
                    response = self.client.get(
                        '/api/instances',
                        headers={'Cf-Access-Authenticated-User-Email': 'student1@example.com'},
                        environ_base={'REMOTE_ADDR': '10.0.0.1'}
                    )
                    
                    data = response.get_json()
                    
                    # Should only see their own instances
                    self.assertEqual(len(data), 2)
                    self.assertIn('Instance1', data)
                    self.assertIn('Instance3', data)
                    self.assertNotIn('Instance2', data)
    
    def test_instance_filtering_for_admin(self):
        """Test that admin users see all instances"""
        import importlib
        
        with patch.dict(os.environ, {'ADMIN_PASSWORD': 'test123', 'ADMINS': 'admin@example.com'}):
            importlib.reload(self.app_module)
            
            # Mock instance data
            mock_instances = {
                'Instance1': {'created_by': 'student1@example.com', 'port': 8123, 'status': 'running'},
                'Instance2': {'created_by': 'student2@example.com', 'port': 8124, 'status': 'running'},
                'Instance3': {'created_by': 'student1@example.com', 'port': 8125, 'status': 'running'},
            }
            
            with patch('app.load_instances', return_value=mock_instances):
                with patch('app.update_instances_status'):
                    # Request as admin
                    response = self.client.get(
                        '/api/instances',
                        headers={'Cf-Access-Authenticated-User-Email': 'admin@example.com'},
                        environ_base={'REMOTE_ADDR': '10.0.0.1'}
                    )
                    
                    data = response.get_json()
                    
                    # Should see all instances
                    self.assertEqual(len(data), 3)
                    self.assertIn('Instance1', data)
                    self.assertIn('Instance2', data)
                    self.assertIn('Instance3', data)
    
    def test_instance_filtering_for_local_user(self):
        """Test that local network users see all instances"""
        import importlib
        
        with patch.dict(os.environ, {'ADMIN_PASSWORD': 'test123', 'ADMINS': 'admin@example.com'}):
            importlib.reload(self.app_module)
            
            # Mock instance data
            mock_instances = {
                'Instance1': {'created_by': 'student1@example.com', 'port': 8123, 'status': 'running'},
                'Instance2': {'created_by': 'student2@example.com', 'port': 8124, 'status': 'running'},
            }
            
            with patch('app.load_instances', return_value=mock_instances):
                with patch('app.update_instances_status'):
                    # Request from local network
                    response = self.client.get(
                        '/api/instances',
                        environ_base={'REMOTE_ADDR': '192.168.50.100'}
                    )
                    
                    data = response.get_json()
                    
                    # Should see all instances
                    self.assertEqual(len(data), 2)

def run_tests():
    """Run the test suite"""
    suite = unittest.TestLoader().loadTestsFromTestCase(TestInstanceCreatorTracking)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    return 0 if result.wasSuccessful() else 1

if __name__ == '__main__':
    sys.exit(run_tests())
