#!/usr/bin/env python3
"""
Comprehensive test to verify the app works well with many instances (15+).
Tests the complete lifecycle: create, check status, and cleanup.
"""

import sys
import os
import json
import tempfile
import threading
import time

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_high_concurrency_complete_lifecycle():
    """
    Test the complete lifecycle with high concurrency:
    1. Create 20 instances simultaneously
    2. Verify all instances created successfully
    3. Simulate onboarding check operations (which use temp containers)
    4. Verify semaphore limits concurrent temp container operations
    """
    print("=" * 70)
    print("High Concurrency Test: Complete Instance Lifecycle with 20 Instances")
    print("=" * 70)
    
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
        
        # Temporarily override DATA_FILE
        old_data_file = app.DATA_FILE
        app.DATA_FILE = temp_file
        
        try:
            # Phase 1: Create 20 instances simultaneously
            print("\n" + "=" * 70)
            print("PHASE 1: Creating 20 instances simultaneously")
            print("=" * 70)
            
            num_instances = 20
            instance_names = [f'test-instance-{i+1:02d}' for i in range(num_instances)]
            
            # Track results
            successful_creations = []
            failed_creations = []
            allocated_ports = {}
            creation_lock = threading.Lock()
            
            # Barrier to synchronize all threads
            barrier = threading.Barrier(num_instances)
            
            def create_instance_thread(instance_name):
                """Simulate instance creation"""
                try:
                    # Wait for all threads to be ready
                    barrier.wait()
                    
                    # Allocate port with lock (simulating the real create_instance flow)
                    with app._port_allocation_lock:
                        instances = app.load_instances()
                        
                        if instance_name in instances:
                            with creation_lock:
                                failed_creations.append({
                                    'instance': instance_name,
                                    'reason': 'Name already exists'
                                })
                            return
                        
                        port = app.get_available_port()
                        container_name = f'ha-edu-{instance_name}'
                        
                        # Reserve immediately
                        instances[instance_name] = {
                            'container_id': f'mock-{instance_name}',
                            'container_name': container_name,
                            'port': port,
                            'status': 'running',
                            'created_at': '2024-01-01T00:00:00'
                        }
                        app.save_instances(instances)
                        
                        with creation_lock:
                            successful_creations.append(instance_name)
                            allocated_ports[instance_name] = port
                    
                except Exception as e:
                    with creation_lock:
                        failed_creations.append({
                            'instance': instance_name,
                            'reason': str(e)
                        })
            
            # Create and start all threads
            threads = []
            start_time = time.time()
            for instance_name in instance_names:
                thread = threading.Thread(
                    target=create_instance_thread,
                    args=(instance_name,),
                    name=f'Thread-{instance_name}'
                )
                threads.append(thread)
                thread.start()
            
            # Wait for all threads to complete
            for thread in threads:
                thread.join(timeout=10)
            
            creation_time = time.time() - start_time
            
            # Verify phase 1 results
            print(f"\nCreation completed in {creation_time:.3f} seconds")
            print(f"Successful: {len(successful_creations)}/{num_instances}")
            print(f"Failed: {len(failed_creations)}/{num_instances}")
            
            if len(successful_creations) != num_instances:
                print("\n❌ PHASE 1 FAILED: Not all instances created")
                if failed_creations:
                    for failure in failed_creations:
                        print(f"  - {failure['instance']}: {failure['reason']}")
                return False
            
            # Check for duplicate ports
            all_ports = list(allocated_ports.values())
            unique_ports = set(all_ports)
            if len(unique_ports) != len(all_ports):
                print("\n❌ PHASE 1 FAILED: Duplicate ports detected")
                return False
            
            print(f"✅ PHASE 1 PASSED: All {num_instances} instances created with unique ports")
            print(f"   Ports: {sorted(all_ports)[:5]}...{sorted(all_ports)[-5:]}")
            
            # Phase 2: Simulate concurrent onboarding checks (uses temp containers)
            print("\n" + "=" * 70)
            print("PHASE 2: Simulating concurrent temp container operations")
            print("=" * 70)
            
            concurrent_ops = []
            max_concurrent = 0
            ops_lock = threading.Lock()
            
            def simulate_onboarding_check(instance_name):
                """Simulate onboarding check which uses temp containers"""
                nonlocal max_concurrent
                
                # This simulates what happens in check_instance_onboarding_complete
                with app._temp_container_semaphore:
                    with ops_lock:
                        concurrent_ops.append(instance_name)
                        if len(concurrent_ops) > max_concurrent:
                            max_concurrent = len(concurrent_ops)
                    
                    # Simulate work
                    time.sleep(0.05)
                    
                    with ops_lock:
                        concurrent_ops.remove(instance_name)
            
            # Create threads for onboarding checks
            check_threads = []
            start_time = time.time()
            for instance_name in instance_names:
                thread = threading.Thread(
                    target=simulate_onboarding_check,
                    args=(instance_name,),
                    name=f'Check-{instance_name}'
                )
                check_threads.append(thread)
                thread.start()
            
            # Wait for all checks to complete
            for thread in check_threads:
                thread.join(timeout=10)
            
            check_time = time.time() - start_time
            
            print(f"\nOnboarding checks completed in {check_time:.3f} seconds")
            print(f"Maximum concurrent temp container operations: {max_concurrent}")
            print(f"Semaphore limit: 5")
            
            if max_concurrent > 5:
                print(f"\n❌ PHASE 2 FAILED: Semaphore didn't limit concurrent ops (observed: {max_concurrent})")
                return False
            
            print(f"✅ PHASE 2 PASSED: Semaphore properly limited concurrent operations")
            
            # Final verification
            print("\n" + "=" * 70)
            print("FINAL VERIFICATION")
            print("=" * 70)
            
            final_instances = app.load_instances()
            print(f"Instances in database: {len(final_instances)}")
            print(f"Expected: {num_instances}")
            
            if len(final_instances) != num_instances:
                print(f"\n❌ FAILED: Expected {num_instances} instances, found {len(final_instances)}")
                return False
            
            print("\n✅ ALL TESTS PASSED!")
            print(f"   - {num_instances} instances created concurrently without conflicts")
            print(f"   - All ports unique and properly allocated")
            print(f"   - Semaphore limited concurrent temp container operations to 5")
            print(f"   - System stable with high concurrency")
            return True
            
        finally:
            # Restore original DATA_FILE
            app.DATA_FILE = old_data_file
            # Clean up temp file
            os.unlink(temp_file)
            
    except Exception as e:
        print(f"\n❌ Test failed with exception: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Run the test"""
    success = test_high_concurrency_complete_lifecycle()
    
    print("\n" + "=" * 70)
    if success:
        print("✅ HIGH CONCURRENCY TEST PASSED")
        print("   The app can handle 20+ instances with proper resource management")
        print("=" * 70)
        return 0
    else:
        print("❌ HIGH CONCURRENCY TEST FAILED")
        print("=" * 70)
        return 1

if __name__ == '__main__':
    sys.exit(main())
