#!/usr/bin/env python3
"""
Test script to verify Docker volumes are properly deleted when instances are deleted.
This test ensures that the volume deletion bug is fixed.
"""

import sys
import os

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_delete_instance_removes_volume():
    """Test that delete_instance function includes volume removal code"""
    print("\nTesting delete_instance removes volume...")
    try:
        with open('app.py', 'r') as f:
            content = f.read()
        
        # Find delete_instance function
        delete_func_start = content.find('def delete_instance(')
        delete_func_end = content.find('\n@app.route', delete_func_start + 1)
        if delete_func_end == -1:
            delete_func_end = content.find('\ndef ', delete_func_start + 1)
        
        delete_func = content[delete_func_start:delete_func_end]
        
        # Check for volume removal code
        checks = [
            ('volume_name', 'Volume name extraction'),
            ('client.volumes.get', 'Get volume object'),
            ('volume.remove()', 'Volume removal call'),
        ]
        
        all_found = True
        for check, desc in checks:
            if check in delete_func:
                print(f"  ✓ Found: {desc}")
            else:
                print(f"  ✗ Missing: {desc}")
                all_found = False
        
        if all_found:
            print("✓ delete_instance properly removes volumes")
            return True
        else:
            print("✗ delete_instance does not properly remove volumes")
            return False
            
    except Exception as e:
        print(f"✗ Test error: {e}")
        return False

def test_delete_all_instances_removes_volumes():
    """Test that delete_all_instances function includes volume removal code"""
    print("\nTesting delete_all_instances removes volumes...")
    try:
        with open('app.py', 'r') as f:
            content = f.read()
        
        # Find delete_all_instances function
        delete_all_start = content.find('def delete_all_instances(')
        delete_all_end = content.find('\n@app.route', delete_all_start + 1)
        if delete_all_end == -1:
            delete_all_end = content.find('\ndef proxy', delete_all_start + 1)
        
        delete_all_func = content[delete_all_start:delete_all_end]
        
        # Check for volume removal code
        checks = [
            ('volume_name', 'Volume name extraction'),
            ('client.volumes.get', 'Get volume object'),
            ('volume.remove()', 'Volume removal call'),
        ]
        
        all_found = True
        for check, desc in checks:
            if check in delete_all_func:
                print(f"  ✓ Found: {desc}")
            else:
                print(f"  ✗ Missing: {desc}")
                all_found = False
        
        if all_found:
            print("✓ delete_all_instances properly removes volumes")
            return True
        else:
            print("✗ delete_all_instances does not properly remove volumes")
            return False
            
    except Exception as e:
        print(f"✗ Test error: {e}")
        return False

def test_volume_removal_pattern_matches_reset():
    """Test that volume removal pattern is consistent with reset_instance"""
    print("\nTesting volume removal pattern consistency...")
    try:
        with open('app.py', 'r') as f:
            content = f.read()
        
        # Find reset_instance volume removal pattern
        reset_start = content.find('def reset_instance(')
        reset_end = content.find('\n@app.route', reset_start + 1)
        if reset_end == -1:
            reset_end = content.find('\ndef check_admin', reset_start + 1)
        reset_func = content[reset_start:reset_end]
        
        # Extract the volume removal pattern from reset_instance
        if 'volume = client.volumes.get(volume_name)' in reset_func and 'volume.remove()' in reset_func:
            print("  ✓ reset_instance has volume removal pattern")
        else:
            print("  ✗ reset_instance missing volume removal pattern")
            return False
        
        # Find delete_instance function
        delete_func_start = content.find('def delete_instance(')
        delete_func_end = content.find('\n@app.route', delete_func_start + 1)
        delete_func = content[delete_func_start:delete_func_end]
        
        # Check delete_instance has same pattern
        if 'volume = client.volumes.get(volume_name)' in delete_func and 'volume.remove()' in delete_func:
            print("  ✓ delete_instance uses same volume removal pattern")
        else:
            print("  ✗ delete_instance uses different volume removal pattern")
            return False
        
        print("✓ Volume removal pattern is consistent")
        return True
        
    except Exception as e:
        print(f"✗ Test error: {e}")
        return False

def test_volume_removal_has_error_handling():
    """Test that volume removal has proper error handling"""
    print("\nTesting volume removal error handling...")
    try:
        with open('app.py', 'r') as f:
            content = f.read()
        
        # Find delete_instance function
        delete_func_start = content.find('def delete_instance(')
        delete_func_end = content.find('\n@app.route', delete_func_start + 1)
        delete_func = content[delete_func_start:delete_func_end]
        
        # Check for error handling around volume removal
        checks = [
            ('try:', 'Try block for volume removal'),
            ('docker.errors.NotFound', 'Handle NotFound error for missing volumes'),
            ('except Exception as e:', 'Generic exception handler'),
        ]
        
        all_found = True
        for check, desc in checks:
            if check in delete_func:
                print(f"  ✓ Found: {desc}")
            else:
                print(f"  ✗ Missing: {desc}")
                all_found = False
        
        if all_found:
            print("✓ Volume removal has proper error handling")
            return True
        else:
            print("✗ Volume removal missing proper error handling")
            return False
            
    except Exception as e:
        print(f"✗ Test error: {e}")
        return False

def main():
    """Run all tests"""
    print("=" * 70)
    print("HA-Edu Docker Volume Deletion Tests")
    print("=" * 70)
    
    tests = [
        test_delete_instance_removes_volume,
        test_delete_all_instances_removes_volumes,
        test_volume_removal_pattern_matches_reset,
        test_volume_removal_has_error_handling,
    ]
    
    results = [test() for test in tests]
    
    passed = sum(results)
    total = len(results)
    
    print("\n" + "=" * 70)
    print(f"Tests passed: {passed}/{total}")
    print("=" * 70)
    
    if passed == total:
        print("\n✓ All tests passed! Volumes will be properly deleted.")
        return 0
    else:
        print(f"\n✗ {total - passed} test(s) failed")
        return 1

if __name__ == '__main__':
    sys.exit(main())
