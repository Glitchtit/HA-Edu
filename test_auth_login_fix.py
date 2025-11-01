#!/usr/bin/env python3
"""
Test to verify the fix for the admin login error

This test verifies that POST requests to /auth/login_flow/* work correctly
without X-Forwarded-Prefix and X-Ingress-Path headers which were causing
500 errors in Home Assistant's authentication system.
"""

import sys
import os
import json
import tempfile
from unittest.mock import patch, MagicMock

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_auth_login_flow_headers():
    """Test that auth login flow POST requests don't include problematic headers"""
    print("Testing auth/login_flow POST request headers...")
    
    # Create a temporary data file with test instance
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        test_data_file = f.name
        json.dump({
            'instances': {
                'test-instance': {
                    'container_id': 'test123',
                    'container_name': 'ha-edu-test-instance',
                    'port': 8124,
                    'status': 'running',
                    'created_at': '2024-01-01T00:00:00'
                }
            },
            'settings': {'instance_creation_enabled': True}
        }, f)
    
    import app
    original_data_file = app.DATA_FILE
    app.DATA_FILE = test_data_file
    
    try:
        test_client = app.app.test_client()
        
        # Mock the backend response
        with patch('app.requests.post') as mock_post:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.headers = {'Content-Type': 'application/json'}
            mock_response.iter_content = lambda chunk_size: [b'{"type": "success"}']
            mock_post.return_value = mock_response
            
            # Simulate a login flow POST request
            post_data = json.dumps({
                "client_id": "http://localhost:5000/",
                "username": "admin",
                "password": "test123"
            })
            
            response = test_client.post(
                '/proxy/8124/auth/login_flow/10f8947f795d4adb12d8bcaa2a190455',
                data=post_data,
                content_type='application/json',
                headers={
                    'Origin': 'http://localhost:5000',
                    'Referer': 'http://localhost:5000/proxy/8124/'
                }
            )
            
            if not mock_post.called:
                print("✗ Backend was not called")
                return False
            
            # Get the headers that were sent to the backend
            call_args = mock_post.call_args
            sent_headers = call_args[1]['headers']
            
            print(f"Response status: {response.status_code}")
            
            # Verify that required headers are present
            required_headers = ['X-Forwarded-For', 'X-Forwarded-Proto', 'X-Forwarded-Host']
            for header in required_headers:
                if header in sent_headers:
                    print(f"✓ {header} header present: {sent_headers[header]}")
                else:
                    print(f"✗ {header} header missing")
                    return False
            
            # Verify that problematic headers are NOT present
            problematic_headers = ['X-Forwarded-Prefix', 'X-Ingress-Path']
            for header in problematic_headers:
                if header in sent_headers:
                    print(f"✗ {header} header should NOT be present but was: {sent_headers[header]}")
                    return False
                else:
                    print(f"✓ {header} header correctly omitted")
            
            # Verify Content-Type and Content-Length are preserved
            if 'Content-Type' in sent_headers and sent_headers['Content-Type'] == 'application/json':
                print(f"✓ Content-Type preserved correctly")
            else:
                print(f"✗ Content-Type not preserved correctly")
                return False
            
            sent_data = call_args[1]['data']
            if 'Content-Length' in sent_headers:
                expected_length = len(sent_data) if sent_data else 0
                actual_length = int(sent_headers['Content-Length'])
                if expected_length == actual_length:
                    print(f"✓ Content-Length matches data: {actual_length} bytes")
                else:
                    print(f"✗ Content-Length mismatch: header={actual_length}, data={expected_length}")
                    return False
            
            print("✓ All auth/login_flow header checks passed")
            return True
            
    except Exception as e:
        print(f"✗ Test error: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        app.DATA_FILE = original_data_file
        os.unlink(test_data_file)

def test_other_endpoints_unaffected():
    """Test that other endpoints still work correctly after the fix"""
    print("\nTesting that other endpoints are unaffected...")
    
    # Create a temporary data file with test instance
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        test_data_file = f.name
        json.dump({
            'instances': {
                'test-instance': {
                    'container_id': 'test123',
                    'container_name': 'ha-edu-test-instance',
                    'port': 8123,
                    'status': 'running',
                    'created_at': '2024-01-01T00:00:00'
                }
            },
            'settings': {'instance_creation_enabled': True}
        }, f)
    
    import app
    original_data_file = app.DATA_FILE
    app.DATA_FILE = test_data_file
    
    try:
        test_client = app.app.test_client()
        
        # Test GET request to API endpoint
        with patch('app.requests.get') as mock_get:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.headers = {'Content-Type': 'application/json'}
            mock_response.iter_content = lambda chunk_size: [b'{"state": "on"}']
            mock_get.return_value = mock_response
            
            response = test_client.get('/proxy/8123/api/states/light.bedroom')
            
            if response.status_code == 200:
                print("✓ GET requests still work correctly")
            else:
                print(f"✗ GET request failed with status {response.status_code}")
                return False
        
        # Test POST request to API endpoint
        with patch('app.requests.post') as mock_post:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.headers = {'Content-Type': 'application/json'}
            mock_response.iter_content = lambda chunk_size: [b'{"success": true}']
            mock_post.return_value = mock_response
            
            response = test_client.post(
                '/proxy/8123/api/services/light/turn_on',
                data=json.dumps({"entity_id": "light.bedroom"}),
                content_type='application/json'
            )
            
            if response.status_code == 200:
                print("✓ POST requests to other endpoints still work correctly")
            else:
                print(f"✗ POST request failed with status {response.status_code}")
                return False
        
        print("✓ All other endpoints unaffected")
        return True
        
    except Exception as e:
        print(f"✗ Test error: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        app.DATA_FILE = original_data_file
        os.unlink(test_data_file)

def main():
    """Run all tests"""
    print("=" * 60)
    print("HA-Edu Auth Login Fix Tests")
    print("=" * 60)
    
    tests = [
        test_auth_login_flow_headers,
        test_other_endpoints_unaffected,
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
        print("\n✓ All auth login fix tests passed!")
        return 0
    else:
        print("\n✗ Some tests failed")
        return 1

if __name__ == '__main__':
    sys.exit(main())
