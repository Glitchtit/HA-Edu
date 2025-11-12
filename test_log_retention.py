#!/usr/bin/env python3
"""
Test script to verify GDPR-compliant log retention functionality
"""

import os
import sys
import json
import tempfile
import shutil
from pathlib import Path
from datetime import datetime, timedelta

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def test_retention_days_configuration():
    """Test that retention days can be configured"""
    print("Testing retention days configuration...")
    try:
        from interaction_logger import InteractionLogger
        
        # Create a temporary directory for test logs
        test_log_dir = tempfile.mkdtemp()
        
        try:
            # Test default retention (90 days)
            logger1 = InteractionLogger(log_dir=test_log_dir)
            if logger1.retention_days != 90:
                print(f"✗ Default retention should be 90 days, got {logger1.retention_days}")
                return False
            
            # Test custom retention
            logger2 = InteractionLogger(log_dir=test_log_dir, retention_days=30)
            if logger2.retention_days != 30:
                print(f"✗ Custom retention should be 30 days, got {logger2.retention_days}")
                return False
            
            # Test unlimited retention (0 days)
            logger3 = InteractionLogger(log_dir=test_log_dir, retention_days=0)
            if logger3.retention_days != 0:
                print(f"✗ Unlimited retention should be 0 days, got {logger3.retention_days}")
                return False
            
            print("✓ Retention days configuration works correctly")
            print(f"  Default retention: 90 days")
            print(f"  Custom retention: configurable")
            print(f"  Unlimited retention: 0 days")
            return True
            
        finally:
            # Clean up
            shutil.rmtree(test_log_dir, ignore_errors=True)
            
    except Exception as e:
        print(f"✗ Retention days configuration failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_cleanup_old_logs():
    """Test that old logs are cleaned up based on retention period"""
    print("\nTesting old log cleanup...")
    try:
        from interaction_logger import InteractionLogger
        
        # Create a temporary directory for test logs
        test_log_dir = tempfile.mkdtemp()
        
        try:
            # Create logger with 7-day retention for testing
            logger = InteractionLogger(log_dir=test_log_dir, retention_days=7)
            
            # Create log entries with different timestamps
            log_file = os.path.join(test_log_dir, 'interactions.log')
            
            # Entry from 10 days ago (should be deleted)
            old_entry = {
                'timestamp': (datetime.now() - timedelta(days=10)).isoformat(),
                'event_type': 'instance_creation',
                'server_name': 'old-instance',
                'user_id': 'old@example.com'
            }
            
            # Entry from 5 days ago (should be kept)
            recent_entry = {
                'timestamp': (datetime.now() - timedelta(days=5)).isoformat(),
                'event_type': 'instance_creation',
                'server_name': 'recent-instance',
                'user_id': 'recent@example.com'
            }
            
            # Entry from today (should be kept)
            current_entry = {
                'timestamp': datetime.now().isoformat(),
                'event_type': 'instance_access',
                'server_name': 'current-instance',
                'user_id': 'current@example.com'
            }
            
            # Write entries manually to bypass cleanup on write
            Path(test_log_dir).mkdir(parents=True, exist_ok=True)
            with open(log_file, 'w') as f:
                f.write(json.dumps(old_entry) + '\n')
                f.write(json.dumps(recent_entry) + '\n')
                f.write(json.dumps(current_entry) + '\n')
            
            # Verify we have 3 entries
            with open(log_file, 'r') as f:
                lines_before = f.readlines()
            
            if len(lines_before) != 3:
                print(f"✗ Expected 3 entries before cleanup, got {len(lines_before)}")
                return False
            
            # Run cleanup
            logger._cleanup_old_logs()
            
            # Check remaining entries
            with open(log_file, 'r') as f:
                lines_after = f.readlines()
            
            if len(lines_after) != 2:
                print(f"✗ Expected 2 entries after cleanup, got {len(lines_after)}")
                return False
            
            # Verify old entry was removed
            remaining_entries = [json.loads(line) for line in lines_after]
            server_names = [entry['server_name'] for entry in remaining_entries]
            
            if 'old-instance' in server_names:
                print("✗ Old entry should have been removed")
                return False
            
            if 'recent-instance' not in server_names:
                print("✗ Recent entry should have been kept")
                return False
            
            if 'current-instance' not in server_names:
                print("✗ Current entry should have been kept")
                return False
            
            print("✓ Old log cleanup works correctly")
            print(f"  Entries before cleanup: {len(lines_before)}")
            print(f"  Entries after cleanup: {len(lines_after)}")
            print(f"  Expired entries removed: {len(lines_before) - len(lines_after)}")
            return True
            
        finally:
            # Clean up
            shutil.rmtree(test_log_dir, ignore_errors=True)
            
    except Exception as e:
        print(f"✗ Old log cleanup failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_cleanup_on_initialization():
    """Test that cleanup runs automatically on logger initialization"""
    print("\nTesting cleanup on initialization...")
    try:
        from interaction_logger import InteractionLogger
        
        # Create a temporary directory for test logs
        test_log_dir = tempfile.mkdtemp()
        
        try:
            # Create log file with old and new entries
            log_file = os.path.join(test_log_dir, 'interactions.log')
            
            old_entry = {
                'timestamp': (datetime.now() - timedelta(days=100)).isoformat(),
                'event_type': 'instance_creation',
                'server_name': 'old-instance'
            }
            
            new_entry = {
                'timestamp': datetime.now().isoformat(),
                'event_type': 'instance_creation',
                'server_name': 'new-instance'
            }
            
            # Write entries
            Path(test_log_dir).mkdir(parents=True, exist_ok=True)
            with open(log_file, 'w') as f:
                f.write(json.dumps(old_entry) + '\n')
                f.write(json.dumps(new_entry) + '\n')
            
            # Initialize logger (should trigger cleanup)
            logger = InteractionLogger(log_dir=test_log_dir, retention_days=90)
            
            # Check that old entry was removed
            with open(log_file, 'r') as f:
                lines = f.readlines()
            
            if len(lines) != 1:
                print(f"✗ Expected 1 entry after initialization cleanup, got {len(lines)}")
                return False
            
            entry = json.loads(lines[0])
            if entry['server_name'] != 'new-instance':
                print(f"✗ Expected new-instance, got {entry['server_name']}")
                return False
            
            print("✓ Cleanup on initialization works correctly")
            print(f"  Old entries automatically removed on startup")
            return True
            
        finally:
            # Clean up
            shutil.rmtree(test_log_dir, ignore_errors=True)
            
    except Exception as e:
        print(f"✗ Cleanup on initialization failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_cleanup_with_rotated_logs():
    """Test that cleanup works with rotated log files"""
    print("\nTesting cleanup with rotated logs...")
    try:
        from interaction_logger import InteractionLogger
        
        # Create a temporary directory for test logs
        test_log_dir = tempfile.mkdtemp()
        
        try:
            logger = InteractionLogger(log_dir=test_log_dir, retention_days=7)
            log_file = os.path.join(test_log_dir, 'interactions.log')
            
            # Create main log file
            Path(test_log_dir).mkdir(parents=True, exist_ok=True)
            
            # Old entry in main log
            old_main = {
                'timestamp': (datetime.now() - timedelta(days=10)).isoformat(),
                'event_type': 'instance_creation',
                'server_name': 'old-main'
            }
            
            # New entry in main log
            new_main = {
                'timestamp': datetime.now().isoformat(),
                'event_type': 'instance_creation',
                'server_name': 'new-main'
            }
            
            with open(log_file, 'w') as f:
                f.write(json.dumps(old_main) + '\n')
                f.write(json.dumps(new_main) + '\n')
            
            # Create rotated log file
            rotated_file = f'{log_file}.1'
            
            old_rotated = {
                'timestamp': (datetime.now() - timedelta(days=15)).isoformat(),
                'event_type': 'instance_deletion',
                'server_name': 'old-rotated'
            }
            
            new_rotated = {
                'timestamp': (datetime.now() - timedelta(days=3)).isoformat(),
                'event_type': 'instance_deletion',
                'server_name': 'new-rotated'
            }
            
            with open(rotated_file, 'w') as f:
                f.write(json.dumps(old_rotated) + '\n')
                f.write(json.dumps(new_rotated) + '\n')
            
            # Run cleanup
            logger._cleanup_old_logs()
            
            # Check main log
            with open(log_file, 'r') as f:
                main_lines = f.readlines()
            
            if len(main_lines) != 1:
                print(f"✗ Expected 1 entry in main log, got {len(main_lines)}")
                return False
            
            # Check rotated log
            with open(rotated_file, 'r') as f:
                rotated_lines = f.readlines()
            
            if len(rotated_lines) != 1:
                print(f"✗ Expected 1 entry in rotated log, got {len(rotated_lines)}")
                return False
            
            print("✓ Cleanup with rotated logs works correctly")
            print(f"  Main log cleaned: {2 - len(main_lines)} entries removed")
            print(f"  Rotated log cleaned: {2 - len(rotated_lines)} entries removed")
            return True
            
        finally:
            # Clean up
            shutil.rmtree(test_log_dir, ignore_errors=True)
            
    except Exception as e:
        print(f"✗ Cleanup with rotated logs failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_unlimited_retention():
    """Test that setting retention to 0 disables cleanup"""
    print("\nTesting unlimited retention (retention_days=0)...")
    try:
        from interaction_logger import InteractionLogger
        
        # Create a temporary directory for test logs
        test_log_dir = tempfile.mkdtemp()
        
        try:
            # Create logger with unlimited retention
            logger = InteractionLogger(log_dir=test_log_dir, retention_days=0)
            log_file = os.path.join(test_log_dir, 'interactions.log')
            
            # Create very old entry
            very_old_entry = {
                'timestamp': (datetime.now() - timedelta(days=365)).isoformat(),
                'event_type': 'instance_creation',
                'server_name': 'very-old-instance'
            }
            
            new_entry = {
                'timestamp': datetime.now().isoformat(),
                'event_type': 'instance_creation',
                'server_name': 'new-instance'
            }
            
            # Write entries
            Path(test_log_dir).mkdir(parents=True, exist_ok=True)
            with open(log_file, 'w') as f:
                f.write(json.dumps(very_old_entry) + '\n')
                f.write(json.dumps(new_entry) + '\n')
            
            # Run cleanup (should not remove anything)
            logger._cleanup_old_logs()
            
            # Check that both entries remain
            with open(log_file, 'r') as f:
                lines = f.readlines()
            
            if len(lines) != 2:
                print(f"✗ Expected 2 entries with unlimited retention, got {len(lines)}")
                return False
            
            print("✓ Unlimited retention works correctly")
            print(f"  All entries preserved regardless of age")
            return True
            
        finally:
            # Clean up
            shutil.rmtree(test_log_dir, ignore_errors=True)
            
    except Exception as e:
        print(f"✗ Unlimited retention test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_malformed_entries_preserved():
    """Test that malformed log entries are preserved during cleanup"""
    print("\nTesting malformed entry preservation...")
    try:
        from interaction_logger import InteractionLogger
        
        # Create a temporary directory for test logs
        test_log_dir = tempfile.mkdtemp()
        
        try:
            logger = InteractionLogger(log_dir=test_log_dir, retention_days=7)
            log_file = os.path.join(test_log_dir, 'interactions.log')
            
            # Create entries
            valid_old = {
                'timestamp': (datetime.now() - timedelta(days=10)).isoformat(),
                'event_type': 'instance_creation',
                'server_name': 'old-instance'
            }
            
            valid_new = {
                'timestamp': datetime.now().isoformat(),
                'event_type': 'instance_creation',
                'server_name': 'new-instance'
            }
            
            # Write entries including malformed ones
            Path(test_log_dir).mkdir(parents=True, exist_ok=True)
            with open(log_file, 'w') as f:
                f.write(json.dumps(valid_old) + '\n')
                f.write('{ invalid json }\n')  # Malformed entry
                f.write(json.dumps(valid_new) + '\n')
            
            # Run cleanup
            logger._cleanup_old_logs()
            
            # Check that malformed entry is preserved
            with open(log_file, 'r') as f:
                lines = f.readlines()
            
            # Should have 2 entries: malformed entry + valid new entry
            if len(lines) != 2:
                print(f"✗ Expected 2 entries (malformed + valid new), got {len(lines)}")
                return False
            
            # Check that malformed entry is still there
            if '{ invalid json }' not in lines[0]:
                print("✗ Malformed entry should have been preserved")
                return False
            
            print("✓ Malformed entries are preserved during cleanup")
            print(f"  Data loss prevention: malformed entries kept")
            return True
            
        finally:
            # Clean up
            shutil.rmtree(test_log_dir, ignore_errors=True)
            
    except Exception as e:
        print(f"✗ Malformed entry preservation test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all tests"""
    print("=" * 60)
    print("GDPR Log Retention Tests")
    print("=" * 60)
    
    tests = [
        test_retention_days_configuration,
        test_cleanup_old_logs,
        test_cleanup_on_initialization,
        test_cleanup_with_rotated_logs,
        test_unlimited_retention,
        test_malformed_entries_preserved,
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
