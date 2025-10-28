#!/usr/bin/env python3
"""
Test to verify the status field shows actual container state
"""

import sys
import os
import json
import tempfile
from unittest.mock import Mock, patch, MagicMock

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_get_instances_updates_status():
    """Test that get_instances endpoint updates status from Docker"""
    print("Testing get_instances status update...")
    print("=" * 60)
    
    try:
        # Create a Flask test client
        with patch('app.client') as mock_docker_client:
            import app
            
            # Create test instances file
            with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
                temp_file = f.name
                test_data = {
                    'test_server_1': {
                        'port': 8123,
                        'container_id': 'running_container',
                        'container_name': 'ha-edu-test-1',
                        'created_at': '2025-01-01T00:00:00',
                        'status': 'running'  # Static status
                    },
                    'test_server_2': {
                        'port': 8124,
                        'container_id': 'stopped_container',
                        'container_name': 'ha-edu-test-2',
                        'created_at': '2025-01-01T00:00:00',
                        'status': 'running'  # Static status, but container is actually stopped
                    },
                    'test_server_3': {
                        'port': 8125,
                        'container_id': 'removed_container',
                        'container_name': 'ha-edu-test-3',
                        'created_at': '2025-01-01T00:00:00',
                        'status': 'running'  # Static status, but container was removed
                    }
                }
                json.dump(test_data, f)
            
            # Override DATA_FILE
            old_data_file = app.DATA_FILE
            app.DATA_FILE = temp_file
            
            try:
                # Mock Docker containers
                mock_running = Mock()
                mock_running.status = 'running'
                
                mock_stopped = Mock()
                mock_stopped.status = 'exited'
                
                def get_container_side_effect(container_id):
                    if container_id == 'running_container':
                        return mock_running
                    elif container_id == 'stopped_container':
                        return mock_stopped
                    elif container_id == 'removed_container':
                        import docker.errors
                        raise docker.errors.NotFound('Container not found')
                    raise Exception('Unknown container')
                
                mock_docker_client.containers.get.side_effect = get_container_side_effect
                
                # Create test client
                app.app.testing = True
                with app.app.test_client() as client:
                    # Call the API endpoint
                    response = client.get('/api/instances')
                    
                    assert response.status_code == 200, f"Expected 200, got {response.status_code}"
                    
                    data = response.get_json()
                    
                    # Verify status was updated from Docker
                    print("\n1. Checking running container status...")
                    assert 'test_server_1' in data, "test_server_1 not found"
                    assert data['test_server_1']['status'] == 'running', \
                        f"Expected 'running', got '{data['test_server_1']['status']}'"
                    print(f"   ✓ test_server_1 status: {data['test_server_1']['status']}")
                    
                    print("\n2. Checking stopped container status...")
                    assert 'test_server_2' in data, "test_server_2 not found"
                    assert data['test_server_2']['status'] == 'exited', \
                        f"Expected 'exited', got '{data['test_server_2']['status']}'"
                    print(f"   ✓ test_server_2 status: {data['test_server_2']['status']}")
                    
                    print("\n3. Checking removed container status...")
                    assert 'test_server_3' in data, "test_server_3 not found"
                    assert data['test_server_3']['status'] == 'removed', \
                        f"Expected 'removed', got '{data['test_server_3']['status']}'"
                    print(f"   ✓ test_server_3 status: {data['test_server_3']['status']}")
                    
                    print("\n" + "=" * 60)
                    print("✓ All status field tests passed!")
                    print("=" * 60)
                    return True
                    
            finally:
                # Restore and cleanup
                app.DATA_FILE = old_data_file
                try:
                    if os.path.exists(temp_file):
                        os.unlink(temp_file)
                except Exception:
                    pass
    
    except Exception as e:
        print(f"\n✗ Status field test failed with error: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Run status field test"""
    print("\n" + "=" * 60)
    print("Status Field Test - Real-time Container Status")
    print("=" * 60)
    print("\nThis test verifies that the status field shows the actual")
    print("container state from Docker, not just the static JSON value.\n")
    
    success = test_get_instances_updates_status()
    
    if success:
        print("\n✓ Status field test completed successfully!")
        print("\nThe fix ensures that:")
        print("1. Status is fetched from Docker in real-time")
        print("2. Stopped containers show 'exited' status")
        print("3. Removed containers show 'removed' status")
        print("4. Running containers show 'running' status")
        return 0
    else:
        print("\n✗ Status field test failed!")
        return 1

if __name__ == '__main__':
    sys.exit(main())
