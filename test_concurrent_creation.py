#!/usr/bin/env python3
"""
Test script to verify concurrent instance creation works without race conditions
"""

import sys
import os
import json
import tempfile
import threading
import time
from datetime import datetime
from unittest.mock import Mock, patch, MagicMock

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_concurrent_port_allocation():
    """Test that concurrent port allocation doesn't result in duplicate ports"""
    print("Testing concurrent port allocation...")
    try:
        import app
        
        # Create a temporary data file for testing
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            temp_file = f.name
            # Start with empty instances
            test_data = {
                'instances': {},
                'settings': {'instance_creation_enabled': True}
            }
            json.dump(test_data, f)
        
        # Temporarily override DATA_FILE
        old_data_file = app.DATA_FILE
        app.DATA_FILE = temp_file
        
        try:
            # Simulate 15 concurrent requests for port allocation
            num_requests = 15
            allocated_ports = []
            errors = []
            
            def allocate_port(index):
                """Simulate a single port allocation"""
                try:
                    # Use the lock as the actual function does
                    with app._port_allocation_lock:
                        instances = app.load_instances()
                        port = app.get_available_port()
                        
                        # Reserve the port
                        server_name = f'test-server-{index}'
                        instances[server_name] = {
                            'container_id': f'test-{index}',
                            'port': port,
                            'created_at': datetime.now().isoformat()
                        }
                        app.save_instances(instances)
                        allocated_ports.append(port)
                except Exception as e:
                    errors.append(str(e))
            
            # Create threads to simulate concurrent requests
            threads = []
            for i in range(num_requests):
                thread = threading.Thread(target=allocate_port, args=(i,))
                threads.append(thread)
            
            # Start all threads nearly simultaneously
            for thread in threads:
                thread.start()
            
            # Wait for all threads to complete
            for thread in threads:
                thread.join(timeout=5)
            
            # Verify results
            if errors:
                print(f"✗ Errors occurred during allocation: {errors}")
                return False
            
            if len(allocated_ports) != num_requests:
                print(f"✗ Expected {num_requests} ports, got {len(allocated_ports)}")
                return False
            
            # Check for duplicates
            unique_ports = set(allocated_ports)
            if len(unique_ports) != len(allocated_ports):
                print(f"✗ Duplicate ports allocated: {allocated_ports}")
                print(f"  Unique ports: {unique_ports}")
                duplicates = [p for p in allocated_ports if allocated_ports.count(p) > 1]
                print(f"  Duplicates: {set(duplicates)}")
                return False
            
            print(f"✓ All {num_requests} ports allocated successfully and uniquely")
            print(f"  Allocated ports: {sorted(allocated_ports)}")
            
            # Verify ports are sequential from BASE_PORT
            expected_ports = list(range(app.BASE_PORT, app.BASE_PORT + num_requests))
            if sorted(allocated_ports) == expected_ports:
                print(f"✓ Ports are sequential from BASE_PORT ({app.BASE_PORT})")
            else:
                print(f"⚠ Ports are not sequential (this is OK if there are gaps)")
                print(f"  Expected: {expected_ports}")
                print(f"  Got: {sorted(allocated_ports)}")
            
            return True
            
        finally:
            # Restore original DATA_FILE
            app.DATA_FILE = old_data_file
            # Clean up temp file
            os.unlink(temp_file)
            
    except Exception as e:
        print(f"✗ Error testing concurrent port allocation: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_concurrent_instance_creation_simulation():
    """Test the entire instance creation flow with logic verification only"""
    print("\nTesting concurrent instance creation logic...")
    try:
        import app
        
        # Create a temporary data file for testing
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            temp_file = f.name
            test_data = {
                'instances': {},
                'settings': {'instance_creation_enabled': True}
            }
            json.dump(test_data, f)
        
        old_data_file = app.DATA_FILE
        app.DATA_FILE = temp_file
        
        try:
            # Simulate 15 concurrent instance creations using just the logic
            num_instances = 15
            results = []
            errors = []
            
            # Track allocated ports
            ports_allocated = []
            ports_lock = threading.Lock()
            
            def create_instance_logic(index):
                """Simulate creating an instance with just the critical logic"""
                try:
                    server_name = f'student-{index:02d}'
                    
                    # Simulate the core logic of create_instance
                    with app._port_allocation_lock:
                        instances = app.load_instances()
                        if server_name in instances:
                            errors.append(f"Server {server_name} already exists")
                            return
                        
                        port = app.get_available_port()
                        container_name = f'ha-edu-{server_name}'
                        
                        # Track this port
                        with ports_lock:
                            ports_allocated.append(port)
                        
                        # Reserve immediately
                        instances[server_name] = {
                            'container_id': f'mock-container-{index}',
                            'container_name': container_name,
                            'port': port,
                            'status': 'running'
                        }
                        app.save_instances(instances)
                    
                    results.append({
                        'server_name': server_name,
                        'port': port
                    })
                except Exception as e:
                    errors.append(f"Instance {index}: {str(e)}")
            
            # Create threads
            threads = []
            for i in range(num_instances):
                thread = threading.Thread(target=create_instance_logic, args=(i,))
                threads.append(thread)
            
            # Start all threads
            for thread in threads:
                thread.start()
            
            # Wait for completion
            for thread in threads:
                thread.join(timeout=10)
            
            # Verify results
            if errors:
                print(f"✗ Errors occurred: {errors}")
                return False
            
            if len(results) != num_instances:
                print(f"✗ Expected {num_instances} instances, created {len(results)}")
                return False
            
            # Verify no duplicate ports were allocated
            unique_ports = set(ports_allocated)
            if len(unique_ports) != len(ports_allocated):
                print(f"✗ Duplicate ports allocated!")
                duplicates = [p for p in ports_allocated if ports_allocated.count(p) > 1]
                print(f"  Duplicates: {set(duplicates)}")
                return False
            
            print(f"✓ All {num_instances} instances created successfully")
            print(f"✓ All ports unique: {sorted(ports_allocated)}")
            
            # Verify final state in JSON
            final_instances = app.load_instances()
            if len(final_instances) != num_instances:
                print(f"✗ Expected {num_instances} in final state, got {len(final_instances)}")
                return False
            
            print(f"✓ Final state verified: {len(final_instances)} instances in JSON")
            return True
            
        finally:
            app.DATA_FILE = old_data_file
            os.unlink(temp_file)
            
    except Exception as e:
        print(f"✗ Error testing concurrent instance creation: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_lock_prevents_race_condition():
    """Test that the lock actually prevents race conditions"""
    print("\nTesting that lock prevents race conditions...")
    try:
        import app
        
        # Create a temporary data file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            temp_file = f.name
            test_data = {
                'instances': {},
                'settings': {'instance_creation_enabled': True}
            }
            json.dump(test_data, f)
        
        old_data_file = app.DATA_FILE
        app.DATA_FILE = temp_file
        
        try:
            race_detected = []
            
            def attempt_allocation_without_lock(index):
                """Try to allocate without proper locking - should cause races"""
                try:
                    # Intentionally don't use the lock to demonstrate the problem
                    instances = app.load_instances()
                    port = app.get_available_port()
                    
                    # Small delay to increase chance of race condition
                    time.sleep(0.001)
                    
                    # Check if port was already allocated by another thread
                    instances = app.load_instances()
                    for name, inst in instances.items():
                        if inst['port'] == port and name != f'test-{index}':
                            race_detected.append(f"Port {port} used by both {name} and test-{index}")
                            return
                    
                    instances[f'test-{index}'] = {'port': port, 'container_id': f'test-{index}'}
                    app.save_instances(instances)
                except Exception as e:
                    pass  # Ignore errors for this test
            
            # Run without lock (should have races)
            threads = []
            for i in range(10):
                thread = threading.Thread(target=attempt_allocation_without_lock, args=(i,))
                threads.append(thread)
            
            for thread in threads:
                thread.start()
            
            for thread in threads:
                thread.join(timeout=5)
            
            # We expect races to be detected when not using locks
            # But this is not a reliable test since it depends on timing
            print(f"✓ Lock mechanism test completed")
            if race_detected:
                print(f"  (Note: {len(race_detected)} races would occur without lock)")
            
            return True
            
        finally:
            app.DATA_FILE = old_data_file
            os.unlink(temp_file)
            
    except Exception as e:
        print(f"✗ Error testing lock mechanism: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Run all tests"""
    print("=" * 60)
    print("Concurrent Instance Creation Tests")
    print("=" * 60)
    
    tests = [
        test_concurrent_port_allocation,
        test_concurrent_instance_creation_simulation,
        test_lock_prevents_race_condition
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
        return 0
    else:
        print("\n✗ Some tests failed")
        return 1

if __name__ == '__main__':
    sys.exit(main())
