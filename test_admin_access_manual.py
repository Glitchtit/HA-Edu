#!/usr/bin/env python3
"""
Manual test script to verify admin access control functionality
This script simulates different access scenarios and tests the API responses
"""

import sys
import os
import json
from unittest.mock import Mock

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_scenario(scenario_name, remote_addr, cf_email=None, x_forwarded_for=None, admin_emails=''):
    """Test a specific access scenario"""
    print(f"\n{'='*70}")
    print(f"Scenario: {scenario_name}")
    print(f"{'='*70}")
    print(f"Remote IP: {remote_addr}")
    print(f"X-Forwarded-For: {x_forwarded_for}")
    print(f"Cloudflare Email: {cf_email}")
    print(f"ADMINS List: {admin_emails}")
    print(f"{'-'*70}")
    
    # Set up environment
    os.environ['ADMINS'] = admin_emails
    os.environ['ADMIN_PASSWORD'] = 'test123'
    
    # Reload app module to pick up new env vars
    import importlib
    import app as app_module
    importlib.reload(app_module)
    
    # Create mock request
    request = Mock()
    request.remote_addr = remote_addr
    
    # Set up headers
    headers = {}
    if x_forwarded_for:
        headers['X-Forwarded-For'] = x_forwarded_for
    if cf_email:
        headers['Cf-Access-Authenticated-User-Email'] = cf_email
    
    request.headers = headers
    
    # Check admin access
    has_access = app_module.is_admin_user(request)
    
    print(f"Result: {'✓ ADMIN ACCESS GRANTED' if has_access else '✗ ADMIN ACCESS DENIED'}")
    print(f"{'='*70}")
    
    return has_access

def main():
    """Run manual test scenarios"""
    print("="*70)
    print("HA-Edu Admin Access Control - Manual Test Scenarios")
    print("="*70)
    
    scenarios = []
    
    # Scenario 1: Local network access (192.168.50.x)
    result = test_scenario(
        "Local Network Access (192.168.50.100)",
        remote_addr='192.168.50.100',
        admin_emails=''
    )
    scenarios.append(('Local IP (no ADMINS)', result, True))
    
    # Scenario 2: Remote access without authentication
    result = test_scenario(
        "Remote Access Without Authentication",
        remote_addr='203.0.113.50',
        admin_emails=''
    )
    scenarios.append(('Remote IP (no auth)', result, False))
    
    # Scenario 3: Cloudflare authenticated user in ADMINS list
    result = test_scenario(
        "Cloudflare Authenticated User (Approved)",
        remote_addr='203.0.113.50',
        cf_email='admin@example.com',
        admin_emails='admin@example.com,teacher@example.com'
    )
    scenarios.append(('Cloudflare approved email', result, True))
    
    # Scenario 4: Cloudflare authenticated user NOT in ADMINS list
    result = test_scenario(
        "Cloudflare Authenticated User (Not Approved)",
        remote_addr='203.0.113.50',
        cf_email='student@example.com',
        admin_emails='admin@example.com,teacher@example.com'
    )
    scenarios.append(('Cloudflare unapproved email', result, False))
    
    # Scenario 5: X-Forwarded-For with local IP (behind reverse proxy)
    result = test_scenario(
        "Behind Reverse Proxy with Local IP",
        remote_addr='10.0.0.1',
        x_forwarded_for='192.168.50.200, 10.0.0.1',
        admin_emails=''
    )
    scenarios.append(('X-Forwarded-For local IP', result, True))
    
    # Scenario 6: X-Forwarded-For with remote IP
    result = test_scenario(
        "Behind Reverse Proxy with Remote IP",
        remote_addr='10.0.0.1',
        x_forwarded_for='203.0.113.99, 10.0.0.1',
        admin_emails=''
    )
    scenarios.append(('X-Forwarded-For remote IP', result, False))
    
    # Scenario 7: Case-insensitive email matching
    result = test_scenario(
        "Cloudflare Email (Case Insensitive)",
        remote_addr='203.0.113.50',
        cf_email='Admin@Example.COM',
        admin_emails='admin@example.com'
    )
    scenarios.append(('Case-insensitive email', result, True))
    
    # Scenario 8: Different subnet (192.168.51.x)
    result = test_scenario(
        "Different Local Subnet (192.168.51.100)",
        remote_addr='192.168.51.100',
        admin_emails=''
    )
    scenarios.append(('Different subnet', result, False))
    
    # Print summary
    print("\n" + "="*70)
    print("TEST SUMMARY")
    print("="*70)
    
    passed = 0
    failed = 0
    
    for name, actual, expected in scenarios:
        status = "✓ PASS" if actual == expected else "✗ FAIL"
        if actual == expected:
            passed += 1
        else:
            failed += 1
        
        print(f"{status}: {name}")
        if actual != expected:
            print(f"        Expected: {expected}, Got: {actual}")
    
    print("="*70)
    print(f"Total: {passed} passed, {failed} failed")
    print("="*70)
    
    return 0 if failed == 0 else 1

if __name__ == '__main__':
    sys.exit(main())
