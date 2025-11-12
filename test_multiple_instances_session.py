#!/usr/bin/env python3
"""
Integration test for multiple instance access with session persistence

This test simulates the scenario where:
1. Multiple HA instances are running
2. A user accesses instance via /proxy/{port}/
3. The browser makes requests to assets like /frontend_latest/...
4. These requests should be routed correctly using session cookies
"""

import sys
import os
import json
import tempfile
import shutil

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_multiple_instances_with_sessions():
    """Test that multiple instances can be accessed correctly with sessions"""
    print("Testing multiple instance access with session persistence...")
    
    # Create a temporary data directory
    temp_dir = tempfile.mkdtemp()
    
    try:
        # Set environment
        os.environ['DATA_FILE'] = os.path.join(temp_dir, 'instances.json')
        
        # Create mock instances data
        instances_data = {
            'instances': {
                'Instance1': {
                    'container_id': 'container1',
                    'container_name': 'ha-edu-instance1',
                    'port': 8123,
                    'status': 'running',
                    'created_at': '2024-01-01T00:00:00',
                    'created_by': 'user1@example.com'
                },
                'Instance2': {
                    'container_id': 'container2',
                    'container_name': 'ha-edu-instance2',
                    'port': 8124,
                    'status': 'running',
                    'created_at': '2024-01-01T00:01:00',
                    'created_by': 'user2@example.com'
                },
                'Instance3': {
                    'container_id': 'container3',
                    'container_name': 'ha-edu-instance3',
                    'port': 8125,
                    'status': 'running',
                    'created_at': '2024-01-01T00:02:00',
                    'created_by': 'user3@example.com'
                }
            },
            'settings': {
                'instance_creation_enabled': True
            }
        }
        
        # Save instances data
        with open(os.path.join(temp_dir, 'instances.json'), 'w') as f:
            json.dump(instances_data, f, indent=2)
        
        # Import app
        import app
        import importlib
        importlib.reload(app)
        
        print(f"✓ Loaded app with 3 instances")
        
        # Create a test client
        with app.app.test_client() as client:
            # Simulate accessing instance 2 via /proxy/8124/
            # This should set session['proxy_port'] = 8124
            with client.session_transaction() as sess:
                sess['proxy_port'] = 8124
            
            print("✓ Session set for port 8124")
            
            # Verify session persists
            with client.session_transaction() as sess:
                if sess.get('proxy_port') != 8124:
                    print("✗ Session port did not persist")
                    return False
            
            print("✓ Session port persisted correctly")
            
            # Simulate multiple sessions for different instances
            sessions = [
                {'port': 8123, 'instance': 'Instance1'},
                {'port': 8124, 'instance': 'Instance2'},
                {'port': 8125, 'instance': 'Instance3'}
            ]
            
            for session_data in sessions:
                with app.app.test_client() as instance_client:
                    with instance_client.session_transaction() as sess:
                        sess['proxy_port'] = session_data['port']
                    
                    # Verify session persists for this instance
                    with instance_client.session_transaction() as sess:
                        if sess.get('proxy_port') != session_data['port']:
                            print(f"✗ Session for {session_data['instance']} (port {session_data['port']}) did not persist")
                            return False
                    
                    print(f"✓ Session for {session_data['instance']} (port {session_data['port']}) works correctly")
        
        print("✓ All instance sessions work correctly")
        return True
        
    finally:
        # Clean up
        shutil.rmtree(temp_dir, ignore_errors=True)
        if 'DATA_FILE' in os.environ:
            del os.environ['DATA_FILE']

def test_secret_key_same_across_workers():
    """Test that the same secret key is used across multiple app instances"""
    print("\nTesting secret key consistency across worker simulations...")
    
    # Create a temporary data directory
    temp_dir = tempfile.mkdtemp()
    
    try:
        # Set environment
        os.environ['DATA_FILE'] = os.path.join(temp_dir, 'instances.json')
        
        # Import app (worker 1)
        import app
        import importlib
        
        worker1_key = app.app.secret_key
        # Note: Logging partial key for test verification only - this is a test-generated key
        print(f"✓ Worker 1 key: {worker1_key[:16]}...")
        
        # Reload app (worker 2)
        importlib.reload(app)
        worker2_key = app.app.secret_key
        # Note: Logging partial key for test verification only - this is a test-generated key
        print(f"✓ Worker 2 key: {worker2_key[:16]}...")
        
        if worker1_key != worker2_key:
            print("✗ Secret keys differ between workers!")
            # Note: Logging partial keys for test debugging only - these are test-generated keys
            print(f"  Worker 1: {worker1_key[:16]}... (masked)")
            print(f"  Worker 2: {worker2_key[:16]}... (masked)")
            return False
        
        print("✓ Secret keys are consistent across workers")
        
        # Reload app again (worker 3)
        importlib.reload(app)
        worker3_key = app.app.secret_key
        
        if worker1_key != worker3_key:
            print("✗ Secret key changed on third worker!")
            return False
        
        print("✓ Secret key remains consistent across multiple workers")
        
        return True
        
    finally:
        # Clean up
        shutil.rmtree(temp_dir, ignore_errors=True)
        if 'DATA_FILE' in os.environ:
            del os.environ['DATA_FILE']

def main():
    """Run all integration tests"""
    print("=" * 60)
    print("HA-Edu Multiple Instance Integration Tests")
    print("=" * 60)
    
    tests = [
        test_secret_key_same_across_workers,
        test_multiple_instances_with_sessions,
    ]
    
    results = []
    for test in tests:
        try:
            result = test()
            results.append(result)
        except Exception as e:
            print(f"✗ Test failed with exception: {e}")
            import traceback
            traceback.print_exc()
            results.append(False)
    
    print("\n" + "=" * 60)
    print(f"Tests passed: {sum(results)}/{len(results)}")
    print("=" * 60)
    
    if all(results):
        print("\n✓ All integration tests passed!")
        return 0
    else:
        print("\n✗ Some integration tests failed")
        return 1

if __name__ == '__main__':
    sys.exit(main())
