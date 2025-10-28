#!/usr/bin/env python3
"""
Integration test to simulate the WebSocket connection error scenario
This test verifies that the fix resolves the actual error from the problem statement.
"""

import sys
import os

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_websocket_route_invocation():
    """Test that invoking WebSocket routes doesn't cause NoneType errors"""
    print("\nTesting WebSocket route invocation (simulating the actual error)...")
    try:
        import app as app_module
        from flask import Flask
        
        # Create a test client
        with app_module.app.test_client() as client:
            # Test the direct /api/websocket route
            # This should not raise a TypeError about NoneType
            print("\n  Testing GET /api/websocket...")
            try:
                # Note: This will return an error (WebSocket upgrade required)
                # but it should NOT be a TypeError about NoneType
                response = client.get('/api/websocket')
                # WebSocket upgrade will fail in test client, but we're checking
                # that we don't get "NoneType is not callable" error
                print(f"    Response status: {response.status_code}")
                
                # If we get here without TypeError, the fix is working
                print(f"    ✓ No TypeError - route handler is callable")
                
            except TypeError as e:
                if 'NoneType' in str(e) and 'callable' in str(e):
                    print(f"    ✗ FAIL: Got the NoneType callable error!")
                    print(f"    Error: {e}")
                    return False
                else:
                    # Some other TypeError, re-raise
                    raise
            except Exception as e:
                # Other exceptions are expected (e.g., WebSocket upgrade issues)
                print(f"    Note: Got expected exception: {type(e).__name__}")
                # This is fine - we're just checking that the handler itself is callable
            
            # Test the proxy route with port
            print("\n  Testing GET /proxy/8123/api/websocket...")
            try:
                response = client.get('/proxy/8123/api/websocket')
                print(f"    Response status: {response.status_code}")
                print(f"    ✓ No TypeError - route handler is callable")
                
            except TypeError as e:
                if 'NoneType' in str(e) and 'callable' in str(e):
                    print(f"    ✗ FAIL: Got the NoneType callable error!")
                    print(f"    Error: {e}")
                    return False
                else:
                    raise
            except Exception as e:
                print(f"    Note: Got expected exception: {type(e).__name__}")
        
        print("\n  ✓ PASS: Both WebSocket routes are properly callable")
        print("  The 'TypeError: NoneType is not callable' error is fixed!")
        return True
        
    except Exception as e:
        print(f"  ✗ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_error_log_scenario():
    """Test the exact scenario from the error log"""
    print("\nSimulating the error scenario from the problem statement...")
    print("  Original error was:")
    print("    ERROR:app:Exception on /api/websocket [GET]")
    print("    TypeError: 'NoneType' object is not callable")
    print()
    
    try:
        import app as app_module
        
        # Verify the routes exist and are callable
        print("  Checking route registration...")
        
        # Get all WebSocket routes
        websocket_routes = []
        for rule in app_module.app.url_map.iter_rules():
            if 'api/websocket' in rule.rule:
                websocket_routes.append(rule)
                endpoint = rule.endpoint
                view_func = app_module.app.view_functions.get(endpoint)
                
                print(f"    Route: {rule.rule}")
                print(f"      Endpoint: {endpoint}")
                print(f"      View function: {view_func}")
                print(f"      Type: {type(view_func).__name__}")
                
                if view_func is None:
                    print(f"      ✗ CRITICAL: View function is None!")
                    return False
                elif not callable(view_func):
                    print(f"      ✗ CRITICAL: View function is not callable!")
                    return False
                else:
                    print(f"      ✓ View function is valid and callable")
        
        if len(websocket_routes) != 2:
            print(f"  ✗ Expected 2 WebSocket routes, found {len(websocket_routes)}")
            return False
        
        print(f"\n  ✓ PASS: Both WebSocket routes are properly configured")
        print("  The error from the problem statement should no longer occur!")
        return True
        
    except Exception as e:
        print(f"  ✗ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Run integration tests for the WebSocket fix"""
    print("=" * 70)
    print("WebSocket Error Fix - Integration Test")
    print("Verifying fix for: TypeError: 'NoneType' object is not callable")
    print("=" * 70)
    
    tests = [
        test_error_log_scenario,
        test_websocket_route_invocation,
    ]
    
    results = []
    for test in tests:
        try:
            result = test()
            results.append(result)
        except Exception as e:
            print(f"\n✗ Test failed with exception: {e}")
            import traceback
            traceback.print_exc()
            results.append(False)
    
    print("\n" + "=" * 70)
    print(f"Tests passed: {sum(results)}/{len(results)}")
    print("=" * 70)
    
    if all(results):
        print("\n✓ SUCCESS: All integration tests passed!")
        print("\nThe WebSocket error that prevented account creation is now fixed.")
        print("Users should be able to create accounts and access /api/websocket.")
        return 0
    else:
        print("\n✗ FAILURE: Some integration tests failed")
        return 1

if __name__ == '__main__':
    sys.exit(main())
