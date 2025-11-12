#!/usr/bin/env python3
"""
Test to verify DOCKER_HOST_IP configuration fix
This test confirms that the hardcoded IP has been replaced with a configurable variable
"""

import sys
import os

# Add the parent directory to the path to import app
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_docker_host_ip_configuration():
    """Test that DOCKER_HOST_IP is configurable and used in proxy code"""
    
    print("=" * 60)
    print("DOCKER_HOST_IP Configuration Tests")
    print("=" * 60)
    print()
    
    # Test 1: Verify DOCKER_HOST_IP is defined
    print("Test 1: Verifying DOCKER_HOST_IP is defined...")
    import app
    
    assert hasattr(app, 'DOCKER_HOST_IP'), "DOCKER_HOST_IP should be defined in app"
    print(f"✓ DOCKER_HOST_IP is defined: {app.DOCKER_HOST_IP}")
    
    # Test 2: Verify default value
    print("\nTest 2: Verifying default value...")
    # When no env var is set, it should default to host.docker.internal
    if 'DOCKER_HOST_IP' not in os.environ:
        assert app.DOCKER_HOST_IP == 'host.docker.internal', \
            f"Default value should be 'host.docker.internal', got: {app.DOCKER_HOST_IP}"
        print(f"✓ Default value is correct: {app.DOCKER_HOST_IP}")
    else:
        print(f"✓ Using environment value: {app.DOCKER_HOST_IP}")
    
    # Test 3: Verify no hardcoded IP in critical proxy code
    print("\nTest 3: Checking for hardcoded IPs in proxy code...")
    with open('app.py', 'r') as f:
        app_code = f.read()
    
    # Find the proxy function
    proxy_start = app_code.find('def proxy(port, path):')
    proxy_end = app_code.find('\n@app.route', proxy_start + 1)
    proxy_code = app_code[proxy_start:proxy_end]
    
    # Check that we're using DOCKER_HOST_IP variable in target_url
    assert 'DOCKER_HOST_IP' in proxy_code, \
        "Proxy function should use DOCKER_HOST_IP variable"
    assert f'http://{"{DOCKER_HOST_IP}"}' in proxy_code or 'f\'http://{DOCKER_HOST_IP}' in proxy_code, \
        "Proxy should construct URL using DOCKER_HOST_IP"
    print("✓ Proxy function uses DOCKER_HOST_IP variable")
    
    # Test 4: Verify WebSocket proxy uses DOCKER_HOST_IP
    print("\nTest 4: Checking WebSocket proxy...")
    ws_proxy_start = app_code.find('def _websocket_proxy_handler')
    ws_proxy_end = app_code.find('\n@sock.route', ws_proxy_start + 1)
    ws_proxy_code = app_code[ws_proxy_start:ws_proxy_end]
    
    assert 'DOCKER_HOST_IP' in ws_proxy_code, \
        "WebSocket proxy should use DOCKER_HOST_IP variable"
    print("✓ WebSocket proxy uses DOCKER_HOST_IP variable")
    
    # Test 5: Verify docker-compose.yml has extra_hosts configuration
    print("\nTest 5: Checking docker-compose.yml configuration...")
    with open('docker-compose.yml', 'r') as f:
        compose_content = f.read()
    
    assert 'DOCKER_HOST_IP' in compose_content, \
        "docker-compose.yml should include DOCKER_HOST_IP environment variable"
    assert 'extra_hosts' in compose_content, \
        "docker-compose.yml should include extra_hosts for Linux/Unraid support"
    assert 'host.docker.internal:host-gateway' in compose_content, \
        "extra_hosts should map host.docker.internal to host-gateway"
    print("✓ docker-compose.yml has correct configuration")
    
    # Test 6: Verify Unraid template has the configuration
    print("\nTest 6: Checking Unraid template...")
    with open('my-ha-edu-portal.xml', 'r') as f:
        xml_content = f.read()
    
    assert 'DOCKER_HOST_IP' in xml_content, \
        "Unraid template should include DOCKER_HOST_IP variable"
    assert '--add-host=host.docker.internal:host-gateway' in xml_content, \
        "Unraid template should include extra_hosts parameter"
    print("✓ Unraid template has correct configuration")
    
    # Test 7: Verify .env.example documents the variable
    print("\nTest 7: Checking .env.example documentation...")
    with open('.env.example', 'r') as f:
        env_example = f.read()
    
    assert 'DOCKER_HOST_IP' in env_example, \
        ".env.example should document DOCKER_HOST_IP"
    print("✓ .env.example documents DOCKER_HOST_IP")
    
    # Test 8: Verify README documents the variable
    print("\nTest 8: Checking README.md documentation...")
    with open('README.md', 'r') as f:
        readme = f.read()
    
    assert 'DOCKER_HOST_IP' in readme, \
        "README should document DOCKER_HOST_IP in configuration table"
    print("✓ README.md documents DOCKER_HOST_IP")
    
    # Test 9: Check that old hardcoded IP is still recognized for compatibility
    print("\nTest 9: Verifying backward compatibility...")
    # The old IP should still be in the list of recognized backend hosts
    # for Location header rewriting (line ~1994)
    location_rewrite_section = app_code[app_code.find('is_backend_host = parsed.hostname in'):
                                       app_code.find('is_backend_host = parsed.hostname in') + 200]
    assert '192.168.50.111' in location_rewrite_section, \
        "Old hardcoded IP should still be recognized for backward compatibility"
    print("✓ Old hardcoded IP still recognized for Location header rewriting")
    
    print()
    print("=" * 60)
    print("✅ All DOCKER_HOST_IP tests passed!")
    print("=" * 60)
    print()
    print("Summary:")
    print("- DOCKER_HOST_IP is properly configured")
    print("- Proxy code uses the variable instead of hardcoded IP")
    print("- WebSocket proxy uses the variable")
    print("- docker-compose.yml has Linux/Unraid support via extra_hosts")
    print("- Unraid template includes the configuration")
    print("- Documentation is complete")
    print("- Backward compatibility maintained")
    print()

if __name__ == '__main__':
    try:
        test_docker_host_ip_configuration()
    except AssertionError as e:
        print(f"\n❌ Test failed: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
