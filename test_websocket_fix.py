#!/usr/bin/env python3
"""
Test to verify the WebSocket route fix for the NoneType callable error
"""

import sys
import os

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_websocket_routes_are_callable():
    """Test that both WebSocket routes have callable view functions"""
    print("\nTesting WebSocket route callability...")
    try:
        import app as app_module
        
        # Get the app's URL map
        url_map = app_module.app.url_map
        
        # Find WebSocket routes and check their view functions
        websocket_routes_status = {}
        for rule in url_map.iter_rules():
            if 'websocket' in rule.rule.lower():
                endpoint = rule.endpoint
                view_func = app_module.app.view_functions.get(endpoint)
                
                is_callable = callable(view_func)
                is_none = view_func is None
                
                websocket_routes_status[rule.rule] = {
                    'endpoint': endpoint,
                    'callable': is_callable,
                    'is_none': is_none,
                    'view_func_type': type(view_func).__name__
                }
                
                print(f"  Route: {rule.rule}")
                print(f"    Endpoint: {endpoint}")
                print(f"    View function: {view_func}")
                print(f"    Callable: {is_callable}")
                print(f"    Is None: {is_none}")
                
                if is_none:
                    print(f"    ✗ FAIL: View function is None!")
                    return False
                elif not is_callable:
                    print(f"    ✗ FAIL: View function is not callable!")
                    return False
                else:
                    print(f"    ✓ PASS: View function is callable")
        
        if not websocket_routes_status:
            print("  ✗ FAIL: No WebSocket routes found!")
            return False
        
        print(f"\n  ✓ All {len(websocket_routes_status)} WebSocket route(s) have callable view functions")
        return True
        
    except Exception as e:
        print(f"  ✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_no_duplicate_decorators():
    """Test that we're not using duplicate @sock.route decorators"""
    print("\nTesting for duplicate decorator pattern...")
    try:
        # Read the app.py file and check for the problematic pattern
        with open('/home/runner/work/HA-Edu/HA-Edu/app.py', 'r') as f:
            content = f.read()
        
        # Look for consecutive @sock.route decorators (the problematic pattern)
        lines = content.split('\n')
        consecutive_sock_routes = 0
        for i in range(len(lines) - 1):
            if '@sock.route' in lines[i] and '@sock.route' in lines[i + 1]:
                consecutive_sock_routes += 1
                print(f"  ✗ Found consecutive @sock.route decorators at lines {i+1} and {i+2}")
                print(f"    Line {i+1}: {lines[i].strip()}")
                print(f"    Line {i+2}: {lines[i+1].strip()}")
        
        if consecutive_sock_routes > 0:
            print(f"  ✗ FAIL: Found {consecutive_sock_routes} instance(s) of consecutive @sock.route decorators")
            return False
        
        print("  ✓ No consecutive @sock.route decorators found")
        return True
        
    except Exception as e:
        print(f"  ✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_separate_websocket_handlers():
    """Test that we have separate handler functions for each WebSocket route"""
    print("\nTesting for separate WebSocket handler functions...")
    try:
        import app as app_module
        
        # Check for the two separate handler functions
        handlers = [
            'websocket_proxy_direct',
            'websocket_proxy_with_port',
            '_websocket_proxy_handler'
        ]
        
        all_found = True
        for handler_name in handlers:
            if hasattr(app_module, handler_name):
                print(f"  ✓ Handler '{handler_name}' exists")
            else:
                print(f"  ✗ Handler '{handler_name}' NOT found")
                all_found = False
        
        if not all_found:
            print("  ✗ FAIL: Not all required handler functions exist")
            return False
        
        print("  ✓ All required handler functions exist")
        return True
        
    except Exception as e:
        print(f"  ✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Run all WebSocket fix tests"""
    print("=" * 60)
    print("HA-Edu WebSocket Fix Verification Tests")
    print("=" * 60)
    
    tests = [
        test_websocket_routes_are_callable,
        test_no_duplicate_decorators,
        test_separate_websocket_handlers,
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
        print("\n✓ All WebSocket fix verification tests passed!")
        print("The 'NoneType is not callable' error should now be resolved.")
        return 0
    else:
        print("\n✗ Some WebSocket fix verification tests failed")
        return 1

if __name__ == '__main__':
    sys.exit(main())
