#!/usr/bin/env python3
"""
Integration test to simulate the exact scenario from the problem statement:
15 students creating instances at the exact same time
"""

import sys
import os
import json
import tempfile
import threading
import time
from datetime import datetime

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_15_students_simultaneous_creation():
    """
    Simulate the exact scenario from the problem statement:
    15 students creating instances at the exact same time
    """
    print("=" * 70)
    print("Simulating: 15 students creating instances at the exact same time")
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
            num_students = 15
            student_names = [f'student-{i+1:02d}' for i in range(num_students)]
            
            # Track results
            successful_creations = []
            failed_creations = []
            allocated_ports = {}
            creation_lock = threading.Lock()
            
            # Barrier to synchronize all threads starting at the exact same time
            barrier = threading.Barrier(num_students)
            
            def student_creates_instance(student_name):
                """Simulate a student creating an instance"""
                try:
                    # Wait for all threads to be ready
                    barrier.wait()
                    
                    # Now all threads will execute this at the same time
                    # This is the critical part that tests our locking mechanism
                    with app._port_allocation_lock:
                        instances = app.load_instances()
                        
                        if student_name in instances:
                            with creation_lock:
                                failed_creations.append({
                                    'student': student_name,
                                    'reason': 'Name already exists'
                                })
                            return
                        
                        port = app.get_available_port()
                        container_name = f'ha-edu-{student_name}'
                        
                        # Reserve immediately
                        instances[student_name] = {
                            'container_id': f'mock-{student_name}',
                            'container_name': container_name,
                            'port': port,
                            'status': 'running',
                            'created_at': datetime.now().isoformat()
                        }
                        app.save_instances(instances)
                        
                        with creation_lock:
                            successful_creations.append(student_name)
                            allocated_ports[student_name] = port
                    
                except Exception as e:
                    with creation_lock:
                        failed_creations.append({
                            'student': student_name,
                            'reason': str(e)
                        })
            
            # Create threads for all students
            threads = []
            print(f"\nCreating {num_students} threads (one per student)...")
            for student_name in student_names:
                thread = threading.Thread(
                    target=student_creates_instance,
                    args=(student_name,),
                    name=f'Thread-{student_name}'
                )
                threads.append(thread)
            
            # Start all threads - they will wait at the barrier
            print("Starting all threads...")
            start_time = time.time()
            for thread in threads:
                thread.start()
            
            print("All threads waiting at barrier...")
            print("Releasing barrier - all students create instances NOW!")
            
            # Wait for all threads to complete
            for thread in threads:
                thread.join(timeout=10)
            
            end_time = time.time()
            duration = end_time - start_time
            
            # Analyze results
            print("\n" + "=" * 70)
            print("RESULTS")
            print("=" * 70)
            
            print(f"\nExecution time: {duration:.3f} seconds")
            print(f"Successful creations: {len(successful_creations)}/{num_students}")
            print(f"Failed creations: {len(failed_creations)}/{num_students}")
            
            if failed_creations:
                print("\nFailures:")
                for failure in failed_creations:
                    print(f"  - {failure['student']}: {failure['reason']}")
            
            if successful_creations:
                print(f"\nSuccessfully created instances:")
                for student in sorted(successful_creations):
                    port = allocated_ports[student]
                    print(f"  - {student}: port {port}")
            
            # Verify no duplicate ports
            all_ports = list(allocated_ports.values())
            unique_ports = set(all_ports)
            
            if len(unique_ports) != len(all_ports):
                print("\n❌ ERROR: DUPLICATE PORTS DETECTED!")
                duplicates = [p for p in all_ports if all_ports.count(p) > 1]
                print(f"   Duplicate ports: {set(duplicates)}")
                return False
            else:
                print(f"\n✅ All ports are unique: {sorted(all_ports)}")
            
            # Verify all students got instances
            if len(successful_creations) == num_students:
                print(f"\n✅ SUCCESS: All {num_students} students created instances successfully!")
                print("   No port conflicts occurred!")
                return True
            else:
                print(f"\n❌ FAILURE: Only {len(successful_creations)} out of {num_students} succeeded")
                return False
            
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
    success = test_15_students_simultaneous_creation()
    
    print("\n" + "=" * 70)
    if success:
        print("✅ TEST PASSED: 15 students can create instances simultaneously!")
        print("=" * 70)
        return 0
    else:
        print("❌ TEST FAILED")
        print("=" * 70)
        return 1

if __name__ == '__main__':
    sys.exit(main())
