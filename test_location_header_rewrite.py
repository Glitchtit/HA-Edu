#!/usr/bin/env python3
"""
Test to verify Location header rewriting for redirect compatibility with Cloudflare tunnel
"""

import sys
import os
import json
from unittest.mock import Mock, patch, MagicMock
import tempfile

# Add the parent directory to the path to import app
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_location_header_rewrite():
    """Test that Location headers in redirects are rewritten to include proxy prefix"""
    
    # Create a temporary data file using mkstemp for better cleanup
    fd, temp_data_file = tempfile.mkstemp(suffix='.json', text=True)
    
    try:
        # Write the test data
        with os.fdopen(fd, 'w') as f:
            json.dump({
                'instances': {
                    'test-instance': {
                        'container_id': 'abc123',
                        'container_name': 'ha-edu-test-instance',
                        'port': 8123,
                        'created_at': '2025-01-01T00:00:00',
                        'status': 'running'
                    }
                },
                'settings': {'instance_creation_enabled': True}
            }, f)
        
        # Set environment variable for data file
        os.environ['DATA_FILE'] = temp_data_file
        
        # Import app after setting environment variable
        import app
        
        # Create a test client
        with app.app.test_client() as client:
            # Mock the requests.get to simulate a redirect response from Home Assistant
            with patch('app.requests.get') as mock_get:
                # Create a mock response with a redirect
                mock_response = Mock()
                mock_response.status_code = 302
                mock_response.headers = {
                    'Location': '/lovelace',
                    'Content-Type': 'text/html'
                }
                mock_response.iter_content = Mock(return_value=iter([]))
                mock_get.return_value = mock_response
                
                # Make a request to the proxy endpoint
                response = client.get('/proxy/8123/')
                
                # Check that the Location header was rewritten
                location_header = response.headers.get('Location')
                assert location_header is not None, "Location header should be present in redirect response"
                assert location_header == '/proxy/8123/lovelace', \
                    f"Location header should be rewritten to include proxy prefix. Got: {location_header}"
                
                print(f"✓ Location header correctly rewritten: {location_header}")
                
            # Test with root redirect
            with patch('app.requests.get') as mock_get:
                mock_response = Mock()
                mock_response.status_code = 301
                mock_response.headers = {
                    'Location': '/',
                    'Content-Type': 'text/html'
                }
                mock_response.iter_content = Mock(return_value=iter([]))
                mock_get.return_value = mock_response
                
                response = client.get('/proxy/8123/some/path')
                
                location_header = response.headers.get('Location')
                assert location_header == '/proxy/8123/', \
                    f"Root redirect should be rewritten. Got: {location_header}"
                
                print(f"✓ Root redirect correctly rewritten: {location_header}")
            
            # Test with absolute URL (should not be rewritten)
            with patch('app.requests.get') as mock_get:
                mock_response = Mock()
                mock_response.status_code = 302
                mock_response.headers = {
                    'Location': 'https://example.com/login',
                    'Content-Type': 'text/html'
                }
                mock_response.iter_content = Mock(return_value=iter([]))
                mock_get.return_value = mock_response
                
                response = client.get('/proxy/8123/')
                
                location_header = response.headers.get('Location')
                assert location_header == 'https://example.com/login', \
                    f"Absolute URL should not be rewritten. Got: {location_header}"
                
                print(f"✓ Absolute URL not rewritten: {location_header}")
            
            # Test with absolute URL without explicit port (should not be rewritten)
            # URLs without explicit ports have parsed.port = None, which are intentionally excluded
            # from rewriting to avoid false positives with standard web services
            with patch('app.requests.get') as mock_get:
                mock_response = Mock()
                mock_response.status_code = 302
                mock_response.headers = {
                    'Location': 'http://localhost/',
                    'Content-Type': 'text/html'
                }
                mock_response.iter_content = Mock(return_value=iter([]))
                mock_get.return_value = mock_response
                
                response = client.get('/proxy/8123/')
                
                location_header = response.headers.get('Location')
                assert location_header == 'http://localhost/', \
                    f"Absolute URL without port should not be rewritten. Got: {location_header}"
                
                print(f"✓ Absolute URL without port not rewritten: {location_header}")
            
            # Test with already-prefixed path (should not be double-prefixed)
            with patch('app.requests.get') as mock_get:
                mock_response = Mock()
                mock_response.status_code = 302
                mock_response.headers = {
                    'Location': '/proxy/8123/lovelace',
                    'Content-Type': 'text/html'
                }
                mock_response.iter_content = Mock(return_value=iter([]))
                mock_get.return_value = mock_response
                
                response = client.get('/proxy/8123/')
                
                location_header = response.headers.get('Location')
                assert location_header == '/proxy/8123/lovelace', \
                    f"Already-prefixed path should not be double-prefixed. Got: {location_header}"
                
                print(f"✓ Already-prefixed path not double-prefixed: {location_header}")
            
            # Test with absolute URL to backend instance (should be rewritten)
            with patch('app.requests.get') as mock_get:
                mock_response = Mock()
                mock_response.status_code = 302
                mock_response.headers = {
                    'Location': 'http://192.168.50.111:8123/',
                    'Content-Type': 'text/html'
                }
                mock_response.iter_content = Mock(return_value=iter([]))
                mock_get.return_value = mock_response
                
                response = client.get('/proxy/8123/')
                
                location_header = response.headers.get('Location')
                assert location_header == '/proxy/8123/', \
                    f"Absolute URL to backend should be rewritten. Got: {location_header}"
                
                print(f"✓ Absolute backend URL correctly rewritten: {location_header}")
            
            # Test with absolute URL to backend with path
            with patch('app.requests.get') as mock_get:
                mock_response = Mock()
                mock_response.status_code = 302
                mock_response.headers = {
                    'Location': 'http://192.168.50.111:8123/lovelace',
                    'Content-Type': 'text/html'
                }
                mock_response.iter_content = Mock(return_value=iter([]))
                mock_get.return_value = mock_response
                
                response = client.get('/proxy/8123/')
                
                location_header = response.headers.get('Location')
                assert location_header == '/proxy/8123/lovelace', \
                    f"Absolute backend URL with path should be rewritten. Got: {location_header}"
                
                print(f"✓ Absolute backend URL with path correctly rewritten: {location_header}")
            
            # Test with absolute URL to localhost backend
            with patch('app.requests.get') as mock_get:
                mock_response = Mock()
                mock_response.status_code = 302
                mock_response.headers = {
                    'Location': 'http://localhost:8123/config',
                    'Content-Type': 'text/html'
                }
                mock_response.iter_content = Mock(return_value=iter([]))
                mock_get.return_value = mock_response
                
                response = client.get('/proxy/8123/')
                
                location_header = response.headers.get('Location')
                assert location_header == '/proxy/8123/config', \
                    f"Absolute localhost URL should be rewritten. Got: {location_header}"
                
                print(f"✓ Absolute localhost URL correctly rewritten: {location_header}")
            
            # Test with absolute URL to backend with query string
            with patch('app.requests.get') as mock_get:
                mock_response = Mock()
                mock_response.status_code = 302
                mock_response.headers = {
                    'Location': 'http://192.168.50.111:8123/auth/authorize?client_id=test',
                    'Content-Type': 'text/html'
                }
                mock_response.iter_content = Mock(return_value=iter([]))
                mock_get.return_value = mock_response
                
                response = client.get('/proxy/8123/')
                
                location_header = response.headers.get('Location')
                assert location_header == '/proxy/8123/auth/authorize?client_id=test', \
                    f"Absolute backend URL with query string should be rewritten. Got: {location_header}"
                
                print(f"✓ Absolute backend URL with query string correctly rewritten: {location_header}")
            
            # Test with external URL on same port (should NOT be rewritten)
            with patch('app.requests.get') as mock_get:
                mock_response = Mock()
                mock_response.status_code = 302
                mock_response.headers = {
                    'Location': 'http://external-service.com:8123/api',
                    'Content-Type': 'text/html'
                }
                mock_response.iter_content = Mock(return_value=iter([]))
                mock_get.return_value = mock_response
                
                response = client.get('/proxy/8123/')
                
                location_header = response.headers.get('Location')
                assert location_header == 'http://external-service.com:8123/api', \
                    f"External URL with same port should NOT be rewritten. Got: {location_header}"
                
                print(f"✓ External URL with same port not rewritten: {location_header}")
            
            print("\n✓ All Location header rewrite tests passed!")
            return True
    
    finally:
        # Clean up temp file
        if os.path.exists(temp_data_file):
            os.unlink(temp_data_file)


if __name__ == '__main__':
    test_location_header_rewrite()
