#!/usr/bin/env python3
"""
Test script for HTML rewriting functionality in the proxy
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
            'instances': {
                'test-instance': {
                    'container_id': 'test123',
                    'container_name': 'ha-edu-test-instance',
                    'port': port,
                    'status': 'running',
                    'created_at': '2024-01-01T00:00:00'
                }
            },
            'settings': {
                'instance_creation_enabled': True
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

def test_html_base_tag_injection():
    """Test that base tag is correctly injected into HTML responses"""
    print("Testing HTML base tag injection...")
    try:
        with setup_test_instance() as test_client:
            with patch('app.requests.get') as mock_get:
                # Mock an HTML response from Home Assistant
                mock_response = MagicMock()
                mock_response.status_code = 200
                mock_response.headers = {'Content-Type': 'text/html; charset=utf-8'}
                
                # Sample HTML that looks like what Home Assistant might return
                sample_html = b'''<!DOCTYPE html>
<html>
<head>
    <title>Home Assistant</title>
    <link rel="stylesheet" href="/static/css/main.css">
</head>
<body>
    <script src="/frontend_latest/app.js"></script>
</body>
</html>'''
                mock_response.content = sample_html
                mock_response.iter_content = lambda chunk_size: [sample_html]
                mock_get.return_value = mock_response
                
                # Make a request through the proxy
                response = test_client.get('/proxy/8123/')
                
                if response.status_code != 200:
                    print(f"✗ Expected 200, got {response.status_code}")
                    return False
                
                # Check that the response contains the injected base tag
                response_html = response.data.decode('utf-8')
                
                if '<base href="/proxy/8123/">' in response_html:
                    print("✓ Base tag correctly injected into HTML")
                else:
                    print("✗ Base tag not found in response")
                    print(f"Response: {response_html[:500]}")
                    return False
                
                # Verify it's after the <head> tag
                head_pos = response_html.lower().find('<head>')
                base_pos = response_html.find('<base href="/proxy/8123/">')
                
                if head_pos >= 0 and base_pos > head_pos:
                    print("✓ Base tag positioned after <head> tag")
                    return True
                else:
                    print("✗ Base tag not properly positioned")
                    return False
                    
    except Exception as e:
        print(f"✗ HTML rewriting test error: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_non_html_not_rewritten():
    """Test that non-HTML content is not rewritten"""
    print("\nTesting that non-HTML content is not rewritten...")
    try:
        with setup_test_instance() as test_client:
            with patch('app.requests.get') as mock_get:
                # Mock a JSON response
                mock_response = MagicMock()
                mock_response.status_code = 200
                mock_response.headers = {'Content-Type': 'application/json'}
                json_data = b'{"status": "ok"}'
                mock_response.content = json_data
                mock_response.iter_content = lambda chunk_size: [json_data]
                mock_get.return_value = mock_response
                
                # Make a request through the proxy
                response = test_client.get('/proxy/8123/api/status')
                
                if response.status_code != 200:
                    print(f"✗ Expected 200, got {response.status_code}")
                    return False
                
                # Verify JSON is not modified
                if b'<base href' in response.data:
                    print("✗ Base tag incorrectly injected into JSON response")
                    return False
                
                if response.data == json_data:
                    print("✓ JSON response not modified")
                    return True
                else:
                    print("✗ JSON response was modified")
                    return False
                    
    except Exception as e:
        print(f"✗ Non-HTML test error: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_session_cookie_set():
    """Test that session cookie is set when accessing /proxy/{port}/"""
    print("\nTesting session cookie is set...")
    try:
        with setup_test_instance() as test_client:
            with patch('app.requests.get') as mock_get:
                mock_response = MagicMock()
                mock_response.status_code = 200
                mock_response.headers = {'Content-Type': 'text/html'}
                mock_response.content = b'<html><head></head><body>Test</body></html>'
                mock_response.iter_content = lambda chunk_size: [mock_response.content]
                mock_get.return_value = mock_response
                
                # Make a request to establish session
                with test_client.session_transaction() as sess:
                    # Session should be empty before request
                    if 'proxy_port' in sess:
                        print("✗ Session already contains proxy_port before request")
                        return False
                
                response = test_client.get('/proxy/8123/')
                
                # Check session after request
                with test_client.session_transaction() as sess:
                    if sess.get('proxy_port') == 8123:
                        print("✓ Session cookie correctly set to port 8123")
                        return True
                    else:
                        print(f"✗ Session proxy_port is {sess.get('proxy_port')}, expected 8123")
                        return False
                    
    except Exception as e:
        print(f"✗ Session cookie test error: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_fallback_uses_session():
    """Test that fallback routes use session cookie when referer is missing"""
    print("\nTesting fallback routes use session cookie...")
    try:
        with setup_test_instance() as test_client:
            with patch('app.requests.get') as mock_get:
                mock_response = MagicMock()
                mock_response.status_code = 200
                mock_response.headers = {'Content-Type': 'application/json'}
                json_data = b'{"test": "data"}'
                mock_response.content = json_data
                mock_response.iter_content = lambda chunk_size: [json_data]
                mock_get.return_value = mock_response
                
                # First, establish a session by accessing the main proxy URL
                with test_client.session_transaction() as sess:
                    sess['proxy_port'] = 8123
                
                # Now make a request to a fallback route without referer
                response = test_client.get('/api/test', headers={})
                
                if response.status_code == 200:
                    print("✓ Fallback route successfully used session cookie")
                    return True
                else:
                    print(f"✗ Expected 200, got {response.status_code}")
                    return False
                    
    except Exception as e:
        print(f"✗ Fallback session test error: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Run all HTML rewriting tests"""
    print("=" * 60)
    print("HA-Edu Proxy HTML Rewriting Tests")
    print("=" * 60)
    
    tests = [
        test_html_base_tag_injection,
        test_non_html_not_rewritten,
        test_session_cookie_set,
        test_fallback_uses_session,
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
        print("\n✓ All HTML rewriting tests passed!")
        return 0
    else:
        print("\n✗ Some HTML rewriting tests failed")
        return 1

if __name__ == '__main__':
    sys.exit(main())
