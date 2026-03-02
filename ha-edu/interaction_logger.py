"""
Interaction Logger for HA-Edu Portal

Logs all user and admin interactions with the application, including:
- Instance creation, deletion, reset, restart
- Instance access
- Admin operations

Logs are stored in /logs directory with rotation support.
"""

import os
import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
import threading

# Thread lock for log file writes to prevent race conditions
_log_write_lock = threading.Lock()

# Configure log directory - use /logs in production, ./logs in development
# Check if running as root or if /logs exists (production)
try:
    is_root = os.getuid() == 0
except AttributeError:
    # Windows doesn't have getuid, assume not root
    is_root = False

LOG_DIR = os.getenv('LOG_DIR', '/logs' if (os.path.exists('/logs') or is_root) else './logs')
INTERACTION_LOG_FILE = os.path.join(LOG_DIR, 'interactions.log')
MAX_LOG_SIZE = 10 * 1024 * 1024  # 10 MB
MAX_LOG_FILES = 10

# GDPR compliance: Maximum log retention period in days
# Default is 90 days, can be configured via LOG_RETENTION_DAYS environment variable
LOG_RETENTION_DAYS = int(os.getenv('LOG_RETENTION_DAYS', '90'))

# Configure logger
logger = logging.getLogger(__name__)

class InteractionLogger:
    """Logger for user and admin interactions"""
    
    def __init__(self, log_dir=LOG_DIR, retention_days=LOG_RETENTION_DAYS):
        """Initialize the interaction logger
        
        Args:
            log_dir: Directory to store log files
            retention_days: Maximum number of days to retain logs (default: 90 for GDPR compliance)
        """
        self.log_dir = log_dir
        self.log_file = os.path.join(log_dir, 'interactions.log')
        self.retention_days = retention_days
        self._dir_created = False
        
        # Clean up old logs on initialization
        self._cleanup_old_logs()
        
    def _ensure_log_dir(self):
        """Ensure log directory exists (lazy creation)"""
        if not self._dir_created:
            try:
                Path(self.log_dir).mkdir(parents=True, exist_ok=True)
                self._dir_created = True
            except Exception as e:
                logger.error(f'Failed to create log directory {self.log_dir}: {str(e)}')
                raise
        
    def _write_log(self, log_entry):
        """Write a log entry to the log file
        
        Args:
            log_entry: Dictionary containing log data
        """
        with _log_write_lock:
            try:
                # Ensure log directory exists
                self._ensure_log_dir()
                
                # Check if log rotation is needed
                if os.path.exists(self.log_file):
                    if os.path.getsize(self.log_file) > MAX_LOG_SIZE:
                        self._rotate_logs()
                
                # Write log entry as JSON line
                with open(self.log_file, 'a') as f:
                    f.write(json.dumps(log_entry) + '\n')
                    
            except Exception as e:
                logger.error(f'Failed to write interaction log: {str(e)}')
    
    def _rotate_logs(self):
        """Rotate log files when they exceed MAX_LOG_SIZE"""
        try:
            # Rotate existing log files
            for i in range(MAX_LOG_FILES - 1, 0, -1):
                old_file = f'{self.log_file}.{i}'
                new_file = f'{self.log_file}.{i + 1}'
                
                if os.path.exists(old_file):
                    if i == MAX_LOG_FILES - 1:
                        # Delete oldest log file
                        os.remove(old_file)
                    else:
                        os.rename(old_file, new_file)
            
            # Rename current log file
            if os.path.exists(self.log_file):
                os.rename(self.log_file, f'{self.log_file}.1')
            
            # Clean up old logs after rotation
            self._cleanup_old_logs()
                
        except Exception as e:
            logger.error(f'Failed to rotate logs: {str(e)}')
    
    def _cleanup_old_logs(self):
        """Clean up log entries older than retention_days for GDPR compliance
        
        This method removes log entries that are older than the configured retention period.
        It processes all log files (main and rotated) and rewrites them without expired entries.
        Runs on logger initialization and can be called periodically.
        """
        if self.retention_days <= 0:
            # If retention is set to 0 or negative, don't clean up (infinite retention)
            return
            
        try:
            # Calculate cutoff timestamp
            cutoff_date = datetime.now() - timedelta(days=self.retention_days)
            
            # Get all log files (main + rotated)
            log_files_to_process = [self.log_file]
            for i in range(1, MAX_LOG_FILES + 1):
                rotated_file = f'{self.log_file}.{i}'
                if os.path.exists(rotated_file):
                    log_files_to_process.append(rotated_file)
            
            # Process each log file
            for log_file_path in log_files_to_process:
                if not os.path.exists(log_file_path):
                    continue
                    
                # Read all entries from the file
                retained_entries = []
                removed_count = 0
                
                try:
                    with open(log_file_path, 'r') as f:
                        for line in f:
                            try:
                                entry = json.loads(line.strip())
                                # Parse timestamp and check if it's within retention period
                                entry_timestamp = datetime.fromisoformat(entry.get('timestamp', ''))
                                
                                if entry_timestamp >= cutoff_date:
                                    retained_entries.append(line)
                                else:
                                    removed_count += 1
                            except (json.JSONDecodeError, ValueError, KeyError):
                                # Keep malformed entries to avoid data loss
                                retained_entries.append(line)
                    
                    # Only rewrite the file if we removed entries
                    if removed_count > 0:
                        with open(log_file_path, 'w') as f:
                            f.writelines(retained_entries)
                        logger.info(f'GDPR cleanup: Removed {removed_count} expired log entries from {os.path.basename(log_file_path)}')
                    
                except Exception as e:
                    logger.error(f'Failed to cleanup logs in {log_file_path}: {str(e)}')
                    
        except Exception as e:
            logger.error(f'Failed to cleanup old logs: {str(e)}')
    
    def log_instance_creation(self, server_name, user_id, user_type, port, container_id):
        """Log instance creation event
        
        Args:
            server_name: Name of the instance
            user_id: User identifier (email or IP)
            user_type: Type of user ('admin' or 'user')
            port: Assigned port number
            container_id: Docker container ID
        """
        log_entry = {
            'timestamp': datetime.now().isoformat(),
            'event_type': 'instance_creation',
            'server_name': server_name,
            'user_id': user_id,
            'user_type': user_type,
            'port': port,
            'container_id': container_id[:12] if container_id else None
        }
        self._write_log(log_entry)
        logger.info(f'Instance created: {server_name} by {user_id} ({user_type})')
    
    def log_instance_deletion(self, server_name, user_id, user_type, container_id):
        """Log instance deletion event
        
        Args:
            server_name: Name of the instance
            user_id: User identifier (email or IP)
            user_type: Type of user ('admin' or 'user')
            container_id: Docker container ID
        """
        log_entry = {
            'timestamp': datetime.now().isoformat(),
            'event_type': 'instance_deletion',
            'server_name': server_name,
            'user_id': user_id,
            'user_type': user_type,
            'container_id': container_id[:12] if container_id else None
        }
        self._write_log(log_entry)
        logger.info(f'Instance deleted: {server_name} by {user_id} ({user_type})')
    
    def log_instance_reset(self, server_name, user_id, user_type, old_container_id, new_container_id):
        """Log instance reset event
        
        Args:
            server_name: Name of the instance
            user_id: User identifier (email or IP)
            user_type: Type of user ('admin' or 'user')
            old_container_id: Old Docker container ID
            new_container_id: New Docker container ID
        """
        log_entry = {
            'timestamp': datetime.now().isoformat(),
            'event_type': 'instance_reset',
            'server_name': server_name,
            'user_id': user_id,
            'user_type': user_type,
            'old_container_id': old_container_id[:12] if old_container_id else None,
            'new_container_id': new_container_id[:12] if new_container_id else None
        }
        self._write_log(log_entry)
        logger.info(f'Instance reset: {server_name} by {user_id} ({user_type})')
    
    def log_instance_restart(self, server_name, user_id, user_type, container_id):
        """Log instance restart event
        
        Args:
            server_name: Name of the instance
            user_id: User identifier (email or IP)
            user_type: Type of user ('admin' or 'user')
            container_id: Docker container ID
        """
        log_entry = {
            'timestamp': datetime.now().isoformat(),
            'event_type': 'instance_restart',
            'server_name': server_name,
            'user_id': user_id,
            'user_type': user_type,
            'container_id': container_id[:12] if container_id else None
        }
        self._write_log(log_entry)
        logger.info(f'Instance restarted: {server_name} by {user_id} ({user_type})')
    
    def log_instance_access(self, server_name, user_id, user_type, access_type='proxy'):
        """Log instance access event
        
        Args:
            server_name: Name of the instance
            user_id: User identifier (email or IP)
            user_type: Type of user ('admin' or 'user')
            access_type: Type of access ('proxy', 'websocket', etc.)
        """
        log_entry = {
            'timestamp': datetime.now().isoformat(),
            'event_type': 'instance_access',
            'server_name': server_name,
            'user_id': user_id,
            'user_type': user_type,
            'access_type': access_type
        }
        self._write_log(log_entry)
        logger.debug(f'Instance accessed: {server_name} by {user_id} ({user_type}) via {access_type}')
    
    def log_admin_operation(self, operation, user_id, details=None):
        """Log admin operation event
        
        Args:
            operation: Type of admin operation
            user_id: Admin user identifier
            details: Additional operation details (dict)
        """
        log_entry = {
            'timestamp': datetime.now().isoformat(),
            'event_type': 'admin_operation',
            'operation': operation,
            'user_id': user_id,
            'user_type': 'admin',
            'details': details or {}
        }
        self._write_log(log_entry)
        logger.info(f'Admin operation: {operation} by {user_id}')
    
    def log_teacher_access_added(self, server_name, user_id, teacher_username):
        """Log teacher access addition event
        
        Args:
            server_name: Name of the instance
            user_id: Admin user identifier
            teacher_username: Teacher account username
        """
        log_entry = {
            'timestamp': datetime.now().isoformat(),
            'event_type': 'teacher_access_added',
            'server_name': server_name,
            'user_id': user_id,
            'user_type': 'admin',
            'teacher_username': teacher_username
        }
        self._write_log(log_entry)
        logger.info(f'Teacher access added to {server_name} by {user_id}')
    
    def get_logs(self, limit=100, event_type=None):
        """Retrieve log entries
        
        Args:
            limit: Maximum number of log entries to return
            event_type: Filter by event type (optional)
            
        Returns:
            List of log entry dictionaries
        """
        logs = []
        
        try:
            if os.path.exists(self.log_file):
                with open(self.log_file, 'r') as f:
                    for line in f:
                        try:
                            log_entry = json.loads(line.strip())
                            
                            # Filter by event type if specified
                            if event_type and log_entry.get('event_type') != event_type:
                                continue
                            
                            logs.append(log_entry)
                        except json.JSONDecodeError:
                            continue
            
            # Return most recent logs first
            logs.reverse()
            return logs[:limit]
            
        except Exception as e:
            logger.error(f'Failed to read logs: {str(e)}')
            return []

# Global instance
interaction_logger = InteractionLogger()
