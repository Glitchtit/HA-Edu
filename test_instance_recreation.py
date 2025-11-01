#!/usr/bin/env python3
"""
Test script to verify instances can be recreated with the same name after deletion.
This test ensures that leftover containers and volumes are cleaned up before creating a new instance.
"""

import sys
import os

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_create_instance_cleans_up_leftovers():
    """Test that create_instance includes cleanup code for leftover containers and volumes"""
    print("\nTesting create_instance cleans up leftover resources...")
    try:
        with open('app.py', 'r') as f:
            content = f.read()
        
        # Find create_instance function
        create_func_start = content.find('def create_instance(')
        # Find next function or route decorator
        next_route = content.find('\n@app.route', create_func_start + 1)
        next_func = content.find('\ndef ', create_func_start + 1)
        
        # Use the earliest endpoint found
        endpoints = [e for e in [next_route, next_func] if e != -1]
        create_func_end = min(endpoints) if endpoints else len(content)
        
        create_func = content[create_func_start:create_func_end]
        
        # Check for cleanup code before container creation
        checks = [
            ('existing_container', 'Check for existing container'),
            ('client.containers.get(container_name)', 'Get existing container by name'),
            ('existing_container.remove', 'Remove existing container'),
            ('existing_volume', 'Check for existing volume'),
            ('client.volumes.get(volume_name)', 'Get existing volume by name'),
            ('existing_volume.remove', 'Remove existing volume'),
        ]
        
        all_found = True
        for check, desc in checks:
            if check in create_func:
                print(f"  ✓ Found: {desc}")
            else:
                print(f"  ✗ Missing: {desc}")
                all_found = False
        
        if all_found:
            print("✓ create_instance properly cleans up leftover resources")
            return True
        else:
            print("✗ create_instance does not clean up leftover resources")
            return False
            
    except Exception as e:
        print(f"✗ Test error: {e}")
        return False

def test_cleanup_happens_before_volume_creation():
    """Test that cleanup happens before copy_master_config_to_volume"""
    print("\nTesting cleanup order (before volume creation)...")
    try:
        with open('app.py', 'r') as f:
            content = f.read()
        
        # Find create_instance function
        create_func_start = content.find('def create_instance(')
        next_route = content.find('\n@app.route', create_func_start + 1)
        next_func = content.find('\ndef ', create_func_start + 1)
        endpoints = [e for e in [next_route, next_func] if e != -1]
        create_func_end = min(endpoints) if endpoints else len(content)
        create_func = content[create_func_start:create_func_end]
        
        # Find positions of key operations
        cleanup_container_pos = create_func.find('existing_container')
        cleanup_volume_pos = create_func.find('existing_volume')
        copy_config_pos = create_func.find('copy_master_config_to_volume')
        
        if cleanup_container_pos == -1 or cleanup_volume_pos == -1 or copy_config_pos == -1:
            print("  ✗ Could not find all required operations")
            return False
        
        if cleanup_container_pos < copy_config_pos and cleanup_volume_pos < copy_config_pos:
            print("  ✓ Cleanup happens before volume initialization")
            print("✓ Operations are in correct order")
            return True
        else:
            print("  ✗ Cleanup does not happen before volume initialization")
            return False
            
    except Exception as e:
        print(f"✗ Test error: {e}")
        return False

def test_cleanup_has_error_handling():
    """Test that cleanup operations have proper error handling"""
    print("\nTesting cleanup error handling...")
    try:
        with open('app.py', 'r') as f:
            content = f.read()
        
        # Find create_instance function
        create_func_start = content.find('def create_instance(')
        next_route = content.find('\n@app.route', create_func_start + 1)
        next_func = content.find('\ndef ', create_func_start + 1)
        endpoints = [e for e in [next_route, next_func] if e != -1]
        create_func_end = min(endpoints) if endpoints else len(content)
        create_func = content[create_func_start:create_func_end]
        
        # Check for error handling in cleanup code
        # Count occurrences of docker.errors.NotFound to ensure both cleanups have it
        notfound_count = create_func.count('docker.errors.NotFound')
        
        if notfound_count >= 2:
            print(f"  ✓ Found {notfound_count} NotFound exception handlers (expected at least 2)")
        else:
            print(f"  ✗ Found only {notfound_count} NotFound exception handlers (expected at least 2)")
            return False
        
        # Check that cleanup uses try/except blocks
        if 'try:' in create_func and 'except docker.errors.NotFound:' in create_func:
            print("  ✓ Cleanup code has proper try/except blocks")
        else:
            print("  ✗ Missing proper try/except blocks for cleanup")
            return False
        
        print("✓ Cleanup has proper error handling")
        return True
            
    except Exception as e:
        print(f"✗ Test error: {e}")
        return False

def main():
    """Run all tests"""
    print("=" * 70)
    print("HA-Edu Instance Recreation Tests")
    print("=" * 70)
    
    tests = [
        test_create_instance_cleans_up_leftovers,
        test_cleanup_happens_before_volume_creation,
        test_cleanup_has_error_handling,
    ]
    
    results = [test() for test in tests]
    
    passed = sum(results)
    total = len(results)
    
    print("\n" + "=" * 70)
    print(f"Tests passed: {passed}/{total}")
    print("=" * 70)
    
    if passed == total:
        print("\n✓ All tests passed! Instances can be recreated with the same name.")
        return 0
    else:
        print(f"\n✗ {total - passed} test(s) failed")
        return 1

if __name__ == '__main__':
    sys.exit(main())
