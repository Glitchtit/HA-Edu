#!/usr/bin/env python3
"""
Test that the copy_master_config_to_volume function now handles missing alpine image
"""

import os
import sys

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_alpine_image_pull_logic():
    """Test that app.py now has logic to pull alpine image"""
    print("Testing alpine image pull logic...")
    
    app_path = os.path.join(os.path.dirname(__file__), 'app.py')
    with open(app_path, 'r') as f:
        content = f.read()
    
    # Check for the image pull logic in copy_master_config_to_volume
    func_start = content.find('def copy_master_config_to_volume')
    func_end = content.find('\ndef ', func_start + 1)
    func_content = content[func_start:func_end]
    
    checks = [
        ('client.images.get', 'Check if image exists'),
        ('docker.errors.ImageNotFound', 'Handle ImageNotFound exception'),
        ('client.images.pull', 'Pull alpine image if not found'),
        ("'alpine:latest'", 'Use alpine:latest image')
    ]
    
    all_passed = True
    for check, desc in checks:
        if check in func_content:
            print(f"✓ Found: {desc}")
        else:
            print(f"✗ Missing: {desc}")
            all_passed = False
    
    return all_passed

def test_pull_before_create():
    """Test that image pull happens before container creation"""
    print("\nTesting that image pull happens before container creation...")
    
    app_path = os.path.join(os.path.dirname(__file__), 'app.py')
    with open(app_path, 'r') as f:
        content = f.read()
    
    # Check order: pull logic should come before container creation
    func_start = content.find('def copy_master_config_to_volume')
    func_end = content.find('\ndef ', func_start + 1)
    func_content = content[func_start:func_end]
    
    pull_pos = func_content.find('client.images.pull')
    create_pos = func_content.find('client.containers.create')
    
    if pull_pos > 0 and create_pos > 0 and pull_pos < create_pos:
        print("✓ Image pull logic appears before container creation")
        return True
    else:
        print("✗ Image pull logic does not appear before container creation")
        return False

def main():
    """Run all tests"""
    print("=" * 60)
    print("Alpine Image Pull Logic Tests")
    print("=" * 60)
    
    tests = [
        test_alpine_image_pull_logic,
        test_pull_before_create
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
        print("\n✓ All alpine image pull logic tests passed!")
        return 0
    else:
        print("\n✗ Some tests failed")
        return 1

if __name__ == '__main__':
    sys.exit(main())
