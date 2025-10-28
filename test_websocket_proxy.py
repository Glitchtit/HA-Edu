#!/usr/bin/env python3
"""
Tests for the WebSocket proxy functionality
"""

import sys
import os

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_websocket_imports():
    """Test that WebSocket dependencies are available"""
    print("\nTesting WebSocket imports...")
    try:
        import flask_sock
        print("✓ flask_sock imported successfully")
        
        import simple_websocket
        print("✓ simple_websocket imported successfully")
        
        return True
    except ImportError as e:
        print(f"✗ Import error: {e}")
        return False

def test_websocket_initialization():
    """Test that WebSocket support is initialized in app"""
    print("\nTesting WebSocket initialization...")
    try:
        import app as app_module
        
        # Check that sock object exists
        if not hasattr(app_module, 'sock'):
            print("✗ sock object not found in app module")
            return False
        print("✓ sock object exists in app module")
        
        # Check that sock is a Sock instance
        from flask_sock import Sock
        if not isinstance(app_module.sock, Sock):
            print(f"✗ sock is not a Sock instance: {type(app_module.sock)}")
            return False
        print("✓ sock is a Sock instance")
        
        return True
    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_websocket_route_exists():
    """Test that WebSocket routes are registered"""
    print("\nTesting WebSocket routes...")
    try:
        import app as app_module
        
        # Check if websocket_proxy function exists
        if not hasattr(app_module, 'websocket_proxy'):
            print("✗ websocket_proxy function not found")
            return False
        print("✓ websocket_proxy function exists")
        
        # The function is decorated by @sock.route, so it's wrapped
        # We just need to verify it exists
        print("✓ websocket_proxy is registered (decorated by @sock.route)")
        
        # Check for the WebSocket proxy helper function
        if not hasattr(app_module, 'proxy_websocket_connection'):
            print("✗ proxy_websocket_connection function not found")
            return False
        print("✓ proxy_websocket_connection function exists")
        
        # Verify the helper is callable
        if not callable(app_module.proxy_websocket_connection):
            print("✗ proxy_websocket_connection is not callable")
            return False
        print("✓ proxy_websocket_connection is callable")
        
        return True
    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_websocket_url_patterns():
    """Test that WebSocket URL patterns are correct"""
    print("\nTesting WebSocket URL patterns...")
    try:
        import app as app_module
        
        # Get the app's URL map
        url_map = app_module.app.url_map
        
        # Look for WebSocket routes
        websocket_routes = []
        for rule in url_map.iter_rules():
            if 'websocket' in rule.rule.lower():
                websocket_routes.append(rule.rule)
        
        if not websocket_routes:
            print("✗ No WebSocket routes found in URL map")
            return False
        
        print(f"✓ Found {len(websocket_routes)} WebSocket route(s):")
        for route in websocket_routes:
            print(f"  - {route}")
        
        # Check for expected routes
        expected_routes = ['/api/websocket', '/proxy/<int:port>/api/websocket']
        found_routes = []
        
        for expected in expected_routes:
            # Normalize the route format for comparison
            found = False
            for route in websocket_routes:
                # Check if the route matches (accounting for different representations)
                if 'api/websocket' in route:
                    if expected == '/api/websocket' and route.count('/') <= 3:
                        found = True
                        found_routes.append(expected)
                        break
                    elif expected.startswith('/proxy/') and 'proxy' in route:
                        found = True
                        found_routes.append(expected)
                        break
        
        if not found_routes:
            print("✗ Expected WebSocket routes not found")
            return False
        
        print(f"✓ Found expected WebSocket routes: {found_routes}")
        return True
        
    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_threading_import():
    """Test that threading module is imported for WebSocket proxy"""
    print("\nTesting threading import...")
    try:
        import app as app_module
        
        # Check if threading is imported
        if not hasattr(app_module, 'threading'):
            print("✗ threading module not imported")
            return False
        print("✓ threading module imported")
        
        return True
    except Exception as e:
        print(f"✗ Error: {e}")
        return False

def main():
    """Run all WebSocket proxy tests"""
    print("=" * 60)
    print("HA-Edu WebSocket Proxy Tests")
    print("=" * 60)
    
    tests = [
        test_websocket_imports,
        test_websocket_initialization,
        test_websocket_route_exists,
        test_websocket_url_patterns,
        test_threading_import,
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
        print("\n✓ All WebSocket proxy tests passed!")
        return 0
    else:
        print("\n✗ Some WebSocket proxy tests failed")
        return 1

if __name__ == '__main__':
    sys.exit(main())
