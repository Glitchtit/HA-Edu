#!/usr/bin/env python3
"""
Final verification script - demonstrates the complete admin access control workflow
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def main():
    print("="*80)
    print("HA-Edu Admin Access Control - Final Verification")
    print("="*80)
    
    print("\n1. Configuration Check")
    print("-" * 80)
    
    # Set up environment
    os.environ['ADMINS'] = 'admin@example.com,teacher@example.com'
    os.environ['ADMIN_PASSWORD'] = 'test123'
    
    import importlib
    import app as app_module
    importlib.reload(app_module)
    
    print(f"✓ ADMIN_PASSWORD configured: {'***' if app_module.ADMIN_PASSWORD else 'Not set'}")
    print(f"✓ ADMINS configured: {app_module.ADMINS}")
    print(f"✓ is_admin_user function exists: {hasattr(app_module, 'is_admin_user')}")
    
    print("\n2. API Endpoint Check")
    print("-" * 80)
    
    routes = [rule.rule for rule in app_module.app.url_map.iter_rules()]
    if '/api/admin/check-access' in routes:
        print("✓ /api/admin/check-access endpoint registered")
    else:
        print("✗ /api/admin/check-access endpoint NOT found")
        return 1
    
    print("\n3. Access Control Test Matrix")
    print("-" * 80)
    print(f"{'Scenario':<40} {'IP Address':<20} {'Email':<25} {'Access':<10}")
    print("-" * 80)
    
    from unittest.mock import Mock
    
    test_cases = [
        ("Local network user", "192.168.50.100", None, True),
        ("Remote user (no auth)", "203.0.113.50", None, False),
        ("Cloudflare admin user", "203.0.113.50", "admin@example.com", True),
        ("Cloudflare student user", "203.0.113.50", "student@example.com", False),
        ("X-Forwarded-For local", "10.0.0.1", None, True, "192.168.50.200"),
        ("Case-insensitive email", "203.0.113.50", "Admin@Example.COM", True),
    ]
    
    all_passed = True
    for test_case in test_cases:
        if len(test_case) == 5:
            scenario, ip, email, expected, xff = test_case
        else:
            scenario, ip, email, expected = test_case
            xff = None
        
        request = Mock()
        request.remote_addr = ip
        headers = {}
        if email:
            headers['Cf-Access-Authenticated-User-Email'] = email
        if xff:
            headers['X-Forwarded-For'] = xff
            ip = f"{xff} (via proxy)"
        request.headers = headers
        
        result = app_module.is_admin_user(request)
        status = "✓ GRANTED" if result else "✗ DENIED"
        
        if result != expected:
            status = f"⚠ FAIL (expected {'GRANTED' if expected else 'DENIED'})"
            all_passed = False
        
        print(f"{scenario:<40} {ip:<20} {email or 'None':<25} {status:<10}")
    
    print("\n4. Frontend Integration Check")
    print("-" * 80)
    
    template_path = os.path.join(os.path.dirname(__file__), 'templates', 'index.html')
    with open(template_path, 'r') as f:
        content = f.read()
        
        checks = [
            ('checkAdminEnabled', 'Admin check function'),
            ('has_admin_access', 'Admin access variable'),
            ('/api/admin/check-access', 'API endpoint call'),
            ('unlockAdminBtn', 'Unlock button element'),
            ('classList.remove(\'hidden\')', 'Show button logic'),
        ]
        
        for check, desc in checks:
            if check in content:
                print(f"✓ {desc}: Found")
            else:
                print(f"✗ {desc}: Missing")
                all_passed = False
    
    print("\n5. Documentation Check")
    print("-" * 80)
    
    readme_path = os.path.join(os.path.dirname(__file__), 'README.md')
    with open(readme_path, 'r') as f:
        content = f.read()
        
        if 'ADMINS' in content and 'Cloudflare Zero Trust' in content:
            print("✓ README.md updated with ADMINS documentation")
        else:
            print("✗ README.md missing ADMINS documentation")
            all_passed = False
    
    env_example_path = os.path.join(os.path.dirname(__file__), '.env.example')
    with open(env_example_path, 'r') as f:
        content = f.read()
        
        if 'ADMINS=' in content:
            print("✓ .env.example updated with ADMINS variable")
        else:
            print("✗ .env.example missing ADMINS variable")
            all_passed = False
    
    print("\n" + "="*80)
    if all_passed:
        print("✅ ALL VERIFICATION CHECKS PASSED")
        print("="*80)
        print("\nThe admin access control feature is fully implemented and working correctly!")
        print("\nUsage:")
        print("  1. Set ADMIN_PASSWORD environment variable")
        print("  2. Set ADMINS=email1@example.com,email2@example.com")
        print("  3. Local users (192.168.50.x) automatically get admin access")
        print("  4. Cloudflare authenticated users with approved emails get admin access")
        print("  5. All other users will not see admin buttons")
        return 0
    else:
        print("❌ SOME VERIFICATION CHECKS FAILED")
        print("="*80)
        return 1

if __name__ == '__main__':
    sys.exit(main())
