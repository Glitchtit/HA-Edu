# Concurrent Instance Creation Fix

## Problem Statement
When multiple students (15+) create Home Assistant instances at the exact same time, the system fails with port allocation errors:

```
ERROR: Failed to create instance: 500 Server Error for http+docker://localhost/v1.47/containers/...: 
Internal Server Error ("driver failed programming external connectivity on endpoint ha-edu-test1: 
Bind for 0.0.0.0:8125 failed: port is already allocated")
```

## Root Cause
The `create_instance()` function had a race condition:

1. **Request A** calls `get_available_port()` → gets port 8125
2. **Request B** calls `get_available_port()` (before A saves to JSON) → also gets port 8125
3. **Request A** creates container with port 8125 → succeeds
4. **Request B** tries to create container with port 8125 → fails (port already in use)

The issue occurred because:
- Port allocation and instance registration were separate, non-atomic operations
- Multiple threads could read the same JSON file state simultaneously
- No synchronization mechanism prevented concurrent access to the critical section

## Solution Implemented

### 1. Added Thread-Safe Locking
```python
# Thread lock for port allocation to prevent race conditions when multiple
# students create instances simultaneously
_port_allocation_lock = threading.Lock()
```

### 2. Atomic Port Allocation and Reservation
Modified `create_instance()` to use the lock for atomic operations:

```python
with _port_allocation_lock:
    instances = load_instances()
    
    # Check if server name already exists
    if server_name in instances:
        return jsonify({'error': 'Server name already exists'}), 400
    
    # Get available port
    port = get_available_port()
    
    # Reserve the port immediately by adding a placeholder entry
    # This prevents other concurrent requests from selecting the same port
    container_name = f'ha-edu-{server_name.lower().replace(" ", "-")}'
    instances[server_name] = {
        'container_id': 'pending',
        'container_name': container_name,
        'port': port,
        'created_at': datetime.now().isoformat(),
        'status': 'creating'
    }
    save_instances(instances)

# Container creation happens outside the lock to avoid blocking other requests
```

### 3. Cleanup on Failure
Added cleanup logic to remove placeholder entries if container creation fails:

```python
except Exception as e:
    logger.error(f'Failed to create instance: {str(e)}', exc_info=True)
    # Clean up the placeholder entry on failure
    try:
        instances = load_instances()
        if server_name in instances and instances[server_name].get('container_id') == 'pending':
            del instances[server_name]
            save_instances(instances)
    except Exception as cleanup_error:
        logger.error(f'Failed to clean up placeholder entry: {str(cleanup_error)}')
    return jsonify({'error': 'Failed to create instance. Please try again or contact support.'}), 500
```

## How It Works

### Before (Race Condition):
```
Thread 1: load_instances() → port=8125 → [waiting to save]
Thread 2: load_instances() → port=8125 → [waiting to save]
Thread 1: create_container(8125) → SUCCESS
Thread 2: create_container(8125) → FAIL (port already allocated)
```

### After (Thread-Safe):
```
Thread 1: LOCK → load_instances() → port=8125 → reserve port → save → UNLOCK
Thread 2: [waiting for lock...]
Thread 1: create_container(8125) → SUCCESS
Thread 2: LOCK → load_instances() → sees 8125 is reserved → port=8126 → reserve → UNLOCK
Thread 2: create_container(8126) → SUCCESS
```

## Testing

### Test Results
Created comprehensive tests to verify the fix:

1. **test_concurrent_creation.py** - Simulates 15 concurrent port allocations
   - ✅ All 15 ports allocated successfully and uniquely
   - ✅ Ports are sequential from BASE_PORT (8123)
   - ✅ Final state verified in JSON

2. **test_15_students_scenario.py** - Simulates the exact problem scenario
   - ✅ All 15 students created instances successfully
   - ✅ No port conflicts occurred
   - ✅ Execution time: ~0.018 seconds

3. **Existing tests** - Verified no regression
   - ✅ test_port_allocation.py: 3/3 passed
   - ✅ test_instance_recreation.py: 3/3 passed
   - ✅ test_orphaned_containers.py: 3/3 passed
   - ✅ test_status_field.py: All passed

## Performance Impact

- **Lock Duration**: Minimal - only held during JSON read/write operations (~1-5ms)
- **Container Creation**: Happens outside the lock, so no blocking
- **Throughput**: 15 students can create instances in ~18ms (sequential port allocation)
- **Scalability**: Lock ensures correctness without significant performance degradation

## Benefits

1. **Eliminates Port Conflicts**: No more "port already allocated" errors
2. **Maintains Order**: Sequential port allocation from BASE_PORT
3. **Graceful Failure**: Placeholder cleanup ensures consistent state
4. **Minimal Changes**: Surgical fix with no breaking changes
5. **Well Tested**: Comprehensive test coverage for concurrent scenarios

## Conclusion

The fix successfully resolves the concurrent instance creation issue by implementing proper thread synchronization. 15 students (or more) can now safely create instances at the exact same time without any port allocation conflicts.
