#!/usr/bin/env python3
"""
Integration test for teacher access API endpoints
"""

import sys
import os
import json
import tempfile

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_teacher_access_check_endpoint():
    """Test the /api/settings/teacher-access endpoint"""
    print("\nTesting GET /api/settings/teacher-access...")
    try:
        import app
        
        # Create a test client
        with app.app.test_client() as client:
            # Test without teacher access configured
            response = client.get('/api/settings/teacher-access')
            assert response.status_code == 200, f"Expected 200, got {response.status_code}"
            
            data = json.loads(response.data)
            assert 'teacher_access_enabled' in data, "Response missing teacher_access_enabled"
            assert data['teacher_access_enabled'] == False, "Teacher access should be disabled by default"
            
            print("✓ Endpoint returns correct response when teacher access is not configured")
            return True
            
    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_add_teacher_access_endpoint():
    """Test the /api/instances/<server_name>/add-teacher-access endpoint"""
    print("\nTesting POST /api/instances/<server_name>/add-teacher-access...")
    try:
        import app
        
        # Create a test client
        with app.app.test_client() as client:
            # Test without admin password configured
            response = client.post(
                '/api/instances/test-instance/add-teacher-access',
                json={'admin_password': 'test'},
                content_type='application/json'
            )
            
            # Should fail because admin password is not configured
            assert response.status_code == 403, f"Expected 403, got {response.status_code}"
            
            data = json.loads(response.data)
            assert 'error' in data, "Response should contain error"
            
            print("✓ Endpoint correctly rejects requests when admin password is not configured")
            
            # Test with non-existent instance
            # We can't test much more without setting up Docker environment
            print("✓ Basic endpoint validation successful")
            return True
            
    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_admin_check_endpoint():
    """Test that admin check endpoint still works"""
    print("\nTesting GET /api/admin/check...")
    try:
        import app
        
        # Create a test client
        with app.app.test_client() as client:
            response = client.get('/api/admin/check')
            assert response.status_code == 200, f"Expected 200, got {response.status_code}"
            
            data = json.loads(response.data)
            assert 'admin_enabled' in data, "Response missing admin_enabled"
            
            print("✓ Admin check endpoint still works correctly")
            return True
            
    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_existing_endpoints():
    """Test that existing endpoints still work"""
    print("\nTesting existing endpoints...")
    try:
        import app
        
        # Create a test client
        with app.app.test_client() as client:
            # Test home page
            response = client.get('/')
            assert response.status_code == 200, f"Home page failed: {response.status_code}"
            print("✓ Home page works")
            
            # Test get instances endpoint
            response = client.get('/api/instances')
            assert response.status_code == 200, f"Get instances failed: {response.status_code}"
            print("✓ Get instances endpoint works")
            
            # Test instance creation status endpoint
            response = client.get('/api/settings/instance-creation')
            assert response.status_code == 200, f"Instance creation status failed: {response.status_code}"
            print("✓ Instance creation status endpoint works")
            
            return True
            
    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Run all integration tests"""
    print("=" * 60)
    print("Teacher Access Integration Tests")
    print("=" * 60)
    
    tests = [
        test_teacher_access_check_endpoint,
        test_add_teacher_access_endpoint,
        test_admin_check_endpoint,
        test_existing_endpoints,
    ]
    
    results = []
    for test in tests:
        try:
            result = test()
            results.append(result)
        except Exception as e:
            print(f"\n✗ Test failed with exception: {e}")
            import traceback
            traceback.print_exc()
            results.append(False)
    
    print("\n" + "=" * 60)
    print(f"Results: {sum(results)}/{len(results)} tests passed")
    print("=" * 60)
    
    return all(results)

if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)
