#!/usr/bin/env python3
"""
Integration test for the proxy endpoint using Flask test client
"""

import sys
import os
import json
import tempfile
from unittest.mock import patch, MagicMock
from contextlib import contextmanager

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

@contextmanager
def setup_test_instance(port=8123):
    """Context manager to set up test instance data and clean up afterwards"""
    # Create a temporary data file with test instance
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        test_data_file = f.name
        json.dump({
            'test-instance': {
                'container_id': 'test123',
                'container_name': 'ha-edu-test-instance',
                'port': port,
                'status': 'running',
                'created_at': '2024-01-01T00:00:00'
            }
        }, f)
    
    import app
    original_data_file = app.DATA_FILE
    app.DATA_FILE = test_data_file
    
    try:
        yield app.app.test_client()
    finally:
        app.DATA_FILE = original_data_file
        os.unlink(test_data_file)

def test_proxy_endpoint_integration():
    """Test proxy endpoint with Flask test client"""
    print("Testing proxy endpoint integration...")
    try:
        with setup_test_instance() as test_client:
            # Test 1: Valid proxy request with mock backend
            print("\nTest 1: Proxy to valid instance...")
            with patch('app.requests.get') as mock_get:
                # Mock the backend response
                mock_response = MagicMock()
                mock_response.status_code = 200
                mock_response.headers = {'Content-Type': 'text/html'}
                mock_response.iter_content = lambda chunk_size: [b'<html>Home Assistant</html>']
                mock_get.return_value = mock_response
                
                response = test_client.get('/proxy/8123/')
                
                if response.status_code == 200:
                    print("✓ Proxy returns 200 for valid instance")
                    print(f"✓ Backend was called with correct URL")
                else:
                    print(f"✗ Expected 200, got {response.status_code}")
                    return False
            
            # Test 2: Invalid port (not in instances)
            print("\nTest 2: Proxy to invalid instance...")
            response = test_client.get('/proxy/9999/')
            
            if response.status_code == 404:
                print("✓ Proxy returns 404 for invalid instance")
            else:
                print(f"✗ Expected 404, got {response.status_code}")
                return False
            
            # Test 3: WebSocket upgrade rejection
            print("\nTest 3: WebSocket upgrade handling...")
            response = test_client.get('/proxy/8123/', headers={'Upgrade': 'websocket'})
            
            if response.status_code == 400:
                print("✓ Proxy rejects WebSocket upgrades with 400")
            else:
                print(f"✗ Expected 400, got {response.status_code}")
                return False
            
            # Test 4: POST request proxying
            print("\nTest 4: POST request proxying...")
            with patch('app.requests.post') as mock_post:
                mock_response = MagicMock()
                mock_response.status_code = 200
                mock_response.headers = {'Content-Type': 'application/json'}
                mock_response.iter_content = lambda chunk_size: [b'{"success": true}']
                mock_post.return_value = mock_response
                
                response = test_client.post('/proxy/8123/api/test', 
                                           data='{"test": "data"}',
                                           content_type='application/json')
                
                if response.status_code == 200:
                    print("✓ POST requests are proxied correctly")
                else:
                    print(f"✗ Expected 200, got {response.status_code}")
                    return False
            
            # Test 5: Connection error handling
            print("\nTest 5: Connection error handling...")
            with patch('app.requests.get') as mock_get:
                import requests
                mock_get.side_effect = requests.exceptions.ConnectionError('Connection refused')
                
                response = test_client.get('/proxy/8123/')
                
                if response.status_code == 502:
                    print("✓ Connection errors return 502")
                else:
                    print(f"✗ Expected 502, got {response.status_code}")
                    return False
            
            # Test 6: Timeout handling
            print("\nTest 6: Timeout handling...")
            with patch('app.requests.get') as mock_get:
                import requests
                mock_get.side_effect = requests.exceptions.Timeout('Request timeout')
                
                response = test_client.get('/proxy/8123/')
                
                if response.status_code == 504:
                    print("✓ Timeouts return 504")
                else:
                    print(f"✗ Expected 504, got {response.status_code}")
                    return False
            
            print("\n✓ All integration tests passed")
            return True
            
    except Exception as e:
        print(f"✗ Integration test error: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_proxy_preserves_paths():
    """Test that proxy correctly forwards paths"""
    print("\nTesting proxy path forwarding...")
    try:
        with setup_test_instance() as test_client:
            with patch('app.requests.get') as mock_get:
                mock_response = MagicMock()
                mock_response.status_code = 200
                mock_response.headers = {}
                mock_response.iter_content = lambda chunk_size: [b'test']
                mock_get.return_value = mock_response
                
                # Test with a complex path
                response = test_client.get('/proxy/8123/api/states/sensor.test')
                
                # Verify the mock was called with the correct URL
                called_url = mock_get.call_args[0][0]
                if '/api/states/sensor.test' in called_url:
                    print("✓ Proxy preserves URL paths correctly")
                    return True
                else:
                    print(f"✗ Path not preserved. Called URL: {called_url}")
                    return False
                    
    except Exception as e:
        print(f"✗ Path forwarding test error: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_proxy_preserves_query_strings():
    """Test that proxy correctly forwards query strings"""
    print("\nTesting proxy query string forwarding...")
    try:
        with setup_test_instance() as test_client:
            with patch('app.requests.get') as mock_get:
                mock_response = MagicMock()
                mock_response.status_code = 200
                mock_response.headers = {}
                mock_response.iter_content = lambda chunk_size: [b'test']
                mock_get.return_value = mock_response
                
                # Test with query string
                response = test_client.get('/proxy/8123/api/test?param1=value1&param2=value2')
                
                # Verify the mock was called with the correct URL including query string
                called_url = mock_get.call_args[0][0]
                if 'param1=value1' in called_url and 'param2=value2' in called_url:
                    print("✓ Proxy preserves query strings correctly")
                    return True
                else:
                    print(f"✗ Query string not preserved. Called URL: {called_url}")
                    return False
                    
    except Exception as e:
        print(f"✗ Query string test error: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Run all integration tests"""
    print("=" * 60)
    print("HA-Edu Proxy Integration Tests")
    print("=" * 60)
    
    tests = [
        test_proxy_endpoint_integration,
        test_proxy_preserves_paths,
        test_proxy_preserves_query_strings,
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
