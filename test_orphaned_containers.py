#!/usr/bin/env python3
"""
Test script to verify orphaned container cleanup correctly excludes ha-edu-portal
"""

import sys
import os
import json
import tempfile
from unittest.mock import Mock, patch

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_portal_container_not_orphaned():
    """Test that ha-edu-portal container is not identified as orphaned"""
    print("Testing that ha-edu-portal is excluded from orphaned cleanup...")
    
    try:
        import app
        
        # Create a temporary data file with no instances
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            temp_file = f.name
            test_data = {}
            json.dump(test_data, f)
        
        # Override DATA_FILE for testing
        old_data_file = app.DATA_FILE
        app.DATA_FILE = temp_file
        
        try:
            # Mock Docker client
            mock_client = Mock()
            
            # Create mock containers
            mock_portal_container = Mock()
            mock_portal_container.name = 'ha-edu-portal'
            mock_portal_container.id = 'portal123'
            mock_portal_container.status = 'running'
            
            mock_orphaned_container = Mock()
            mock_orphaned_container.name = 'ha-edu-orphaned-test'
            mock_orphaned_container.id = 'orphan456'
            mock_orphaned_container.status = 'running'
            
            # Both containers are returned by the filter
            mock_client.containers.list.return_value = [
                mock_portal_container,
                mock_orphaned_container
            ]
            
            # Replace the client temporarily
            old_client = app.client
            app.client = mock_client
            
            try:
                # Run cleanup
                app.cleanup_orphaned_containers()
                
                # Verify portal container was NOT stopped or removed
                if mock_portal_container.stop.call_count == 0 and mock_portal_container.remove.call_count == 0:
                    print("✓ ha-edu-portal container was not stopped or removed")
                else:
                    print("✗ ERROR: ha-edu-portal container was incorrectly stopped or removed")
                    return False
                
                # Verify orphaned container WAS stopped and removed
                if mock_orphaned_container.stop.call_count > 0 and mock_orphaned_container.remove.call_count > 0:
                    print("✓ Truly orphaned container was stopped and removed")
                else:
                    print("✗ ERROR: Orphaned container was not properly cleaned up")
                    return False
                
                return True
                
            finally:
                app.client = old_client
            
        finally:
            app.DATA_FILE = old_data_file
            os.unlink(temp_file)
            
    except Exception as e:
        print(f"✗ Error testing portal container exclusion: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_portal_container_different_names():
    """Test that only the exact name 'ha-edu-portal' is excluded"""
    print("\nTesting that other containers starting with 'ha-edu-' are not excluded...")
    
    try:
        import app
        
        # Create a temporary data file with no instances
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            temp_file = f.name
            test_data = {}
            json.dump(test_data, f)
        
        old_data_file = app.DATA_FILE
        app.DATA_FILE = temp_file
        
        try:
            mock_client = Mock()
            
            # Create containers with names similar to portal
            test_containers = [
                ('ha-edu-portal', 'portal123', False),  # Should be excluded
                ('ha-edu-portaltest', 'test123', True),  # Should be cleaned up
                ('ha-edu-test', 'test456', True),  # Should be cleaned up
                ('ha-edu-my-server', 'server789', True),  # Should be cleaned up
            ]
            
            mock_containers = []
            for name, container_id, should_cleanup in test_containers:
                mock_container = Mock()
                mock_container.name = name
                mock_container.id = container_id
                mock_container.status = 'running'
                mock_containers.append((mock_container, should_cleanup))
            
            mock_client.containers.list.return_value = [mc[0] for mc in mock_containers]
            
            old_client = app.client
            app.client = mock_client
            
            try:
                app.cleanup_orphaned_containers()
                
                # Verify each container's cleanup status
                all_correct = True
                for mock_container, should_cleanup in mock_containers:
                    was_cleaned = mock_container.stop.call_count > 0 and mock_container.remove.call_count > 0
                    
                    if should_cleanup and was_cleaned:
                        print(f"✓ {mock_container.name} was correctly cleaned up")
                    elif not should_cleanup and not was_cleaned:
                        print(f"✓ {mock_container.name} was correctly excluded")
                    elif should_cleanup and not was_cleaned:
                        print(f"✗ ERROR: {mock_container.name} should have been cleaned up but wasn't")
                        all_correct = False
                    else:
                        print(f"✗ ERROR: {mock_container.name} should not have been cleaned up but was")
                        all_correct = False
                
                return all_correct
                
            finally:
                app.client = old_client
            
        finally:
            app.DATA_FILE = old_data_file
            os.unlink(temp_file)
            
    except Exception as e:
        print(f"✗ Error testing container name variations: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_tracked_containers_not_cleaned():
    """Test that containers tracked in instances.json are not cleaned up"""
    print("\nTesting that tracked containers are not cleaned up...")
    
    try:
        import app
        
        # Create a temporary data file with a tracked instance
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            temp_file = f.name
            test_data = {
                'my_server': {
                    'container_id': 'tracked123',
                    'container_name': 'ha-edu-my-server',
                    'port': 8123,
                    'password': 'test',
                    'created_at': '2025-01-01T00:00:00',
                    'status': 'running'
                }
            }
            json.dump(test_data, f)
        
        old_data_file = app.DATA_FILE
        app.DATA_FILE = temp_file
        
        try:
            mock_client = Mock()
            
            # Create mock containers
            mock_portal = Mock()
            mock_portal.name = 'ha-edu-portal'
            mock_portal.id = 'portal123'
            mock_portal.status = 'running'
            
            mock_tracked = Mock()
            mock_tracked.name = 'ha-edu-my-server'
            mock_tracked.id = 'tracked123'
            mock_tracked.status = 'running'
            
            mock_orphaned = Mock()
            mock_orphaned.name = 'ha-edu-orphan'
            mock_orphaned.id = 'orphan456'
            mock_orphaned.status = 'running'
            
            mock_client.containers.list.return_value = [
                mock_portal,
                mock_tracked,
                mock_orphaned
            ]
            
            old_client = app.client
            app.client = mock_client
            
            try:
                app.cleanup_orphaned_containers()
                
                # Verify portal was not cleaned
                if mock_portal.stop.call_count == 0 and mock_portal.remove.call_count == 0:
                    print("✓ Portal container was not cleaned")
                else:
                    print("✗ ERROR: Portal container was incorrectly cleaned")
                    return False
                
                # Verify tracked container was not cleaned
                if mock_tracked.stop.call_count == 0 and mock_tracked.remove.call_count == 0:
                    print("✓ Tracked container was not cleaned")
                else:
                    print("✗ ERROR: Tracked container was incorrectly cleaned")
                    return False
                
                # Verify orphaned container was cleaned
                if mock_orphaned.stop.call_count > 0 and mock_orphaned.remove.call_count > 0:
                    print("✓ Orphaned container was cleaned")
                else:
                    print("✗ ERROR: Orphaned container was not cleaned")
                    return False
                
                return True
                
            finally:
                app.client = old_client
            
        finally:
            app.DATA_FILE = old_data_file
            os.unlink(temp_file)
            
    except Exception as e:
        print(f"✗ Error testing tracked containers: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Run all tests"""
    print("=" * 60)
    print("Orphaned Container Cleanup Tests")
    print("=" * 60)
    
    tests = [
        test_portal_container_not_orphaned,
        test_portal_container_different_names,
        test_tracked_containers_not_cleaned
    ]
    
    results = []
    for test in tests:
        try:
            result = test()
            results.append(result)
        except Exception as e:
            print(f"✗ Test failed with exception: {e}")
            import traceback
            traceback.print_exc()
            results.append(False)
    
    print("\n" + "=" * 60)
    print(f"Tests passed: {sum(results)}/{len(results)}")
    print("=" * 60)
    
    if all(results):
        print("\n✓ All tests passed!")
        print("\nThe fix ensures that:")
        print("1. The ha-edu-portal container is never cleaned up as orphaned")
        print("2. Other containers with 'ha-edu-' prefix are still cleaned if orphaned")
        print("3. Containers tracked in instances.json are not cleaned up")
        return 0
    else:
        print("\n✗ Some tests failed")
        return 1

if __name__ == '__main__':
    sys.exit(main())
