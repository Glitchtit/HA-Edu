#!/usr/bin/env python3
"""
Test script for the lock button feature
"""

import sys
import os
import json
import tempfile
import unittest
from unittest.mock import Mock, patch, MagicMock

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

class TestLockFeature(unittest.TestCase):
    """Test the lock button feature"""
    
    def setUp(self):
        """Set up test environment"""
        # Create a temporary file for testing
        self.temp_file = tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json')
        # Initialize with empty JSON structure
        json.dump({'instances': {}, 'settings': {'instance_creation_enabled': True}}, self.temp_file)
        self.temp_file.close()
        
        # Set up environment variables
        os.environ['DATA_FILE'] = self.temp_file.name
        os.environ['ADMIN_PASSWORD'] = 'test_admin_password'
        
        # Mock docker client
        self.docker_patcher = patch('app.client')
        self.mock_docker = self.docker_patcher.start()
        
        # Import app after environment is set up
        import app
        self.app = app
        self.client = app.app.test_client()
        
    def tearDown(self):
        """Clean up after tests"""
        self.docker_patcher.stop()
        # Remove temporary file
        if os.path.exists(self.temp_file.name):
            os.unlink(self.temp_file.name)
    
    def test_toggle_lock_endpoint(self):
        """Test that the toggle lock endpoint works"""
        # Create a test instance
        instances = {
            'test-instance': {
                'container_id': 'abc123',
                'container_name': 'ha-edu-test-instance',
                'port': 8123,
                'created_at': '2024-01-01T00:00:00',
                'status': 'running',
                'locked': False
            }
        }
        self.app.save_instances(instances)
        
        # Toggle lock (should set to True)
        response = self.client.post('/api/instances/test-instance/toggle-lock')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertTrue(data['locked'])
        
        # Verify lock state is saved
        instances = self.app.load_instances()
        self.assertTrue(instances['test-instance']['locked'])
        
        # Toggle lock again (should set to False)
        response = self.client.post('/api/instances/test-instance/toggle-lock')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertFalse(data['locked'])
        
        # Verify lock state is saved
        instances = self.app.load_instances()
        self.assertFalse(instances['test-instance']['locked'])
    
    def test_delete_locked_instance_fails(self):
        """Test that deleting a locked instance fails"""
        # Create a locked instance
        instances = {
            'test-instance': {
                'container_id': 'abc123',
                'container_name': 'ha-edu-test-instance',
                'port': 8123,
                'created_at': '2024-01-01T00:00:00',
                'status': 'running',
                'locked': True,
                'instance_password_hash': None
            }
        }
        self.app.save_instances(instances)
        
        # Try to delete locked instance
        response = self.client.delete(
            '/api/instances/test-instance',
            json={'password': 'test_admin_password'}
        )
        self.assertEqual(response.status_code, 403)
        data = json.loads(response.data)
        self.assertIn('locked', data['error'].lower())
        
        # Verify instance still exists
        instances = self.app.load_instances()
        self.assertIn('test-instance', instances)
    
    def test_delete_unlocked_instance_succeeds(self):
        """Test that deleting an unlocked instance succeeds"""
        # Mock docker containers
        mock_container = MagicMock()
        self.mock_docker.containers.get.return_value = mock_container
        mock_volume = MagicMock()
        self.mock_docker.volumes.get.return_value = mock_volume
        
        # Create an unlocked instance
        instances = {
            'test-instance': {
                'container_id': 'abc123',
                'container_name': 'ha-edu-test-instance',
                'port': 8123,
                'created_at': '2024-01-01T00:00:00',
                'status': 'running',
                'locked': False,
                'instance_password_hash': None
            }
        }
        self.app.save_instances(instances)
        
        # Delete unlocked instance
        with patch('app.get_user_info_for_logging', return_value=('test-user', 'test')):
            response = self.client.delete(
                '/api/instances/test-instance',
                json={'password': 'test_admin_password'}
            )
        self.assertEqual(response.status_code, 200)
        
        # Verify instance was deleted
        instances = self.app.load_instances()
        self.assertNotIn('test-instance', instances)
    
    def test_delete_all_skips_locked_instances(self):
        """Test that delete all skips locked instances"""
        # Mock docker containers
        mock_container = MagicMock()
        self.mock_docker.containers.get.return_value = mock_container
        mock_volume = MagicMock()
        self.mock_docker.volumes.get.return_value = mock_volume
        
        # Create multiple instances, some locked
        instances = {
            'unlocked-1': {
                'container_id': 'abc123',
                'container_name': 'ha-edu-unlocked-1',
                'port': 8123,
                'created_at': '2024-01-01T00:00:00',
                'status': 'running',
                'locked': False
            },
            'locked-1': {
                'container_id': 'def456',
                'container_name': 'ha-edu-locked-1',
                'port': 8124,
                'created_at': '2024-01-01T00:00:00',
                'status': 'running',
                'locked': True
            },
            'unlocked-2': {
                'container_id': 'ghi789',
                'container_name': 'ha-edu-unlocked-2',
                'port': 8125,
                'created_at': '2024-01-01T00:00:00',
                'status': 'running',
                'locked': False
            }
        }
        self.app.save_instances(instances)
        
        # Delete all instances
        with patch('app.get_user_info_for_logging', return_value=('test-user', 'test')):
            response = self.client.post(
                '/api/instances/delete-all',
                json={'admin_password': 'test_admin_password'}
            )
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        
        # Verify results
        self.assertEqual(data['deleted_count'], 2)  # 2 unlocked instances deleted
        self.assertEqual(data['locked_count'], 1)   # 1 locked instance preserved
        
        # Verify locked instance still exists
        instances = self.app.load_instances()
        self.assertIn('locked-1', instances)
        self.assertNotIn('unlocked-1', instances)
        self.assertNotIn('unlocked-2', instances)
    
    def test_lock_state_defaults_to_false(self):
        """Test that lock state defaults to False for instances without it"""
        # Create an instance without lock state
        instances = {
            'test-instance': {
                'container_id': 'abc123',
                'container_name': 'ha-edu-test-instance',
                'port': 8123,
                'created_at': '2024-01-01T00:00:00',
                'status': 'running'
                # Note: no 'locked' field
            }
        }
        self.app.save_instances(instances)
        
        # Toggle lock should work even without initial lock field
        response = self.client.post('/api/instances/test-instance/toggle-lock')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertTrue(data['locked'])  # Should be True after toggle
        
        # Verify lock state is saved
        instances = self.app.load_instances()
        self.assertTrue(instances['test-instance']['locked'])


if __name__ == '__main__':
    # Run tests
    unittest.main(verbosity=2)
