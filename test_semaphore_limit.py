#!/usr/bin/env python3
"""
Test to verify that the semaphore limits concurrent temporary container operations.
This ensures the app doesn't get overwhelmed when many instances are created.
"""

import sys
import os
import threading
import time
from datetime import datetime

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_semaphore_limits_concurrent_operations():
    """
    Test that the semaphore properly limits concurrent temporary container operations
    """
    print("=" * 70)
    print("Testing: Semaphore limits concurrent temporary container operations")
    print("=" * 70)
    
    try:
        import app
        
        # Track how many operations are running concurrently
        concurrent_count = 0
        max_concurrent = 0
        lock = threading.Lock()
        
        # Simulate temporary container operation
        def simulate_temp_container_operation(operation_id):
            nonlocal concurrent_count, max_concurrent
            
            # Acquire semaphore (same as in the actual functions)
            with app._temp_container_semaphore:
                # Track concurrent operations
                with lock:
                    concurrent_count += 1
                    if concurrent_count > max_concurrent:
                        max_concurrent = concurrent_count
                    print(f"Operation {operation_id:02d}: Started (concurrent: {concurrent_count})")
                
                # Simulate work
                time.sleep(0.1)
                
                # Release
                with lock:
                    concurrent_count -= 1
                    print(f"Operation {operation_id:02d}: Completed (concurrent: {concurrent_count})")
        
        # Create many threads to simulate concurrent instance creations
        # Each instance creation might do config copy + onboarding check + teacher account
        # So 15 instances could mean up to 45 operations
        num_operations = 30
        threads = []
        
        print(f"\nStarting {num_operations} concurrent operations...")
        print(f"Semaphore limit: 5")
        print()
        
        start_time = time.time()
        
        for i in range(num_operations):
            thread = threading.Thread(
                target=simulate_temp_container_operation,
                args=(i,),
                name=f'Thread-{i}'
            )
            threads.append(thread)
            thread.start()
        
        # Wait for all operations to complete
        for thread in threads:
            thread.join()
        
        end_time = time.time()
        duration = end_time - start_time
        
        # Analyze results
        print("\n" + "=" * 70)
        print("RESULTS")
        print("=" * 70)
        
        print(f"\nExecution time: {duration:.3f} seconds")
        print(f"Maximum concurrent operations observed: {max_concurrent}")
        print(f"Expected maximum (semaphore limit): 5")
        
        # Verify semaphore is working
        if max_concurrent <= 5:
            print(f"\n✅ SUCCESS: Semaphore properly limited concurrent operations to {max_concurrent}")
            print("   This prevents overwhelming the Docker daemon with too many containers.")
            return True
        else:
            print(f"\n❌ FAILURE: Semaphore did not limit operations (observed: {max_concurrent}, expected: ≤5)")
            return False
            
    except Exception as e:
        print(f"\n❌ Test failed with exception: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Run the test"""
    success = test_semaphore_limits_concurrent_operations()
    
    print("\n" + "=" * 70)
    if success:
        print("✅ TEST PASSED: Semaphore successfully limits concurrent operations!")
        print("=" * 70)
        return 0
    else:
        print("❌ TEST FAILED")
        print("=" * 70)
        return 1

if __name__ == '__main__':
    sys.exit(main())
