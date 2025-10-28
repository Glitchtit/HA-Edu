#!/usr/bin/env python3
"""
Test script to verify password-related changes in the HA-Edu application
This tests that:
1. Creating instances no longer requires a password
2. Deleting instances requires admin password
3. Resetting instances requires admin password
"""

import sys
import os

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_create_instance_no_password():
    """Test that create_instance doesn't require password in code"""
    print("\nTesting create instance (no password required)...")
    try:
        with open('app.py', 'r') as f:
            content = f.read()
            
        # Check that create_instance doesn't validate password
        create_func_start = content.find('def create_instance():')
        create_func_end = content.find('\n@app.route', create_func_start + 1)
        create_func = content[create_func_start:create_func_end]
        
        # Should not have password validation
        if "password = data.get('password'" in create_func:
            print("✗ Password extraction still present in create_instance")
            return False
        print("✓ Password extraction removed from create_instance")
        
        # Should only require server_name
        if 'if not server_name:' in create_func:
            print("✓ Only server_name is required for creation")
        else:
            print("✗ Unexpected validation logic in create_instance")
            return False
        
        # Check that password is not stored
        if "'password': password" in create_func or '"password": password' in create_func:
            print("✗ Password still being stored in instance data")
            return False
        print("✓ Password not stored in instance data")
        
        return True
    except Exception as e:
        print(f"✗ Test error: {e}")
        return False

def test_delete_requires_admin_password():
    """Test that delete_instance requires admin password"""
    print("\nTesting delete instance (admin password required)...")
    try:
        with open('app.py', 'r') as f:
            content = f.read()
        
        # Find delete_instance function
        delete_func_start = content.find('def delete_instance(')
        delete_func_end = content.find('\n@app.route', delete_func_start + 1)
        if delete_func_end == -1:
            delete_func_end = content.find('\ndef ', delete_func_start + 1)
        delete_func = content[delete_func_start:delete_func_end]
        
        # Should check for ADMIN_PASSWORD
        if 'if not ADMIN_PASSWORD:' in delete_func:
            print("✓ Admin password configuration check present")
        else:
            print("✗ Missing admin password configuration check")
            return False
        
        # Should validate admin password
        if 'secrets.compare_digest(admin_password, ADMIN_PASSWORD)' in delete_func:
            print("✓ Admin password validation present")
        else:
            print("✗ Missing admin password validation")
            return False
        
        # Should return 401 on invalid password
        if "'Invalid admin password'" in delete_func or '"Invalid admin password"' in delete_func:
            print("✓ Invalid password error message present")
        else:
            print("✗ Missing invalid password error handling")
            return False
        
        return True
    except Exception as e:
        print(f"✗ Test error: {e}")
        return False

def test_reset_requires_admin_password():
    """Test that reset_instance requires admin password (existing feature)"""
    print("\nTesting reset instance (admin password required)...")
    try:
        with open('app.py', 'r') as f:
            content = f.read()
        
        # Find reset_instance function
        reset_func_start = content.find('def reset_instance(')
        reset_func_end = content.find('\n@app.route', reset_func_start + 1)
        if reset_func_end == -1:
            reset_func_end = content.find('\nif __name__', reset_func_start + 1)
        reset_func = content[reset_func_start:reset_func_end]
        
        # Should check for ADMIN_PASSWORD
        if 'if not ADMIN_PASSWORD:' in reset_func:
            print("✓ Admin password configuration check present")
        else:
            print("✗ Missing admin password configuration check")
            return False
        
        # Should validate admin password
        if 'secrets.compare_digest(admin_password, ADMIN_PASSWORD)' in reset_func:
            print("✓ Admin password validation present")
        else:
            print("✗ Missing admin password validation")
            return False
        
        return True
    except Exception as e:
        print(f"✗ Test error: {e}")
        return False

def test_ui_changes():
    """Test that UI reflects the password changes"""
    print("\nTesting UI changes...")
    try:
        with open('templates/index.html', 'r') as f:
            content = f.read()
        
        # Check that create form doesn't have password field
        add_modal_start = content.find('id="addModal"')
        add_modal_end = content.find('</div>', content.find('</form>', add_modal_start))
        add_modal = content[add_modal_start:add_modal_end]
        
        if 'id="password"' in add_modal or 'name="password"' in add_modal:
            print("✗ Password field still present in create form")
            return False
        print("✓ Password field removed from create form")
        
        # Check that delete modal exists
        if 'id="deleteModal"' in content:
            print("✓ Delete modal present")
        else:
            print("✗ Delete modal missing")
            return False
        
        # Check that delete modal has admin password field
        if 'id="deleteAdminPassword"' in content:
            print("✓ Admin password field in delete modal")
        else:
            print("✗ Admin password field missing from delete modal")
            return False
        
        # Check JavaScript for delete function
        if 'function deleteInstance(serverName)' in content:
            print("✓ Delete function present")
        else:
            print("✗ Delete function missing")
            return False
        
        # Check that create instance doesn't send password
        if "getElementById('addInstanceForm')" in content:
            form_handler_start = content.find("getElementById('addInstanceForm')")
            # Find the end of this event listener function
            brace_count = 0
            in_listener = False
            form_handler_end = form_handler_start
            
            for i in range(form_handler_start, len(content)):
                char = content[i]
                if char == '{':
                    brace_count += 1
                    in_listener = True
                elif char == '}' and in_listener:
                    brace_count -= 1
                    if brace_count == 0:
                        form_handler_end = i
                        break
            
            create_form_handler = content[form_handler_start:form_handler_end]
            
            if 'password:' in create_form_handler.lower():
                print("✗ Password still being sent in create request")
                return False
            print("✓ Password not sent in create request")
        else:
            print("✗ Create form handler not found")
            return False
        
        return True
    except Exception as e:
        print(f"✗ Test error: {e}")
        return False

def main():
    """Run all password change tests"""
    print("=" * 60)
    print("HA-Edu Password Change Tests")
    print("=" * 60)
    
    tests = [
        test_create_instance_no_password,
        test_delete_requires_admin_password,
        test_reset_requires_admin_password,
        test_ui_changes
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
        print("\n✓ All password change tests passed!")
        return 0
    else:
        print("\n✗ Some tests failed")
        return 1

if __name__ == '__main__':
    sys.exit(main())
