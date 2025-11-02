#!/usr/bin/env python3
"""
Test script for admin access control based on IP address and Cloudflare email.
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
        from flask import Flask, request
        print("✓ All dependencies imported successfully")
        return True
    except ImportError as e:
        print(f"✗ Import error: {e}")
        return False

def test_admin_env_variable():
    """Test that ADMINS environment variable is loaded"""
    print("\nTesting ADMINS environment variable...")
    try:
        import app
        
        # Check if ADMINS variable exists
        if hasattr(app, 'ADMINS'):
            print("✓ ADMINS variable exists in app module")
            print(f"  Current value: '{app.ADMINS}'")
            return True
        else:
            print("✗ ADMINS variable not found in app module")
            return False
    except Exception as e:
        print(f"✗ Environment variable test error: {e}")
        return False

def test_is_admin_user_function():
    """Test that is_admin_user function exists"""
    print("\nTesting is_admin_user function...")
    try:
        import app
        
        if hasattr(app, 'is_admin_user'):
            print("✓ is_admin_user function exists")
            
            # Check function signature
            import inspect
            sig = inspect.signature(app.is_admin_user)
            if 'request' in sig.parameters:
                print("✓ Function has correct signature (accepts request)")
            else:
                print("✗ Function signature incorrect")
                return False
            
            return True
        else:
            print("✗ is_admin_user function not found")
            return False
    except Exception as e:
        print(f"✗ Function test error: {e}")
        return False

def test_admin_check_access_route():
    """Test that admin check-access route is registered"""
    print("\nTesting /api/admin/check-access route...")
    try:
        import app
        
        # Check if new route is registered
        routes = [rule.rule for rule in app.app.url_map.iter_rules()]
        
        if '/api/admin/check-access' in routes:
            print("✓ Route registered: /api/admin/check-access")
            return True
        else:
            print("✗ Route /api/admin/check-access not found")
            print(f"  Available routes: {[r for r in routes if 'admin' in r]}")
            return False
    except Exception as e:
        print(f"✗ Route test error: {e}")
        return False

def test_ip_parsing_logic():
    """Test the IP address parsing logic"""
    print("\nTesting IP address parsing logic...")
    try:
        # Test IP address pattern
        test_ips = [
            ('192.168.50.1', True, 'Valid local IP'),
            ('192.168.50.255', True, 'Valid local IP (broadcast)'),
            ('192.168.51.1', False, 'Different subnet'),
            ('10.0.0.1', False, 'Different network'),
            ('192.168.50.1.1', False, 'Invalid IP format'),
        ]
        
        all_passed = True
        for ip, should_match, desc in test_ips:
            try:
                ip_parts = ip.split('.')
                matches = (len(ip_parts) == 4 and 
                          ip_parts[0] == '192' and 
                          ip_parts[1] == '168' and 
                          ip_parts[2] == '50')
                
                if matches == should_match:
                    print(f"✓ {desc}: {ip} -> {matches}")
                else:
                    print(f"✗ {desc}: {ip} -> {matches} (expected {should_match})")
                    all_passed = False
            except Exception as e:
                print(f"✗ Error parsing {ip}: {e}")
                all_passed = False
        
        return all_passed
    except Exception as e:
        print(f"✗ IP parsing test error: {e}")
        return False

def test_email_list_parsing():
    """Test email list parsing from ADMINS variable"""
    print("\nTesting email list parsing...")
    try:
        test_cases = [
            ('admin@example.com,user@test.com', ['admin@example.com', 'user@test.com']),
            ('admin@example.com', ['admin@example.com']),
            ('admin@example.com, user@test.com , test@demo.com', 
             ['admin@example.com', 'user@test.com', 'test@demo.com']),
            ('', []),
        ]
        
        all_passed = True
        for admins_str, expected in test_cases:
            result = [email.strip().lower() for email in admins_str.split(',') if email.strip()]
            if result == expected:
                print(f"✓ Parsing '{admins_str}' -> {result}")
            else:
                print(f"✗ Parsing '{admins_str}' -> {result} (expected {expected})")
                all_passed = False
        
        return all_passed
    except Exception as e:
        print(f"✗ Email parsing test error: {e}")
        return False

def test_env_example_updated():
    """Test that .env.example contains ADMINS variable"""
    print("\nTesting .env.example file...")
    env_example_path = os.path.join(os.path.dirname(__file__), '.env.example')
    
    if os.path.exists(env_example_path):
        print(f"✓ .env.example exists at {env_example_path}")
        
        with open(env_example_path, 'r', encoding='utf-8') as f:
            content = f.read()
            
            if 'ADMINS=' in content:
                print("✓ ADMINS variable found in .env.example")
                
                # Check for documentation
                if 'email' in content.lower() and 'comma' in content.lower():
                    print("✓ ADMINS variable has proper documentation")
                    return True
                else:
                    print("⚠ ADMINS variable could use better documentation")
                    return True
            else:
                print("✗ ADMINS variable not found in .env.example")
                return False
    else:
        print(f"✗ .env.example not found at {env_example_path}")
        return False

def test_frontend_updated():
    """Test that index.html has been updated with new admin check"""
    print("\nTesting frontend updates...")
    template_path = os.path.join(os.path.dirname(__file__), 'templates', 'index.html')
    
    if os.path.exists(template_path):
        print(f"✓ Template exists at {template_path}")
        
        with open(template_path, 'r', encoding='utf-8') as f:
            content = f.read()
            
            checks = [
                ('/api/admin/check-access', 'New admin check-access endpoint'),
                ('has_admin_access', 'Admin access check variable'),
                ('admin_password_enabled', 'Admin password enabled check'),
            ]
            
            all_passed = True
            for check, desc in checks:
                if check in content:
                    print(f"✓ Found: {desc}")
                else:
                    print(f"✗ Missing: {desc}")
                    all_passed = False
            
            return all_passed
    else:
        print(f"✗ Template not found at {template_path}")
        return False

def main():
    """Run all tests"""
    print("=" * 70)
    print("HA-Edu Admin Access Control Tests")
    print("=" * 70)
    
    tests = [
        test_imports,
        test_admin_env_variable,
        test_is_admin_user_function,
        test_admin_check_access_route,
        test_ip_parsing_logic,
        test_email_list_parsing,
        test_env_example_updated,
        test_frontend_updated,
    ]
    
    results = [test() for test in tests]
    
    passed = sum(results)
    total = len(results)
    
    print("\n" + "=" * 70)
    print(f"Tests passed: {passed}/{total}")
    print("=" * 70)
    
    if passed == total:
        print("\n✓ All tests passed!")
        return 0
    else:
        print(f"\n✗ {total - passed} test(s) failed")
        return 1

if __name__ == '__main__':
    sys.exit(main())
