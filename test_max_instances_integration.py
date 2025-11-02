#!/usr/bin/env python3
"""
Integration test to verify MAX_INSTANCES works end-to-end
"""

import sys
import os
import json
import tempfile

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_integration():
    """Test the MAX_INSTANCES feature end-to-end"""
    print("=" * 60)
    print("MAX_INSTANCES Integration Test")
    print("=" * 60)
    
    # Set up environment
    os.environ['MAX_INSTANCES'] = '2'
    os.environ.pop('ADMIN_PASSWORD', None)
    os.environ.pop('ADMINS', None)
    
    # Create a temporary data file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        temp_file = f.name
        json.dump({'instances': {}, 'settings': {'instance_creation_enabled': True}}, f)
    
    os.environ['DATA_FILE'] = temp_file
    
    try:
        # Import app
        if 'app' in sys.modules:
            del sys.modules['app']
        import app
        import importlib
        importlib.reload(app)
        
        print(f"\n✓ MAX_INSTANCES set to: {app.MAX_INSTANCES}")
        
        # Create a test client
        app.app.config['TESTING'] = True
        client = app.app.test_client()
        
        # Test 1: Check homepage loads
        print("\nTest 1: Homepage loads correctly")
        response = client.get('/')
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print("✓ Homepage loads successfully")
        
        # Test 2: Non-admin user can create first instance
        print("\nTest 2: Non-admin user can create first instance")
        response = client.post('/api/instances', 
                             json={'server_name': 'Test-Instance-1'},
                             environ_base={'REMOTE_ADDR': '1.2.3.4'})
        print(f"Response status: {response.status_code}")
        print(f"Response data: {response.get_json()}")
        # Note: This will fail if Docker is not available, but we check the logic
        # The important part is that it doesn't fail with a limit error
        if response.status_code == 201:
            print("✓ First instance created successfully")
        elif response.status_code == 500:
            # Docker not available, but no limit error
            data = response.get_json()
            if 'maximum limit' not in data.get('error', '').lower():
                print("✓ No limit error (Docker not available in test environment)")
            else:
                print(f"✗ Unexpected limit error: {data}")
                return False
        else:
            data = response.get_json()
            if 'maximum limit' not in data.get('error', '').lower():
                print(f"✓ No limit error (status: {response.status_code})")
            else:
                print(f"✗ Unexpected limit error: {data}")
                return False
        
        # Test 3: Check that limit validation is in place
        print("\nTest 3: Server-side limit validation exists")
        # Manually add 2 instances to the data file to simulate reaching limit
        with open(temp_file, 'r') as f:
            data = json.load(f)
        data['instances'] = {
            'test1': {'created_by': 'IP: 1.2.3.4', 'port': 8123, 'container_id': 'abc123', 'container_name': 'test1'},
            'test2': {'created_by': 'IP: 1.2.3.4', 'port': 8124, 'container_id': 'def456', 'container_name': 'test2'}
        }
        with open(temp_file, 'w') as f:
            json.dump(data, f)
        
        # Try to create third instance (should be blocked)
        response = client.post('/api/instances',
                             json={'server_name': 'Test-Instance-3'},
                             environ_base={'REMOTE_ADDR': '1.2.3.4'})
        print(f"Response status: {response.status_code}")
        response_data = response.get_json()
        print(f"Response data: {response_data}")
        
        if response.status_code == 403 and 'maximum limit' in response_data.get('error', '').lower():
            print("✓ Third instance creation blocked by server-side validation")
        else:
            print(f"✗ Expected 403 with limit error, got {response.status_code}: {response_data}")
            return False
        
        # Test 4: Different user can still create instances
        print("\nTest 4: Different user can create instances")
        response = client.post('/api/instances',
                             json={'server_name': 'Test-Instance-Other-User'},
                             environ_base={'REMOTE_ADDR': '5.6.7.8'})
        print(f"Response status: {response.status_code}")
        response_data = response.get_json()
        
        # Should not be blocked by limit (different user)
        if response.status_code == 403 and 'maximum limit' in response_data.get('error', '').lower():
            print(f"✗ Different user blocked by limit: {response_data}")
            return False
        else:
            print("✓ Different user not blocked by limit")
        
        # Test 5: Admin user (local IP) is not limited
        print("\nTest 5: Admin user can bypass limits")
        response = client.post('/api/instances',
                             json={'server_name': 'Test-Instance-Admin'},
                             environ_base={'REMOTE_ADDR': '192.168.50.10'})
        print(f"Response status: {response.status_code}")
        response_data = response.get_json()
        
        # Should not be blocked by limit (admin)
        if response.status_code == 403 and 'maximum limit' in response_data.get('error', '').lower():
            print(f"✗ Admin blocked by limit: {response_data}")
            return False
        else:
            print("✓ Admin not blocked by limit")
        
        # Test 6: Unlimited mode (MAX_INSTANCES = 0)
        print("\nTest 6: Unlimited mode (MAX_INSTANCES = 0)")
        os.environ['MAX_INSTANCES'] = '0'
        if 'app' in sys.modules:
            del sys.modules['app']
        import app as app_unlimited
        importlib.reload(app_unlimited)
        
        app_unlimited.app.config['TESTING'] = True
        client_unlimited = app_unlimited.app.test_client()
        
        response = client_unlimited.post('/api/instances',
                                       json={'server_name': 'Test-Unlimited'},
                                       environ_base={'REMOTE_ADDR': '1.2.3.4'})
        response_data = response.get_json()
        
        # Should not be blocked by limit (unlimited mode)
        if response.status_code == 403 and 'maximum limit' in response_data.get('error', '').lower():
            print(f"✗ User blocked by limit in unlimited mode: {response_data}")
            return False
        else:
            print("✓ Unlimited mode allows all users to create instances")
        
        print("\n" + "=" * 60)
        print("All Integration Tests Passed!")
        print("=" * 60)
        return True
        
    except Exception as e:
        print(f"\n✗ Integration test error: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        # Clean up
        os.remove(temp_file)

if __name__ == '__main__':
    success = test_integration()
    sys.exit(0 if success else 1)
