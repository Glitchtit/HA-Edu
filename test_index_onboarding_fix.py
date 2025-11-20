#!/usr/bin/env python3
"""
Test to verify that the index() route includes onboarding status for admins
This test ensures the fix for the onboarding check bug is working correctly
"""

import sys
import os
import json

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def test_index_adds_onboarding_for_admins():
    """Test that index() route adds onboarding status for admin users"""
    print("\nTesting that index() includes onboarding check for admins...")
    
    # Read app.py to verify the code is present
    app_path = os.path.join(os.path.dirname(__file__), 'app.py')
    with open(app_path, 'r') as f:
        content = f.read()
    
    # Find the index() function
    if "def index():" not in content:
        print("✗ index() function not found")
        return False
    
    # Extract the index function (simplified check)
    index_start = content.find("def index():")
    index_end = content.find("\n@app.route", index_start + 1)
    if index_end == -1:
        index_end = content.find("\ndef ", index_start + 1)
    
    index_code = content[index_start:index_end]
    
    # Check that the onboarding check is present in index()
    checks = [
        ("# For admins, add onboarding status to each instance", "Admin onboarding comment"),
        ("check_instance_onboarding_complete_cached(volume_name)", "Onboarding check call"),
        ("instance['onboarded'] = ", "Onboarded field assignment"),
    ]
    
    all_checks_passed = True
    for check, description in checks:
        if check in index_code:
            print(f"✓ Found: {description}")
        else:
            print(f"✗ Missing: {description}")
            all_checks_passed = False
    
    if not all_checks_passed:
        print("\n✗ The onboarding check is not properly implemented in index()")
        return False
    
    # Verify the check is in the else block (for admins)
    if "else:" in index_code and index_code.find("else:") < index_code.find("check_instance_onboarding_complete_cached"):
        print("✓ Onboarding check is in the admin-only section")
    else:
        print("✗ Onboarding check might not be properly restricted to admins")
        return False
    
    print("\n✓ index() route correctly adds onboarding status for admins")
    return True


def test_consistency_between_index_and_api():
    """Test that index() and get_instances() use the same logic"""
    print("\nTesting consistency between index() and get_instances()...")
    
    app_path = os.path.join(os.path.dirname(__file__), 'app.py')
    with open(app_path, 'r') as f:
        content = f.read()
    
    # Find both functions
    index_start = content.find("def index():")
    get_instances_start = content.find("def get_instances():")
    
    if index_start == -1 or get_instances_start == -1:
        print("✗ Could not find both functions")
        return False
    
    # Extract relevant sections
    index_end = content.find("\n@app.route", index_start + 1)
    if index_end == -1:
        index_end = content.find("\ndef ", index_start + 1)
    
    get_instances_end = content.find("\n@app.route", get_instances_start + 1)
    if get_instances_end == -1:
        get_instances_end = content.find("\ndef ", get_instances_start + 1)
    
    index_code = content[index_start:index_end]
    get_instances_code = content[get_instances_start:get_instances_end]
    
    # Check that both use the same volume name logic
    volume_name_pattern = "instance.get('container_name', f'ha-edu-{server_name.lower().replace(\" \", \"-\")}')"
    
    if volume_name_pattern in index_code and volume_name_pattern in get_instances_code:
        print("✓ Both functions use the same volume name logic")
    else:
        print("✗ Volume name logic differs between functions")
        return False
    
    # Check that both call check_instance_onboarding_complete_cached
    if "check_instance_onboarding_complete_cached(volume_name)" in index_code and \
       "check_instance_onboarding_complete_cached(volume_name)" in get_instances_code:
        print("✓ Both functions use the same onboarding check")
    else:
        print("✗ Onboarding check differs or is missing")
        return False
    
    print("\n✓ index() and get_instances() are consistent")
    return True


def main():
    """Run all tests"""
    print("=" * 70)
    print("Index Onboarding Fix Verification Tests")
    print("=" * 70)
    
    tests = [
        test_index_adds_onboarding_for_admins,
        test_consistency_between_index_and_api,
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
    print(f"Results: {sum(results)}/{len(results)} tests passed")
    print("=" * 70)
    
    return all(results)


if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)
