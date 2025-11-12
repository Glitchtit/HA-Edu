#!/usr/bin/env python3
"""
Test script for session persistence across multiple workers

This test verifies that the SECRET_KEY is persistent and allows
sessions to work correctly across multiple Gunicorn workers.
"""

import sys
import os
import json
import tempfile
import shutil

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_secret_key_persistence():
    """Test that SECRET_KEY is generated and persists"""
    print("Testing SECRET_KEY persistence...")
    
    # Create a temporary data directory
    temp_dir = tempfile.mkdtemp()
    
    try:
        # Set environment
        os.environ['DATA_FILE'] = os.path.join(temp_dir, 'instances.json')
        
        # Import app (first time - should generate key)
        import app
        first_key = app.app.secret_key
        
        print(f"✓ First load generated key (length: {len(first_key)})")
        
        # Check that file was created
        secret_file = os.path.join(temp_dir, 'secret_key')
        if not os.path.exists(secret_file):
            print("✗ Secret key file was not created")
            return False
        
        print(f"✓ Secret key file created at {secret_file}")
        
        # Read the file
        with open(secret_file, 'r') as f:
            file_key = f.read().strip()
        
        if file_key != first_key:
            print("✗ Secret key in file doesn't match app secret key")
            return False
        
        print("✓ Secret key in file matches app secret key")
        
        # Reload the module to simulate a new worker
        import importlib
        importlib.reload(app)
        second_key = app.app.secret_key
        
        if second_key != first_key:
            print("✗ Secret key changed on reload")
            print(f"  First:  {first_key}")
            print(f"  Second: {second_key}")
            return False
        
        print("✓ Secret key persisted across reload")
        
        return True
        
    finally:
        # Clean up
        shutil.rmtree(temp_dir, ignore_errors=True)

def test_env_var_override():
    """Test that SECRET_KEY environment variable takes precedence"""
    print("\nTesting SECRET_KEY environment variable override...")
    
    # Create a temporary data directory
    temp_dir = tempfile.mkdtemp()
    
    try:
        # Set environment
        os.environ['DATA_FILE'] = os.path.join(temp_dir, 'instances.json')
        custom_key = 'test_secret_key_12345678901234567890123456789012'
        os.environ['SECRET_KEY'] = custom_key
        
        # Import app
        import app
        import importlib
        importlib.reload(app)
        
        if app.app.secret_key != custom_key:
            print(f"✗ Environment variable not used")
            print(f"  Expected: {custom_key}")
            print(f"  Got:      {app.app.secret_key}")
            return False
        
        print("✓ Environment variable SECRET_KEY used correctly")
        
        # Clean up
        del os.environ['SECRET_KEY']
        
        return True
        
    finally:
        # Clean up
        if 'SECRET_KEY' in os.environ:
            del os.environ['SECRET_KEY']
        shutil.rmtree(temp_dir, ignore_errors=True)

def test_session_cookie_functionality():
    """Test that Flask sessions work with the persistent secret key"""
    print("\nTesting Flask session functionality...")
    
    try:
        import app
        
        # Create a test client
        with app.app.test_client() as client:
            # Set a session value
            with client.session_transaction() as sess:
                sess['test_key'] = 'test_value'
                sess['proxy_port'] = 8123
            
            print("✓ Session values set correctly")
            
            # Make another request and verify session value persists
            with client.session_transaction() as sess:
                if sess.get('test_key') != 'test_value':
                    print("✗ Session value did not persist")
                    return False
                if sess.get('proxy_port') != 8123:
                    print("✗ Proxy port session value did not persist")
                    return False
            
            print("✓ Session values persisted correctly")
            
        return True
        
    except Exception as e:
        print(f"✗ Error testing session functionality: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Run all session persistence tests"""
    print("=" * 60)
    print("HA-Edu Session Persistence Tests")
    print("=" * 60)
    
    tests = [
        test_secret_key_persistence,
        test_env_var_override,
        test_session_cookie_functionality,
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
        print("\n✓ All session persistence tests passed!")
        return 0
    else:
        print("\n✗ Some session persistence tests failed")
        return 1

if __name__ == '__main__':
    sys.exit(main())
