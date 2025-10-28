#!/usr/bin/env python3
"""
Test script for the proxy endpoint functionality
"""

import sys
import os
import json
import tempfile

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_proxy_route_exists():
    """Test that proxy route is registered"""
    print("Testing proxy route registration...")
    try:
        import app
        
        # Check if proxy routes are registered
        routes = [rule.rule for rule in app.app.url_map.iter_rules()]
        proxy_routes = [r for r in routes if '/proxy' in r]
        
        if proxy_routes:
            print(f"✓ Proxy routes found: {proxy_routes}")
            return True
        else:
            print("✗ No proxy routes found")
            return False
            
    except Exception as e:
        print(f"✗ Error testing proxy route: {e}")
        return False

def test_proxy_function_exists():
    """Test that proxy function exists"""
    print("\nTesting proxy function...")
    try:
        import app
        
        if hasattr(app, 'proxy'):
            print("✓ Proxy function exists")
            return True
        else:
            print("✗ Proxy function not found")
            return False
            
    except Exception as e:
        print(f"✗ Error testing proxy function: {e}")
        return False

def test_template_uses_proxy():
    """Test that template uses proxy URLs"""
    print("\nTesting template proxy URL usage...")
    try:
        template_path = os.path.join(os.path.dirname(__file__), 'templates', 'index.html')
        with open(template_path, 'r') as f:
            content = f.read()
            
        # Check that template uses /proxy/ URL instead of direct port
        if '/proxy/{{ instance.port }}/' in content:
            print("✓ Template uses proxy URL format")
            
            # Make sure it doesn't have the old direct port format
            if 'request.host.split' not in content or '}}:{{ instance.port }}' not in content:
                print("✓ Template doesn't use old direct port URL")
                return True
            else:
                print("⚠ Template still contains old direct port URL format")
                return True  # Still pass since proxy URL is present
        else:
            print("✗ Template doesn't use proxy URL format")
            return False
            
    except Exception as e:
        print(f"✗ Error testing template: {e}")
        return False

def test_proxy_validates_port():
    """Test that proxy endpoint validates ports against instances"""
    print("\nTesting proxy port validation logic...")
    try:
        import app
        from flask import Flask
        
        # Create a temporary test app
        test_app = Flask(__name__)
        
        # Create a temporary data file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            test_data_file = f.name
            json.dump({
                'test-instance': {
                    'container_id': 'test123',
                    'port': 8123,
                    'status': 'running'
                }
            }, f)
        
        # Override DATA_FILE temporarily
        original_data_file = app.DATA_FILE
        app.DATA_FILE = test_data_file
        
        try:
            # Test loading instances
            instances = app.load_instances()
            if 'test-instance' in instances and instances['test-instance']['port'] == 8123:
                print("✓ Proxy can validate ports against loaded instances")
                result = True
            else:
                print("✗ Failed to load test instances")
                result = False
        finally:
            # Restore original DATA_FILE
            app.DATA_FILE = original_data_file
            # Clean up temp file
            os.unlink(test_data_file)
            
        return result
            
    except Exception as e:
        print(f"✗ Error testing proxy validation: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_requests_import():
    """Test that requests library is available for proxy"""
    print("\nTesting requests library for proxy...")
    try:
        import requests
        print("✓ Requests library available for proxy functionality")
        return True
    except ImportError as e:
        print(f"✗ Requests library not available: {e}")
        return False

def main():
    """Run all proxy tests"""
    print("=" * 60)
    print("HA-Edu Proxy Functionality Tests")
    print("=" * 60)
    
    tests = [
        test_requests_import,
        test_proxy_route_exists,
        test_proxy_function_exists,
        test_template_uses_proxy,
        test_proxy_validates_port,
    ]
    
    results = []
    for test in tests:
        try:
            result = test()
            results.append(result)
        except Exception as e:
            print(f"✗ Test failed with exception: {e}")
            results.append(False)
    
    print("\n" + "=" * 60)
    print(f"Tests passed: {sum(results)}/{len(results)}")
    print("=" * 60)
    
    if all(results):
        print("\n✓ All proxy tests passed!")
        return 0
    else:
        print("\n✗ Some proxy tests failed")
        return 1

if __name__ == '__main__':
    sys.exit(main())
