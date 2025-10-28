#!/usr/bin/env python3
"""
Manual integration test to verify the port allocation fix works correctly
"""

import sys
import os
import json
import tempfile

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def simulate_port_conflict():
    """Simulate a scenario where port is already in use"""
    print("Simulating port conflict scenario...")
    print("=" * 60)
    
    try:
        import app
        
        # Create test instances file with port 8123 used
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            temp_file = f.name
            test_data = {
                'existing_server': {
                    'port': 8123,
                    'container_id': 'mock_container_id',
                    'container_name': 'ha-edu-existing',
                    'password': 'testpass',
                    'created_at': '2025-01-01T00:00:00',
                    'status': 'running'
                }
            }
            json.dump(test_data, f)
        
        # Override DATA_FILE for testing
        old_data_file = app.DATA_FILE
        app.DATA_FILE = temp_file
        
        try:
            print("\n1. Loading existing instances...")
            instances = app.load_instances()
            print(f"   Found {len(instances)} existing instance(s)")
            for name, inst in instances.items():
                print(f"   - {name}: port {inst['port']}")
            
            print("\n2. Getting available port...")
            print(f"   BASE_PORT is set to: {app.BASE_PORT}")
            port = app.get_available_port()
            print(f"   ✓ Available port found: {port}")
            
            if port == 8123:
                print(f"   ✗ ERROR: Port {port} is already in use but was returned!")
                return False
            elif port > 8123:
                print(f"   ✓ Correctly skipped port 8123 (in use)")
            
            print("\n3. Testing sequential port allocation...")
            # Simulate creating multiple instances
            for i in range(3):
                instances = app.load_instances()
                port = app.get_available_port()
                
                # Add to instances
                instances[f'test_server_{i}'] = {
                    'port': port,
                    'container_id': f'mock_id_{i}',
                    'container_name': f'ha-edu-test-{i}',
                    'password': 'test',
                    'created_at': '2025-01-01T00:00:00',
                    'status': 'running'
                }
                app.save_instances(instances)
                print(f"   Allocated port {port} for test_server_{i}")
            
            print("\n4. Verifying all ports are unique...")
            instances = app.load_instances()
            ports = [inst['port'] for inst in instances.values()]
            if len(ports) == len(set(ports)):
                print(f"   ✓ All {len(ports)} ports are unique: {sorted(ports)}")
            else:
                print(f"   ✗ ERROR: Duplicate ports found: {sorted(ports)}")
                return False
            
            print("\n5. Testing cleanup function exists...")
            if hasattr(app, 'cleanup_orphaned_containers'):
                print("   ✓ cleanup_orphaned_containers function is available")
            else:
                print("   ✗ ERROR: cleanup_orphaned_containers function not found")
                return False
            
            print("\n" + "=" * 60)
            print("✓ All integration tests passed!")
            print("=" * 60)
            return True
            
        finally:
            # Restore and cleanup
            app.DATA_FILE = old_data_file
            try:
                if os.path.exists(temp_file):
                    os.unlink(temp_file)
            except Exception:
                pass  # Ignore cleanup errors
            
    except Exception as e:
        print(f"\n✗ Integration test failed with error: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Run manual integration test"""
    print("\n" + "=" * 60)
    print("Manual Integration Test - Port Allocation Fix")
    print("=" * 60)
    print("\nThis test simulates the port conflict scenario described in the issue.")
    print("It verifies that the fix correctly handles already-allocated ports.\n")
    
    success = simulate_port_conflict()
    
    if success:
        print("\n✓ Integration test completed successfully!")
        print("\nThe fix addresses the following:")
        print("1. Checks actual Docker container port usage")
        print("2. Avoids allocating ports already in use")
        print("3. Provides cleanup for orphaned containers")
        print("4. Maintains consistency between instances.json and running containers")
        return 0
    else:
        print("\n✗ Integration test failed!")
        return 1

if __name__ == '__main__':
    sys.exit(main())
