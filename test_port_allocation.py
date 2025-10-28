#!/usr/bin/env python3
"""
Test script to verify port allocation and cleanup functionality
"""

import sys
import os
import json
import tempfile

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_get_available_port():
    """Test that get_available_port correctly finds available ports"""
    print("Testing get_available_port...")
    try:
        import app
        
        # Create a temporary data file for testing
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            temp_file = f.name
            # Create test data with some used ports
            test_data = {
                'server1': {'port': 8123, 'container_id': 'test1'},
                'server2': {'port': 8124, 'container_id': 'test2'},
                'server3': {'port': 8126, 'container_id': 'test3'}  # Gap at 8125
            }
            json.dump(test_data, f)
        
        # Temporarily override DATA_FILE
        old_data_file = app.DATA_FILE
        app.DATA_FILE = temp_file
        
        try:
            # Get available port - should reuse 8125 (the gap)
            port = app.get_available_port()
            print(f"✓ get_available_port returned: {port}")
            
            # Port should be one of the available ones
            if port >= app.BASE_PORT:
                print(f"✓ Port {port} is valid (>= BASE_PORT {app.BASE_PORT})")
            else:
                print(f"✗ Port {port} is invalid (< BASE_PORT {app.BASE_PORT})")
                return False
            
            # Test that function exists and returns an integer
            if isinstance(port, int):
                print("✓ Port is an integer")
            else:
                print("✗ Port is not an integer")
                return False
            
            return True
            
        finally:
            # Restore original DATA_FILE
            app.DATA_FILE = old_data_file
            # Clean up temp file
            os.unlink(temp_file)
            
    except Exception as e:
        print(f"✗ Error testing get_available_port: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_cleanup_function_exists():
    """Test that cleanup_orphaned_containers function exists"""
    print("\nTesting cleanup_orphaned_containers function...")
    try:
        import app
        
        if hasattr(app, 'cleanup_orphaned_containers'):
            print("✓ cleanup_orphaned_containers function exists")
            
            # Check if it's callable
            if callable(app.cleanup_orphaned_containers):
                print("✓ cleanup_orphaned_containers is callable")
            else:
                print("✗ cleanup_orphaned_containers is not callable")
                return False
            
            return True
        else:
            print("✗ cleanup_orphaned_containers function not found")
            return False
            
    except Exception as e:
        print(f"✗ Error testing cleanup function: {e}")
        return False

def test_port_collision_handling():
    """Test that the port allocation handles collisions"""
    print("\nTesting port collision handling...")
    try:
        import app
        
        # Create test scenario where ports are used
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            temp_file = f.name
            test_data = {
                'server1': {'port': 8123, 'container_id': 'test1'},
            }
            json.dump(test_data, f)
        
        old_data_file = app.DATA_FILE
        app.DATA_FILE = temp_file
        
        try:
            # Get multiple ports and ensure they're different
            ports = []
            for i in range(3):
                # Reload instances to simulate sequential allocations
                port = app.get_available_port()
                ports.append(port)
                
                # Add the port to instances to simulate allocation
                instances = app.load_instances()
                instances[f'test_server_{i}'] = {
                    'port': port,
                    'container_id': f'test_container_{i}'
                }
                app.save_instances(instances)
            
            # All ports should be unique
            if len(ports) == len(set(ports)):
                print(f"✓ All allocated ports are unique: {ports}")
            else:
                print(f"✗ Duplicate ports allocated: {ports}")
                return False
            
            # Ports should be sequential (with possible gaps from running containers)
            if all(p >= app.BASE_PORT for p in ports):
                print(f"✓ All ports are >= BASE_PORT ({app.BASE_PORT})")
            else:
                print(f"✗ Some ports are < BASE_PORT")
                return False
            
            return True
            
        finally:
            app.DATA_FILE = old_data_file
            os.unlink(temp_file)
            
    except Exception as e:
        print(f"✗ Error testing port collision handling: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Run all tests"""
    print("=" * 60)
    print("Port Allocation and Cleanup Tests")
    print("=" * 60)
    
    tests = [
        test_get_available_port,
        test_cleanup_function_exists,
        test_port_collision_handling
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
        print("\n✓ All tests passed!")
        return 0
    else:
        print("\n✗ Some tests failed")
        return 1

if __name__ == '__main__':
    sys.exit(main())
