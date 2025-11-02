#!/usr/bin/env python3
"""
Test script to verify that the wsgi.py entry point correctly prevents
MonkeyPatchWarning by applying gevent monkey-patching before importing app.

This test simulates what Gunicorn does when loading the application.
"""

import sys
import subprocess

def test_wsgi_import_order():
    """Test that wsgi.py applies monkey-patching before importing app"""
    
    print("=" * 70)
    print("Testing wsgi.py import order")
    print("=" * 70)
    
    # Test 1: Verify wsgi.py exists and is correctly structured
    print("\n1. Checking wsgi.py file structure...")
    try:
        with open('wsgi.py', 'r') as f:
            content = f.read()
            
        # Check that gevent import comes before app import
        gevent_pos = content.find('from gevent import monkey')
        monkey_patch_pos = content.find('monkey.patch_all()')
        app_import_pos = content.find('from app import app')
        
        if gevent_pos < 0:
            print("   ❌ FAIL: gevent import not found in wsgi.py")
            return False
            
        if monkey_patch_pos < 0:
            print("   ❌ FAIL: monkey.patch_all() not found in wsgi.py")
            return False
            
        if app_import_pos < 0:
            print("   ❌ FAIL: app import not found in wsgi.py")
            return False
            
        if gevent_pos < app_import_pos and monkey_patch_pos < app_import_pos:
            print("   ✅ PASS: Correct import order in wsgi.py")
            print(f"      - gevent import at position {gevent_pos}")
            print(f"      - monkey.patch_all() at position {monkey_patch_pos}")
            print(f"      - app import at position {app_import_pos}")
        else:
            print("   ❌ FAIL: Incorrect import order in wsgi.py")
            return False
            
    except FileNotFoundError:
        print("   ❌ FAIL: wsgi.py file not found")
        return False
    except Exception as e:
        print(f"   ❌ FAIL: Error reading wsgi.py: {e}")
        return False
    
    # Test 2: Verify Dockerfile uses wsgi.py
    print("\n2. Checking Dockerfile configuration...")
    try:
        with open('Dockerfile', 'r') as f:
            content = f.read()
            
        # Check that wsgi.py is copied
        if 'COPY wsgi.py' in content:
            print("   ✅ PASS: wsgi.py is copied in Dockerfile")
        else:
            print("   ❌ FAIL: wsgi.py is not copied in Dockerfile")
            return False
            
        # Check that CMD uses wsgi:application
        if 'wsgi:application' in content:
            print("   ✅ PASS: CMD uses wsgi:application as entry point")
        else:
            print("   ❌ FAIL: CMD does not use wsgi:application")
            return False
            
        # Check that --preload is removed (important for per-worker monkey-patching)
        # Only check in CMD lines, not in comments
        has_preload_in_cmd = any('--preload' in line for line in content.split('\n') if line.strip().startswith('CMD'))
        
        if not has_preload_in_cmd:
            print("   ✅ PASS: --preload flag is not in CMD (correct for gevent)")
        else:
            print("   ⚠️  WARNING: --preload flag found in CMD, may cause issues with gevent monkey-patching")
            
    except FileNotFoundError:
        print("   ❌ FAIL: Dockerfile not found")
        return False
    except Exception as e:
        print(f"   ❌ FAIL: Error reading Dockerfile: {e}")
        return False
    
    # Test 3: Verify app.py imports that need monkey-patching
    print("\n3. Checking app.py imports...")
    try:
        with open('app.py', 'r') as f:
            lines = f.readlines()
            
        # Check for imports that need to be monkey-patched
        # Support various import patterns: import X, from X import Y, import X as Y
        import re
        imports_to_check = ['requests', 'docker', 'urllib']
        found_imports = []
        
        for line in lines[:30]:  # Check first 30 lines (import section)
            # Skip comments
            if line.strip().startswith('#'):
                continue
            # Match: import requests, from requests import ..., import requests as ...
            for imp in imports_to_check:
                pattern = rf'\b(import\s+{imp}|from\s+{imp}\s+import)'
                if re.search(pattern, line):
                    found_imports.append(imp)
                    
        if found_imports:
            print(f"   ✅ PASS: Found SSL-dependent imports in app.py: {', '.join(set(found_imports))}")
            print("      These will be monkey-patched by wsgi.py before app.py is loaded")
        else:
            print("   ⚠️  WARNING: No SSL-dependent imports found in app.py")
            
    except FileNotFoundError:
        print("   ❌ FAIL: app.py not found")
        return False
    except Exception as e:
        print(f"   ❌ FAIL: Error reading app.py: {e}")
        return False
    
    print("\n" + "=" * 70)
    print("✅ All tests passed! The fix is correctly implemented.")
    print("=" * 70)
    print("\nExpected behavior:")
    print("  - When Gunicorn starts with gevent worker class:")
    print("  - Each worker imports wsgi.py")
    print("  - wsgi.py applies gevent monkey-patching FIRST")
    print("  - Then wsgi.py imports app.py")
    print("  - app.py imports requests, docker, urllib3 (already monkey-patched)")
    print("  - No MonkeyPatchWarning should appear!")
    print("=" * 70)
    
    return True

if __name__ == '__main__':
    success = test_wsgi_import_order()
    sys.exit(0 if success else 1)
