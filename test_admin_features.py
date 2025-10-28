#!/usr/bin/env python3
"""
Test script for the admin features (delete all and toggle instance creation)
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

def test_app_routes():
    """Test that new API routes are registered"""
    print("\nTesting new API routes...")
    try:
        import app
        
        # Check if new routes are registered
        routes = [rule.rule for rule in app.app.url_map.iter_rules()]
        
        expected_routes = [
            ('/api/instances/delete-all', 'delete all instances'),
            ('/api/settings/instance-creation', 'toggle instance creation')
        ]
        
        for route, desc in expected_routes:
            if any(route in r for r in routes):
                print(f"✓ Route registered: {desc}")
            else:
                print(f"✗ Route missing: {desc}")
                return False
        
        return True
    except Exception as e:
        print(f"✗ App routes error: {e}")
        return False

def test_helper_functions():
    """Test helper functions for settings"""
    print("\nTesting helper functions...")
    try:
        import app
        
        # Test that functions exist
        functions = ['load_data', 'save_data', 'load_settings', 'save_settings']
        for func in functions:
            if hasattr(app, func):
                print(f"✓ Function exists: {func}")
            else:
                print(f"✗ Function missing: {func}")
                return False
        
        return True
    except Exception as e:
        print(f"✗ Function test error: {e}")
        return False

def test_templates():
    """Test that templates contain new elements"""
    print("\nTesting template updates...")
    template_path = os.path.join(os.path.dirname(__file__), 'templates', 'index.html')
    if os.path.exists(template_path):
        print(f"✓ Template exists: {template_path}")
        # Check for key HTML elements
        with open(template_path, 'r') as f:
            content = f.read()
            checks = [
                ('deleteAllBtn', 'Delete All button'),
                ('instanceCreationToggle', 'Instance creation toggle'),
                ('deleteAllModal', 'Delete All modal'),
                ('toggleModal', 'Toggle modal'),
                ('deleteAllInstancesForm', 'Delete All form'),
                ('toggleInstanceCreationForm', 'Toggle form'),
                ('openDeleteAllModal', 'Delete All function'),
                ('checkInstanceCreationStatus', 'Instance creation status check'),
                ('/api/instances/delete-all', 'Delete All API endpoint'),
                ('/api/settings/instance-creation', 'Settings API endpoint'),
                ('toggle-container', 'Toggle container CSS'),
                ('toggle-slider', 'Toggle slider CSS'),
                ('btn-delete-all', 'Delete All button CSS'),
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

def test_create_instance_check():
    """Test that create instance checks for enabled flag"""
    print("\nTesting instance creation check...")
    try:
        import app
        
        # Read the app.py file to check for the instance creation check
        app_path = os.path.join(os.path.dirname(__file__), 'app.py')
        with open(app_path, 'r') as f:
            content = f.read()
            
            if 'instance_creation_enabled' in content:
                print("✓ Instance creation enabled check found in code")
            else:
                print("✗ Instance creation enabled check not found")
                return False
            
            # Check for 403 error when disabled
            if "return jsonify({'error': 'Instance creation is currently disabled'}), 403" in content:
                print("✓ Proper error response when disabled")
            else:
                print("✗ Missing error response when disabled")
                return False
        
        return True
    except Exception as e:
        print(f"✗ Instance creation check error: {e}")
        return False

def main():
    """Run all tests"""
    print("=" * 60)
    print("HA-Edu Admin Features Tests")
    print("=" * 60)
    
    tests = [
        test_imports,
        test_app_routes,
        test_helper_functions,
        test_templates,
        test_create_instance_check,
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
