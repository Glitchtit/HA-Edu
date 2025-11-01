# Instance Password and Auto-Restart Features

This document describes the new instance password and automatic restart features added to HA-Edu.

## Features Overview

### 1. Instance Password Protection

When creating a new instance, users can now optionally set an instance password. This password allows authorized users to restart the instance without requiring admin access.

**Key Points:**
- Password is optional during instance creation
- Stored securely using bcrypt hashing
- Can be used to restart the instance
- Admin password also works for restart operations

### 2. Automatic Restart After Teacher Account Creation

When a teacher account is added to an instance (via the "Add Teacher Access" feature), the instance will automatically restart. This ensures the new teacher account is properly activated in Home Assistant.

**Key Points:**
- Automatic restart occurs after successful teacher account creation
- No manual intervention required
- If restart fails, a warning message is shown but the teacher account is still created

### 3. Instance Restart Button

A new "🔄 Restart" button is available on each instance card, allowing users to restart instances as needed.

**Key Points:**
- Visible to all users (no admin unlock required)
- Requires either the instance password or admin password
- Shows a modal dialog for password entry
- Provides clear feedback on success or failure

## Usage

### Setting an Instance Password

1. Click "Add New Instance"
2. Enter a server name
3. (Optional) Enter an instance password
4. Click "Create"

The password is securely hashed and stored with the instance metadata.

### Restarting an Instance

1. Click the "🔄 Restart" button on any instance card
2. Enter either:
   - The instance password (if one was set)
   - The admin password (if configured)
3. Click "Restart"

The instance will restart and status will be updated.

### Teacher Account Auto-Restart

1. Click "👨‍🏫 Teacher" button on an instance
2. Enter admin password
3. Click "Add Teacher Access"
4. The teacher account is created AND the instance automatically restarts

## Security Considerations

- Instance passwords are hashed using bcrypt (12 rounds)
- Passwords are never stored in plain text
- Password verification uses constant-time comparison to prevent timing attacks
- Both instance and admin passwords are accepted for restart operations
- Admin password takes precedence if both are valid

## API Endpoints

### POST /api/instances
Create a new instance with optional password:
```json
{
  "server_name": "Student-Lab-01",
  "instance_password": "optional_password"
}
```

### POST /api/instances/<server_name>/restart
Restart an instance:
```json
{
  "password": "instance_or_admin_password"
}
```

Response on success:
```json
{
  "message": "Instance restarted successfully",
  "server_name": "Student-Lab-01"
}
```

### POST /api/instances/<server_name>/add-teacher-access
Add teacher access (now includes auto-restart):
```json
{
  "admin_password": "admin_password_here"
}
```

Response on success:
```json
{
  "message": "Teacher access added successfully and instance restarted",
  "teacher_username": "teacher"
}
```

## Testing

Run the test suite:
```bash
python test_restart_password.py
```

The test suite includes:
- Password hashing and verification tests
- Container restart functionality tests
- Instance creation with/without password tests
- Restart endpoint authentication tests

## Implementation Details

### Password Hashing
```python
def hash_password(password):
    """Hash a password using bcrypt"""
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def verify_password(password, hashed):
    """Verify a password against a bcrypt hash"""
    return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))
```

### Container Restart
```python
def restart_instance_container(container_id):
    """Restart a Docker container"""
    container = client.containers.get(container_id)
    container.restart(timeout=10)
    return True, 'Instance restarted successfully'
```

### Dual Password Verification
The restart endpoint checks:
1. Admin password first (if configured)
2. Instance password second (if set)
3. Rejects if neither matches

## Dependencies

Added `bcrypt==4.1.2` to requirements.txt for secure password hashing.
