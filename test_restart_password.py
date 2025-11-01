#!/usr/bin/env python3
"""
Test script for instance password and restart functionality
"""

import sys
import os
import unittest
import docker
from unittest.mock import Mock, patch, MagicMock

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import app


class TestPasswordFunctions(unittest.TestCase):
    """Test password hashing and verification"""
    
    def test_hash_password(self):
        """Test that passwords are hashed correctly"""
        password = "test_password_123"
        hashed = app.hash_password(password)
        
        # Verify hash is not empty and different from original
        self.assertIsNotNone(hashed)
        self.assertNotEqual(hashed, password)
        self.assertTrue(len(hashed) > 0)
    
    def test_verify_password_correct(self):
        """Test that correct passwords verify successfully"""
        password = "test_password_123"
        hashed = app.hash_password(password)
        
        # Verify correct password
        self.assertTrue(app.verify_password(password, hashed))
    
    def test_verify_password_incorrect(self):
        """Test that incorrect passwords fail verification"""
        password = "test_password_123"
        wrong_password = "wrong_password"
        hashed = app.hash_password(password)
        
        # Verify wrong password fails
        self.assertFalse(app.verify_password(wrong_password, hashed))


class TestRestartInstanceContainer(unittest.TestCase):
    """Test container restart functionality"""
    
    @patch('app.client')
    def test_restart_instance_container_success(self, mock_client):
        """Test successful container restart"""
        # Mock container
        mock_container = Mock()
        mock_container.restart = Mock()
        mock_client.containers.get.return_value = mock_container
        
        container_id = "test_container_id"
        success, message = app.restart_instance_container(container_id)
        
        # Verify restart was called
        self.assertTrue(success)
        self.assertEqual(message, 'Instance restarted successfully')
        mock_container.restart.assert_called_once_with(timeout=10)
    
    @patch('app.client')
    def test_restart_instance_container_not_found(self, mock_client):
        """Test restart fails when container not found"""
        mock_client.containers.get.side_effect = docker.errors.NotFound("Container not found")
        
        container_id = "nonexistent_container"
        success, message = app.restart_instance_container(container_id)
        
        # Verify failure
        self.assertFalse(success)
        self.assertEqual(message, 'Instance not found')


class TestCreateInstanceWithPassword(unittest.TestCase):
    """Test instance creation with password"""
    
    @patch('app.client')
    @patch('app.save_instances')
    @patch('app.load_instances')
    @patch('app.load_settings')
    @patch('app.get_available_port')
    @patch('app.copy_master_config_to_volume')
    def test_create_instance_with_password(self, mock_copy_config, mock_get_port, 
                                          mock_load_settings, mock_load_instances, 
                                          mock_save_instances, mock_client):
        """Test that instance password is hashed and stored"""
        # Setup mocks
        mock_load_settings.return_value = {'instance_creation_enabled': True}
        mock_load_instances.return_value = {}
        mock_get_port.return_value = 8123
        mock_copy_config.return_value = True
        
        # Mock container creation
        mock_container = Mock()
        mock_container.id = "test_container_id"
        mock_client.containers.run.return_value = mock_container
        
        # Create test client
        with app.app.test_client() as client:
            response = client.post('/api/instances', json={
                'server_name': 'Test Instance',
                'instance_password': 'test_password'
            })
            
            # Verify response
            self.assertEqual(response.status_code, 201)
            
            # Verify save_instances was called
            self.assertTrue(mock_save_instances.called)
            
            # Get the saved instance data
            saved_data = mock_save_instances.call_args[0][0]
            self.assertIn('Test Instance', saved_data)
            
            # Verify password hash was stored
            instance = saved_data['Test Instance']
            self.assertIn('instance_password_hash', instance)
            self.assertIsNotNone(instance['instance_password_hash'])
            
            # Verify the hash is valid
            self.assertTrue(app.verify_password('test_password', instance['instance_password_hash']))
    
    @patch('app.client')
    @patch('app.save_instances')
    @patch('app.load_instances')
    @patch('app.load_settings')
    @patch('app.get_available_port')
    @patch('app.copy_master_config_to_volume')
    def test_create_instance_without_password(self, mock_copy_config, mock_get_port, 
                                             mock_load_settings, mock_load_instances, 
                                             mock_save_instances, mock_client):
        """Test that instance can be created without password"""
        # Setup mocks
        mock_load_settings.return_value = {'instance_creation_enabled': True}
        mock_load_instances.return_value = {}
        mock_get_port.return_value = 8123
        mock_copy_config.return_value = True
        
        # Mock container creation
        mock_container = Mock()
        mock_container.id = "test_container_id"
        mock_client.containers.run.return_value = mock_container
        
        # Create test client
        with app.app.test_client() as client:
            response = client.post('/api/instances', json={
                'server_name': 'Test Instance No Password'
            })
            
            # Verify response
            self.assertEqual(response.status_code, 201)
            
            # Get the saved instance data
            saved_data = mock_save_instances.call_args[0][0]
            instance = saved_data['Test Instance No Password']
            
            # Verify password hash was NOT stored
            self.assertNotIn('instance_password_hash', instance)


class TestRestartEndpoint(unittest.TestCase):
    """Test the restart API endpoint"""
    
    @patch('app.restart_instance_container')
    @patch('app.save_instances')
    @patch('app.load_instances')
    @patch('app.ADMIN_PASSWORD', 'admin_password')
    def test_restart_with_admin_password(self, mock_load_instances, mock_save_instances, 
                                        mock_restart):
        """Test restart with admin password"""
        # Setup mock instance
        mock_load_instances.return_value = {
            'Test Instance': {
                'container_id': 'test_container_id',
                'port': 8123,
                'status': 'running'
            }
        }
        mock_restart.return_value = (True, 'Instance restarted successfully')
        
        # Test restart with admin password
        with app.app.test_client() as client:
            response = client.post('/api/instances/Test Instance/restart', json={
                'password': 'admin_password'
            })
            
            # Verify response
            self.assertEqual(response.status_code, 200)
            data = response.get_json()
            self.assertIn('message', data)
            self.assertEqual(data['message'], 'Instance restarted successfully')
    
    @patch('app.restart_instance_container')
    @patch('app.save_instances')
    @patch('app.load_instances')
    def test_restart_with_instance_password(self, mock_load_instances, mock_save_instances, 
                                           mock_restart):
        """Test restart with instance password"""
        # Create instance with password
        instance_password_hash = app.hash_password('instance_password')
        
        mock_load_instances.return_value = {
            'Test Instance': {
                'container_id': 'test_container_id',
                'port': 8123,
                'status': 'running',
                'instance_password_hash': instance_password_hash
            }
        }
        mock_restart.return_value = (True, 'Instance restarted successfully')
        
        # Test restart with instance password
        with app.app.test_client() as client:
            response = client.post('/api/instances/Test Instance/restart', json={
                'password': 'instance_password'
            })
            
            # Verify response
            self.assertEqual(response.status_code, 200)
            data = response.get_json()
            self.assertIn('message', data)
    
    @patch('app.load_instances')
    def test_restart_with_wrong_password(self, mock_load_instances):
        """Test restart with wrong password"""
        instance_password_hash = app.hash_password('correct_password')
        
        mock_load_instances.return_value = {
            'Test Instance': {
                'container_id': 'test_container_id',
                'port': 8123,
                'status': 'running',
                'instance_password_hash': instance_password_hash
            }
        }
        
        # Test restart with wrong password
        with app.app.test_client() as client:
            response = client.post('/api/instances/Test Instance/restart', json={
                'password': 'wrong_password'
            })
            
            # Verify response is 401 unauthorized
            self.assertEqual(response.status_code, 401)
            data = response.get_json()
            self.assertIn('error', data)


if __name__ == '__main__':
    print("Testing instance password and restart functionality...\n")
    
    # Run tests
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromModule(sys.modules[__name__])
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Exit with appropriate code
    sys.exit(0 if result.wasSuccessful() else 1)
