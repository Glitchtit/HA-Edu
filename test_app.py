#!/usr/bin/env python3
"""
Simple test script to verify the HA-Edu application functionality
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

def test_app_structure():
    """Test that the Flask app is properly structured"""
    print("\nTesting application structure...")
    try:
        import app
        
        # Check if Flask app exists
        if not hasattr(app, 'app'):
            print("✗ Flask app not found")
            return False
        print("✓ Flask app initialized")
        
        # Check if routes are registered
        routes = [rule.rule for rule in app.app.url_map.iter_rules()]
        expected_routes = [
            ('/', 'index'),
            ('/api/instances', 'api instances'),
            ('/api/instances/<', 'api instance operations')
        ]
        
        for route, desc in expected_routes:
            if any(route in r for r in routes):
                print(f"✓ Route registered: {desc}")
            else:
                print(f"✗ Route missing: {desc}")
                return False
        
        return True
    except Exception as e:
        print(f"✗ App structure error: {e}")
        return False

def test_functions():
    """Test helper functions"""
    print("\nTesting helper functions...")
    try:
        import app
        
        # Test port calculation
        app.BASE_PORT = 8123
        
        print(f"✓ BASE_PORT: {app.BASE_PORT}")
        
        # Test that functions exist
        functions = ['load_instances', 'save_instances', 'get_available_port']
        for func in functions:
            if hasattr(app, func):
                print(f"✓ Function exists: {func}")
            else:
                print(f"✗ Function missing: {func}")
                return False
        
        # Test that MAX_INSTANCES exists and is configurable
        if hasattr(app, 'MAX_INSTANCES'):
            print(f"✓ MAX_INSTANCES exists (configurable limit): {app.MAX_INSTANCES}")
        else:
            print("✗ MAX_INSTANCES not found (should exist)")
            return False
        
        return True
    except Exception as e:
        print(f"✗ Function test error: {e}")
        return False

def test_templates():
    """Test that templates exist"""
    print("\nTesting templates...")
    template_path = os.path.join(os.path.dirname(__file__), 'templates', 'index.html')
    if os.path.exists(template_path):
        print(f"✓ Template exists: {template_path}")
        # Check for key HTML elements
        with open(template_path, 'r') as f:
            content = f.read()
            checks = [
                ('Skapa ny instans', 'Add New button'),
                ('server_name', 'Server name field'),
                ('modal', 'Modal dialog'),
                ('/api/instances', 'API endpoint reference'),
                ('deleteModal', 'Delete modal dialog'),
                ('deleteAllAdminPassword', 'Delete admin password field')
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

def test_dockerfile():
    """Test that Dockerfile exists and has required content"""
    print("\nTesting Dockerfile...")
    dockerfile_path = os.path.join(os.path.dirname(__file__), 'Dockerfile')
    if os.path.exists(dockerfile_path):
        print(f"✓ Dockerfile exists: {dockerfile_path}")
        with open(dockerfile_path, 'r') as f:
            content = f.read()
            checks = [
                ('FROM python', 'Base image'),
                ('requirements.txt', 'Requirements installation'),
                ('EXPOSE 5000', 'Port exposure'),
                ('CMD', 'Container command')
            ]
            for check, desc in checks:
                if check in content:
                    print(f"✓ Found: {desc}")
                else:
                    print(f"✗ Missing: {desc}")
                    return False
        return True
    else:
        print(f"✗ Dockerfile not found: {dockerfile_path}")
        return False

def test_admin_password_feature():
    """Test admin password functionality"""
    print("\nTesting admin password feature...")
    try:
        import app
        
        # Check if ADMIN_PASSWORD config exists
        if hasattr(app, 'ADMIN_PASSWORD'):
            print("✓ ADMIN_PASSWORD configuration exists")
        else:
            print("✗ ADMIN_PASSWORD configuration missing")
            return False
        
        # Check if reset route exists
        routes = [rule.rule for rule in app.app.url_map.iter_rules()]
        if any('/reset' in r for r in routes):
            print("✓ Reset endpoint registered")
        else:
            print("✗ Reset endpoint missing")
            return False
        
        # Check if admin check route exists
        if any('/admin/check' in r for r in routes):
            print("✓ Admin check endpoint registered")
        else:
            print("✗ Admin check endpoint missing")
            return False
        
        # Check template for reset functionality
        template_path = os.path.join(os.path.dirname(__file__), 'templates', 'index.html')
        with open(template_path, 'r') as f:
            content = f.read()
            checks = [
                ('btn-reset', 'Reset button styling'),
                ('resetInstance', 'Reset function'),
                ('resetModal', 'Reset modal'),
                ('adminPassword', 'Admin password field'),
                ('checkAdminEnabled', 'Admin check function')
            ]
            for check, desc in checks:
                if check in content:
                    print(f"✓ Found: {desc}")
                else:
                    print(f"✗ Missing: {desc}")
                    return False
        
        # Check .env.example for ADMIN_PASSWORD
        env_path = os.path.join(os.path.dirname(__file__), '.env.example')
        with open(env_path, 'r') as f:
            content = f.read()
            if 'ADMIN_PASSWORD' in content:
                print("✓ ADMIN_PASSWORD in .env.example")
            else:
                print("✗ ADMIN_PASSWORD missing in .env.example")
                return False
        
        return True
    except Exception as e:
        print(f"✗ Admin password feature test error: {e}")
        return False

def main():
    """Run all tests"""
    print("=" * 60)
    print("HA-Edu Application Tests")
    print("=" * 60)
    
    tests = [
        test_imports,
        test_app_structure,
        test_functions,
        test_templates,
        test_dockerfile,
        test_admin_password_feature
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
        print("\n✓ All tests passed!")
        return 0
    else:
        print("\n✗ Some tests failed")
        return 1

if __name__ == '__main__':
    sys.exit(main())
