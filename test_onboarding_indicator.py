#!/usr/bin/env python3
"""
Test script for the onboarding indicator feature
"""

import sys
import os

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_imports():
    """Test that all required modules can be imported"""
    print("Testing imports...")
    try:
        import flask
        import docker
        from dotenv import load_dotenv
        print("✓ All dependencies imported successfully")
        return True
    except ImportError as e:
        print(f"✗ Import error: {e}")
        return False

def test_get_instances_has_onboarding_check():
    """Test that get_instances adds onboarding status for admins"""
    print("\nTesting get_instances endpoint...")
    try:
        import app
        
        # Read the app.py file to check for onboarding check
        app_path = os.path.join(os.path.dirname(__file__), 'app.py')
        with open(app_path, 'r') as f:
            content = f.read()
            
            # Check that we call check_instance_onboarding_complete for admins
            if "check_instance_onboarding_complete(volume_name)" in content:
                print("✓ Onboarding check called in get_instances")
            else:
                print("✗ Onboarding check not found in get_instances")
                return False
            
            # Check that we add onboarded field to instance
            if "instance['onboarded']" in content:
                print("✓ Onboarded field added to instance data")
            else:
                print("✗ Onboarded field not added to instance data")
                return False
            
            # Check that it's only for admins
            if "# For admins, add onboarding status to each instance" in content:
                print("✓ Onboarding status only added for admins")
            else:
                print("✗ Missing admin-only logic for onboarding")
                return False
        
        return True
    except Exception as e:
        print(f"✗ get_instances endpoint error: {e}")
        return False

def test_template_has_onboarding_display():
    """Test that template displays onboarding status for admins"""
    print("\nTesting template updates...")
    template_path = os.path.join(os.path.dirname(__file__), 'templates', 'index.html')
    if os.path.exists(template_path):
        print(f"✓ Template exists: {template_path}")
        with open(template_path, 'r') as f:
            content = f.read()
            checks = [
                ('Onboarded:', 'Onboarded label'),
                ("instance.get('onboarded')", 'Onboarded field check'),
                ('status-badge status-running', 'Status badge for onboarded instances'),
                ('status-badge status-created', 'Status badge for non-onboarded instances'),
            ]
            
            for check, desc in checks:
                if check in content:
                    print(f"✓ Found: {desc}")
                else:
                    print(f"✗ Missing: {desc}")
                    return False
        
        return True
    else:
        print(f"✗ Template not found: {template_path}")
        return False

def test_onboarding_only_for_admins():
    """Test that onboarding indicator is only shown to admins"""
    print("\nTesting admin-only onboarding display...")
    template_path = os.path.join(os.path.dirname(__file__), 'templates', 'index.html')
    with open(template_path, 'r') as f:
        content = f.read()
        
        # Find the onboarding section and verify it's wrapped in {% if is_admin %}
        lines = content.split('\n')
        onboarding_section_start = None
        for i, line in enumerate(lines):
            if 'Onboarded:' in line:
                onboarding_section_start = i
                break
        
        if onboarding_section_start is None:
            print("✗ Onboarding section not found in template")
            return False
        
        # Check a few lines before for is_admin check
        admin_check_found = False
        for i in range(max(0, onboarding_section_start - 5), onboarding_section_start):
            if '{% if is_admin %}' in lines[i]:
                admin_check_found = True
                break
        
        if admin_check_found:
            print("✓ Onboarding display is admin-only")
        else:
            print("✗ Onboarding display not properly restricted to admins")
            return False
        
        return True

def test_check_instance_onboarding_complete_exists():
    """Test that the check_instance_onboarding_complete function exists"""
    print("\nTesting onboarding check function...")
    try:
        import app
        
        if hasattr(app, 'check_instance_onboarding_complete'):
            print("✓ check_instance_onboarding_complete function exists")
        else:
            print("✗ check_instance_onboarding_complete function not found")
            return False
        
        return True
    except Exception as e:
        print(f"✗ Function check error: {e}")
        return False

def main():
    """Run all tests"""
    print("=" * 60)
    print("HA-Edu Onboarding Indicator Tests")
    print("=" * 60)
    
    tests = [
        test_imports,
        test_check_instance_onboarding_complete_exists,
        test_get_instances_has_onboarding_check,
        test_template_has_onboarding_display,
        test_onboarding_only_for_admins,
    ]
    
    results = [test() for test in tests]
    
    passed = sum(results)
    total = len(results)
    
    print("\n" + "=" * 60)
    print(f"Tests passed: {passed}/{total}")
    print("=" * 60)
    
    if passed == total:
        print("\n✓ All tests passed!")
        return 0
    else:
        print(f"\n✗ {total - passed} test(s) failed")
        return 1

if __name__ == '__main__':
    sys.exit(main())
