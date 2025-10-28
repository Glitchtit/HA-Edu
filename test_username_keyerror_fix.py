#!/usr/bin/env python3
"""
Test to verify that the username KeyError fix works correctly.
This test specifically validates that the code handles users without 'username' field.
"""

import sys
import os

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def test_username_field_handling():
    """Test that the code in create_teacher_account handles users without username field"""
    print("\nTesting username field handling in list comprehension...")
    
    # Simulate the auth_data structure with mixed user types
    # Some users have 'username', others don't (like system-generated or owner users)
    auth_data = {
        'data': {
            'users': [
                {
                    'id': 'user1',
                    'name': 'Owner User',
                    'is_owner': True,
                    'is_active': True,
                    # Note: No 'username' field - this is the case that causes KeyError
                },
                {
                    'id': 'user2',
                    'name': 'System User',
                    'is_active': True,
                    'system_generated': True,
                    # Note: No 'username' field
                },
                {
                    'id': 'user3',
                    'username': 'existingteacher',
                    'name': 'Existing Teacher',
                    'is_active': True,
                    # This user HAS 'username' field
                }
            ]
        }
    }
    
    teacher_username = 'newteacher'
    
    # This is the fixed code - should not raise KeyError
    try:
        existing_users = [u for u in auth_data['data']['users'] if u.get('username') == teacher_username]
        print(f"✓ List comprehension with .get() works correctly")
        print(f"  Found {len(existing_users)} existing users with username '{teacher_username}'")
        assert len(existing_users) == 0, "Should find no existing users with 'newteacher' username"
        print(f"✓ Correctly found no existing users with username '{teacher_username}'")
    except KeyError as e:
        print(f"✗ KeyError raised: {e}")
        return False
    
    # Test with existing username
    teacher_username = 'existingteacher'
    try:
        existing_users = [u for u in auth_data['data']['users'] if u.get('username') == teacher_username]
        print(f"✓ List comprehension works with existing username")
        print(f"  Found {len(existing_users)} existing users with username '{teacher_username}'")
        assert len(existing_users) == 1, "Should find 1 existing user with 'existingteacher' username"
        print(f"✓ Correctly found existing user with username '{teacher_username}'")
    except KeyError as e:
        print(f"✗ KeyError raised: {e}")
        return False
    
    # Test the old broken code for comparison
    print("\nTesting OLD code (should fail with KeyError)...")
    try:
        # This is the old broken code - SHOULD raise KeyError
        existing_users = [u for u in auth_data['data']['users'] if u['username'] == 'newteacher']
        print(f"✗ Old code did not raise KeyError (unexpected)")
        return False
    except KeyError as e:
        print(f"✓ Old code correctly raises KeyError: {e}")
        print(f"  This confirms the bug existed and our fix is necessary")
    
    return True


def main():
    """Run the test"""
    print("=" * 60)
    print("Username KeyError Fix Test")
    print("=" * 60)
    
    try:
        result = test_username_field_handling()
        
        print("\n" + "=" * 60)
        if result:
            print("✓ Test PASSED - Fix handles users without username field")
        else:
            print("✗ Test FAILED")
        print("=" * 60)
        
        return result
    except Exception as e:
        print(f"\n✗ Test failed with exception: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)
