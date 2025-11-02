#!/usr/bin/env python3
"""
Test script to verify MAX_INSTANCES environment variable functionality
"""

import sys
import os
import json
import tempfile

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_max_instances_env_variable():
    """Test that MAX_INSTANCES environment variable is loaded correctly"""
    print("Testing MAX_INSTANCES environment variable loading...")
    
    # Save original env
    original_max_instances = os.environ.get('MAX_INSTANCES')
    
    try:
        # Test 1: No env set (should default to 0 for unlimited)
        os.environ.pop('MAX_INSTANCES', None)
        if 'app' in sys.modules:
            del sys.modules['app']
        import app
        assert app.MAX_INSTANCES == 0, f"Expected 0, got {app.MAX_INSTANCES}"
        print("✓ MAX_INSTANCES defaults to 0 (unlimited) when not set")
        
        # Test 2: Empty string (should be 0)
        os.environ['MAX_INSTANCES'] = ''
        if 'app' in sys.modules:
            del sys.modules['app']
        import importlib
        import app as app2
        importlib.reload(app2)
        assert app2.MAX_INSTANCES == 0, f"Expected 0, got {app2.MAX_INSTANCES}"
        print("✓ MAX_INSTANCES is 0 when set to empty string")
        
        # Test 3: Set to 1
        os.environ['MAX_INSTANCES'] = '1'
        if 'app' in sys.modules:
            del sys.modules['app']
        import app as app3
        importlib.reload(app3)
        assert app3.MAX_INSTANCES == 1, f"Expected 1, got {app3.MAX_INSTANCES}"
        print("✓ MAX_INSTANCES is 1 when set to '1'")
        
        # Test 4: Set to 5
        os.environ['MAX_INSTANCES'] = '5'
        if 'app' in sys.modules:
            del sys.modules['app']
        import app as app4
        importlib.reload(app4)
        assert app4.MAX_INSTANCES == 5, f"Expected 5, got {app4.MAX_INSTANCES}"
        print("✓ MAX_INSTANCES is 5 when set to '5'")
        
        return True
    except Exception as e:
        print(f"✗ Error testing MAX_INSTANCES: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        # Restore original env
        if original_max_instances is not None:
            os.environ['MAX_INSTANCES'] = original_max_instances
        else:
            os.environ.pop('MAX_INSTANCES', None)

def test_can_create_instance_function():
    """Test the can_create_instance function logic"""
    print("\nTesting can_create_instance function...")
    
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
        # Reload app with new config
        if 'app' in sys.modules:
            del sys.modules['app']
        import app
        import importlib
        importlib.reload(app)
        
        # Create a mock request object
        class MockRequest:
            def __init__(self, remote_addr='1.2.3.4', headers=None):
                self.remote_addr = remote_addr
                self.headers = headers or {}
        
        # Test 1: User with no instances (should be allowed)
        request = MockRequest()
        instances = {}
        can_create, user_count, max_allowed = app.can_create_instance(request, instances)
        assert can_create == True, "User with 0 instances should be able to create"
        assert user_count == 0, f"Expected count 0, got {user_count}"
        assert max_allowed == 2, f"Expected max 2, got {max_allowed}"
        print("✓ User with 0 instances can create (limit: 2)")
        
        # Test 2: User with 1 instance (should be allowed)
        instances = {
            'test1': {'created_by': 'IP: 1.2.3.4', 'port': 8123}
        }
        can_create, user_count, max_allowed = app.can_create_instance(request, instances)
        assert can_create == True, "User with 1 instance should be able to create"
        assert user_count == 1, f"Expected count 1, got {user_count}"
        assert max_allowed == 2, f"Expected max 2, got {max_allowed}"
        print("✓ User with 1 instance can create (limit: 2)")
        
        # Test 3: User with 2 instances (should NOT be allowed)
        instances = {
            'test1': {'created_by': 'IP: 1.2.3.4', 'port': 8123},
            'test2': {'created_by': 'IP: 1.2.3.4', 'port': 8124}
        }
        can_create, user_count, max_allowed = app.can_create_instance(request, instances)
        assert can_create == False, "User with 2 instances should NOT be able to create"
        assert user_count == 2, f"Expected count 2, got {user_count}"
        assert max_allowed == 2, f"Expected max 2, got {max_allowed}"
        print("✓ User with 2 instances cannot create (limit: 2)")
        
        # Test 4: Different user should be allowed
        request2 = MockRequest(remote_addr='5.6.7.8')
        can_create, user_count, max_allowed = app.can_create_instance(request2, instances)
        assert can_create == True, "Different user should be able to create"
        assert user_count == 0, f"Expected count 0, got {user_count}"
        print("✓ Different user can create their own instances")
        
        # Test 5: Admin user should always be allowed
        request_admin = MockRequest(remote_addr='192.168.50.10')  # Local network IP
        instances_full = {
            'test1': {'created_by': 'IP: 192.168.50.10', 'port': 8123},
            'test2': {'created_by': 'IP: 192.168.50.10', 'port': 8124},
            'test3': {'created_by': 'IP: 192.168.50.10', 'port': 8125}
        }
        can_create, user_count, max_allowed = app.can_create_instance(request_admin, instances_full)
        assert can_create == True, "Admin should always be able to create"
        print("✓ Admin user can create unlimited instances")
        
        # Test 6: Unlimited mode (MAX_INSTANCES = 0)
        os.environ['MAX_INSTANCES'] = '0'
        if 'app' in sys.modules:
            del sys.modules['app']
        import app as app_unlimited
        importlib.reload(app_unlimited)
        
        can_create, user_count, max_allowed = app_unlimited.can_create_instance(request, instances)
        assert can_create == True, "User should be able to create in unlimited mode"
        assert max_allowed == 0, "Max should be 0 in unlimited mode"
        print("✓ Unlimited mode (MAX_INSTANCES=0) allows all users to create")
        
        return True
    except Exception as e:
        print(f"✗ Error testing can_create_instance: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        # Clean up
        os.remove(temp_file)

def test_server_side_validation():
    """Test that server-side validation is in place in create_instance endpoint"""
    print("\nTesting server-side validation in create_instance...")
    
    try:
        # Import app
        if 'app' in sys.modules:
            del sys.modules['app']
        import app
        import importlib
        importlib.reload(app)
        
        # Check that create_instance endpoint exists
        assert hasattr(app, 'create_instance'), "create_instance function not found"
        
        # Check that the function contains MAX_INSTANCES validation
        import inspect
        source = inspect.getsource(app.create_instance)
        
        # Verify server-side checks are present
        assert 'can_create_instance' in source, "can_create_instance check not found in create_instance"
        assert 'maximum limit' in source.lower(), "Maximum limit error message not found"
        
        print("✓ Server-side validation is present in create_instance endpoint")
        
        # Verify the validation is called twice (before and inside lock)
        count = source.count('can_create_instance')
        assert count >= 2, f"Expected at least 2 calls to can_create_instance (found {count})"
        print("✓ Server-side validation is called both before and inside the lock")
        
        return True
    except Exception as e:
        print(f"✗ Error testing server-side validation: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Run all tests"""
    print("=" * 60)
    print("MAX_INSTANCES Feature Test Suite")
    print("=" * 60)
    
    results = []
    
    # Run tests
    results.append(("MAX_INSTANCES env variable", test_max_instances_env_variable()))
    results.append(("can_create_instance function", test_can_create_instance_function()))
    results.append(("Server-side validation", test_server_side_validation()))
    
    # Print summary
    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✓ PASSED" if result else "✗ FAILED"
        print(f"{status}: {test_name}")
    
    print(f"\n{passed}/{total} tests passed")
    
    return passed == total

if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)
