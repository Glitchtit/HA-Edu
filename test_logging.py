#!/usr/bin/env python3
"""
Test script to verify interaction logging functionality
"""

import os
import sys
import json
import tempfile
import shutil
from pathlib import Path

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_logger_creation():
    """Test that the logger can be created"""
    print("Testing logger creation...")
    try:
        from interaction_logger import InteractionLogger
        
        # Create a temporary directory for test logs
        test_log_dir = tempfile.mkdtemp()
        
        try:
            logger = InteractionLogger(log_dir=test_log_dir)
            
            # Check that log directory was created
            if not os.path.exists(test_log_dir):
                print("✗ Log directory not created")
                return False
            
            print(f"✓ Logger created with log directory: {test_log_dir}")
            return True
        finally:
            # Clean up
            shutil.rmtree(test_log_dir, ignore_errors=True)
            
    except Exception as e:
        print(f"✗ Logger creation failed: {e}")
        return False

def test_instance_creation_logging():
    """Test logging instance creation"""
    print("\nTesting instance creation logging...")
    try:
        from interaction_logger import InteractionLogger
        
        # Create a temporary directory for test logs
        test_log_dir = tempfile.mkdtemp()
        
        try:
            logger = InteractionLogger(log_dir=test_log_dir)
            
            # Log an instance creation
            logger.log_instance_creation(
                server_name='test-instance',
                user_id='test@example.com',
                user_type='user',
                port=8123,
                container_id='abc123def456'
            )
            
            # Check that log file was created
            log_file = os.path.join(test_log_dir, 'interactions.log')
            if not os.path.exists(log_file):
                print("✗ Log file not created")
                return False
            
            # Read and verify log entry
            with open(log_file, 'r') as f:
                log_line = f.readline().strip()
                log_entry = json.loads(log_line)
            
            # Verify log entry fields
            if log_entry.get('event_type') != 'instance_creation':
                print(f"✗ Wrong event type: {log_entry.get('event_type')}")
                return False
            
            if log_entry.get('server_name') != 'test-instance':
                print(f"✗ Wrong server name: {log_entry.get('server_name')}")
                return False
            
            if log_entry.get('user_id') != 'test@example.com':
                print(f"✗ Wrong user_id: {log_entry.get('user_id')}")
                return False
            
            if log_entry.get('port') != 8123:
                print(f"✗ Wrong port: {log_entry.get('port')}")
                return False
            
            print("✓ Instance creation logged correctly")
            print(f"  Event type: {log_entry.get('event_type')}")
            print(f"  Server name: {log_entry.get('server_name')}")
            print(f"  User: {log_entry.get('user_id')} ({log_entry.get('user_type')})")
            print(f"  Port: {log_entry.get('port')}")
            return True
            
        finally:
            # Clean up
            shutil.rmtree(test_log_dir, ignore_errors=True)
            
    except Exception as e:
        print(f"✗ Instance creation logging failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_multiple_events():
    """Test logging multiple events"""
    print("\nTesting multiple event logging...")
    try:
        from interaction_logger import InteractionLogger
        
        # Create a temporary directory for test logs
        test_log_dir = tempfile.mkdtemp()
        
        try:
            logger = InteractionLogger(log_dir=test_log_dir)
            
            # Log multiple events
            logger.log_instance_creation(
                server_name='test-1',
                user_id='user1@example.com',
                user_type='user',
                port=8123,
                container_id='abc123'
            )
            
            logger.log_instance_access(
                server_name='test-1',
                user_id='user1@example.com',
                user_type='user',
                access_type='proxy'
            )
            
            logger.log_instance_restart(
                server_name='test-1',
                user_id='admin@example.com',
                user_type='admin',
                container_id='abc123'
            )
            
            logger.log_instance_deletion(
                server_name='test-1',
                user_id='user1@example.com',
                user_type='user',
                container_id='abc123'
            )
            
            # Retrieve logs
            logs = logger.get_logs(limit=10)
            
            # Verify log count
            if len(logs) != 4:
                print(f"✗ Expected 4 logs, got {len(logs)}")
                return False
            
            # Verify logs are in reverse chronological order (most recent first)
            event_types = [log['event_type'] for log in logs]
            expected_order = ['instance_deletion', 'instance_restart', 'instance_access', 'instance_creation']
            
            if event_types != expected_order:
                print(f"✗ Logs not in correct order. Got: {event_types}")
                return False
            
            print("✓ Multiple events logged correctly")
            print(f"  Total events: {len(logs)}")
            print(f"  Event types: {', '.join(event_types)}")
            return True
            
        finally:
            # Clean up
            shutil.rmtree(test_log_dir, ignore_errors=True)
            
    except Exception as e:
        print(f"✗ Multiple event logging failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_log_filtering():
    """Test log filtering by event type"""
    print("\nTesting log filtering...")
    try:
        from interaction_logger import InteractionLogger
        
        # Create a temporary directory for test logs
        test_log_dir = tempfile.mkdtemp()
        
        try:
            logger = InteractionLogger(log_dir=test_log_dir)
            
            # Log different event types
            logger.log_instance_creation('test-1', 'user@example.com', 'user', 8123, 'abc123')
            logger.log_instance_access('test-1', 'user@example.com', 'user')
            logger.log_instance_access('test-1', 'admin@example.com', 'admin')
            logger.log_instance_deletion('test-1', 'user@example.com', 'user', 'abc123')
            
            # Filter by event type
            access_logs = logger.get_logs(limit=10, event_type='instance_access')
            
            if len(access_logs) != 2:
                print(f"✗ Expected 2 access logs, got {len(access_logs)}")
                return False
            
            # Verify all filtered logs are of correct type
            for log in access_logs:
                if log['event_type'] != 'instance_access':
                    print(f"✗ Found wrong event type in filtered results: {log['event_type']}")
                    return False
            
            print("✓ Log filtering works correctly")
            print(f"  Total access logs: {len(access_logs)}")
            return True
            
        finally:
            # Clean up
            shutil.rmtree(test_log_dir, ignore_errors=True)
            
    except Exception as e:
        print(f"✗ Log filtering failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_app_integration():
    """Test that app.py imports the logger correctly"""
    print("\nTesting app integration...")
    try:
        import app
        from interaction_logger import interaction_logger
        
        # Check that app imports interaction_logger
        if not hasattr(app, 'interaction_logger'):
            print("✗ app.py does not import interaction_logger")
            return False
        
        # Check that get_user_info_for_logging function exists
        if not hasattr(app, 'get_user_info_for_logging'):
            print("✗ get_user_info_for_logging function not found in app.py")
            return False
        
        print("✓ App integration successful")
        print("  interaction_logger imported")
        print("  get_user_info_for_logging function available")
        return True
        
    except Exception as e:
        print(f"✗ App integration failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Run all tests"""
    print("=" * 60)
    print("Interaction Logging Tests")
    print("=" * 60)
    
    tests = [
        test_logger_creation,
        test_instance_creation_logging,
        test_multiple_events,
        test_log_filtering,
        test_app_integration,
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        if test():
            passed += 1
        else:
            failed += 1
    
    print("\n" + "=" * 60)
    print(f"Tests passed: {passed}/{len(tests)}")
    print("=" * 60)
    
    if failed > 0:
        print(f"\n✗ {failed} test(s) failed")
        sys.exit(1)
    else:
        print("\n✓ All tests passed!")
        sys.exit(0)

if __name__ == '__main__':
    main()
