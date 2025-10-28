#!/usr/bin/env python3
"""
Test script for the teacher access feature
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
        import bcrypt
        print("✓ All dependencies imported successfully")
        return True
    except ImportError as e:
        print(f"✗ Import error: {e}")
        return False

def test_app_configuration():
    """Test that teacher access configuration is loaded"""
    print("\nTesting teacher access configuration...")
    try:
        import app
        
        # Check that configuration variables exist
        assert hasattr(app, 'TEACHER_USERNAME'), "TEACHER_USERNAME not found"
        assert hasattr(app, 'TEACHER_PASSWORD'), "TEACHER_PASSWORD not found"
        
        print("✓ Configuration variables loaded")
        return True
    except Exception as e:
        print(f"✗ Configuration error: {e}")
        return False

def test_helper_functions():
    """Test that helper functions exist"""
    print("\nTesting helper functions...")
    try:
        import app
        
        functions = [
            ('check_instance_onboarding_complete', 'check onboarding status'),
            ('create_teacher_account', 'create teacher account'),
        ]
        
        for func_name, desc in functions:
            if hasattr(app, func_name):
                print(f"✓ Function exists: {desc}")
            else:
                print(f"✗ Function missing: {desc}")
                return False
        
        return True
    except Exception as e:
        print(f"✗ Helper functions error: {e}")
        return False

def test_api_routes():
    """Test that teacher access API routes are registered"""
    print("\nTesting teacher access API routes...")
    try:
        import app
        
        # Check if new routes are registered
        routes = [rule.rule for rule in app.app.url_map.iter_rules()]
        
        expected_routes = [
            ('teacher-access', 'check teacher access settings'),
            ('add-teacher-access', 'add teacher access')
        ]
        
        for route_part, desc in expected_routes:
            # Check if route pattern exists (handle dynamic parts)
            route_exists = any(route_part in r for r in routes)
            if route_exists:
                print(f"✓ Route registered: {desc}")
            else:
                print(f"✗ Route missing: {desc}")
                return False
        
        return True
    except Exception as e:
        print(f"✗ API routes error: {e}")
        return False

def test_template_updates():
    """Test that template has been updated with teacher access UI"""
    print("\nTesting template updates...")
    try:
        template_path = os.path.join(os.path.dirname(__file__), 'templates', 'index.html')
        
        if not os.path.exists(template_path):
            print(f"✗ Template not found: {template_path}")
            return False
        
        print(f"✓ Template exists: {template_path}")
        
        with open(template_path, 'r') as f:
            content = f.read()
        
        # Check for key elements
        checks = [
            ('btn-teacher-access', 'Teacher access button style'),
            ('teacher-access-badge', 'Teacher access badge style'),
            ('teacherAccessModal', 'Teacher access modal'),
            ('teacherAccessForm', 'Teacher access form'),
            ('checkTeacherAccessEnabled', 'Check teacher access function'),
            ('openTeacherAccessModal', 'Open teacher access modal function'),
            ('addTeacherAccess', 'Add teacher access function'),
            ('👨‍🏫', 'Teacher emoji icon'),
        ]
        
        for check, desc in checks:
            if check in content:
                print(f"✓ Found: {desc}")
            else:
                print(f"✗ Missing: {desc}")
                return False
        
        return True
    except Exception as e:
        print(f"✗ Template error: {e}")
        return False

def test_documentation_updates():
    """Test that documentation has been updated"""
    print("\nTesting documentation updates...")
    try:
        readme_path = os.path.join(os.path.dirname(__file__), 'README.md')
        quickstart_path = os.path.join(os.path.dirname(__file__), 'QUICKSTART.md')
        env_example_path = os.path.join(os.path.dirname(__file__), '.env.example')
        
        files_to_check = [
            (readme_path, 'README.md', ['Teacher Access', 'TEACHER_USERNAME', 'TEACHER_PASSWORD']),
            (quickstart_path, 'QUICKSTART.md', ['Teacher Access', 'TEACHER_USERNAME', 'TEACHER_PASSWORD']),
            (env_example_path, '.env.example', ['TEACHER_USERNAME', 'TEACHER_PASSWORD']),
        ]
        
        for file_path, file_name, keywords in files_to_check:
            if not os.path.exists(file_path):
                print(f"✗ File not found: {file_name}")
                return False
            
            with open(file_path, 'r') as f:
                content = f.read()
            
            for keyword in keywords:
                if keyword in content:
                    print(f"✓ {file_name}: Found '{keyword}'")
                else:
                    print(f"✗ {file_name}: Missing '{keyword}'")
                    return False
        
        return True
    except Exception as e:
        print(f"✗ Documentation error: {e}")
        return False

def main():
    """Run all tests"""
    print("=" * 60)
    print("HA-Edu Teacher Access Feature Tests")
    print("=" * 60)
    
    tests = [
        test_imports,
        test_app_configuration,
        test_helper_functions,
        test_api_routes,
        test_template_updates,
        test_documentation_updates,
    ]
    
    results = []
    for test in tests:
        try:
            result = test()
            results.append(result)
        except Exception as e:
            print(f"\n✗ Test failed with exception: {e}")
            results.append(False)
    
    print("\n" + "=" * 60)
    print(f"Results: {sum(results)}/{len(results)} tests passed")
    print("=" * 60)
    
    return all(results)

if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)
