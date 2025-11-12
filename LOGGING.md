# Interaction Logging

The HA-Edu portal now includes comprehensive logging of all user and admin interactions with the application.

## What Gets Logged

All interactions are logged with the following information:
- **Timestamp**: When the event occurred
- **Event Type**: The type of interaction (see below)
- **User ID**: Email address from Cloudflare authentication (or IP address as fallback)
- **User Type**: Either 'admin' or 'user'
- **Event-specific details**: Additional information relevant to each event type

### Logged Events

1. **Instance Creation** (`instance_creation`)
   - Server name
   - Assigned port
   - Container ID
   - Who created it

2. **Instance Deletion** (`instance_deletion`)
   - Server name
   - Container ID
   - Who deleted it

3. **Instance Reset** (`instance_reset`)
   - Server name
   - Old container ID
   - New container ID
   - Who reset it

4. **Instance Restart** (`instance_restart`)
   - Server name
   - Container ID
   - Who restarted it

5. **Instance Access** (`instance_access`)
   - Server name
   - Access type (proxy, websocket, etc.)
   - Who accessed it

6. **Admin Operations** (`admin_operation`)
   - Operation type (e.g., delete_all_instances)
   - Operation details
   - Who performed it

7. **Teacher Access Added** (`teacher_access_added`)
   - Server name
   - Teacher username
   - Who added it

## Log File Location

Logs are stored in the `/logs` directory by default. This can be configured using the `LOG_DIR` environment variable.

### Log File Format

Logs are stored in JSON Lines format (one JSON object per line) in `/logs/interactions.log`:

```json
{"timestamp": "2025-11-02T22:30:45.123456", "event_type": "instance_creation", "server_name": "student-ha", "user_id": "student@example.com", "user_type": "user", "port": 8123, "container_id": "abc123def456"}
{"timestamp": "2025-11-02T22:35:12.789012", "event_type": "instance_access", "server_name": "student-ha", "user_id": "student@example.com", "user_type": "user", "access_type": "proxy"}
```

### Log Rotation

- Maximum log file size: **10 MB**
- Maximum number of rotated files: **10**
- When the current log file reaches 10 MB, it's rotated to `interactions.log.1`, and previous rotated files are shifted (`.1` → `.2`, etc.)
- The oldest log file (`.10`) is deleted when a new rotation occurs

## Accessing Logs

### Via API (Admin Only)

Logs can be retrieved programmatically using the `/api/logs` endpoint:

```bash
# Get the last 100 log entries (default)
curl -H "Cf-Access-Authenticated-User-Email: admin@example.com" \
     https://your-portal.com/api/logs

# Get the last 50 log entries
curl -H "Cf-Access-Authenticated-User-Email: admin@example.com" \
     https://your-portal.com/api/logs?limit=50

# Get only instance creation events
curl -H "Cf-Access-Authenticated-User-Email: admin@example.com" \
     https://your-portal.com/api/logs?event_type=instance_creation
```

**Response format:**
```json
{
  "logs": [
    {
      "timestamp": "2025-11-02T22:30:45.123456",
      "event_type": "instance_creation",
      "server_name": "student-ha",
      "user_id": "student@example.com",
      "user_type": "user",
      "port": 8123,
      "container_id": "abc123def456"
    }
  ],
  "count": 1
}
```

**Access Control:**
- Only users with admin access can retrieve logs
- Admin access is granted to:
  - Users from local network (192.168.50.0/24, 10.0.0.0/8, 127.0.0.0/8)
  - Users authenticated via Cloudflare with email in the `ADMINS` environment variable

### Via Direct File Access

If you have access to the server, you can directly read the log files:

```bash
# View recent logs
tail -f /logs/interactions.log

# View all logs (use jq for pretty formatting)
cat /logs/interactions.log | jq

# Filter by event type
cat /logs/interactions.log | jq 'select(.event_type == "instance_creation")'

# Count events by type
cat /logs/interactions.log | jq -r '.event_type' | sort | uniq -c

# Get logs from a specific user
cat /logs/interactions.log | jq 'select(.user_id == "student@example.com")'
```

## Configuration

### Environment Variables

- `LOG_DIR`: Directory where logs are stored (default: `/logs`)

### Docker Compose

The `docker-compose.yml` includes a volume mount for logs:

```yaml
volumes:
  - ./logs:/logs
```

This ensures logs persist on the host machine at `./logs/` relative to the docker-compose.yml file.

### Log Retention (GDPR Compliance)

- `LOG_RETENTION_DAYS`: Maximum number of days to retain logs (default: `90` days)
  - Set to `90` for GDPR compliance (automatic cleanup of logs older than 90 days)
  - Set to `0` for unlimited retention (no automatic cleanup)
  - Logs are cleaned up automatically on application startup and during log rotation

## GDPR Compliance

The HA-Edu portal implements **automatic log retention** to comply with GDPR (General Data Protection Regulation) requirements.

### Default Retention Period

- **90 days**: All log entries older than 90 days are automatically removed
- Configurable via the `LOG_RETENTION_DAYS` environment variable
- Cleanup happens automatically on application startup and during log rotation

### How It Works

1. **Automatic Cleanup**: Old log entries are removed automatically when:
   - The application starts
   - Log files are rotated (when they reach 10 MB)

2. **Timestamp-Based Retention**: The system checks the `timestamp` field of each log entry
   - Entries older than the retention period are removed
   - Entries within the retention period are kept

3. **All Log Files Cleaned**: Cleanup applies to:
   - Main log file (`interactions.log`)
   - All rotated log files (`interactions.log.1`, `interactions.log.2`, etc.)

### Configuration Examples

```yaml
# Docker Compose example - 90-day retention (GDPR compliant)
environment:
  - LOG_RETENTION_DAYS=90

# Shorter retention period (30 days)
environment:
  - LOG_RETENTION_DAYS=30

# Unlimited retention (not recommended for GDPR compliance)
environment:
  - LOG_RETENTION_DAYS=0
```

### What Gets Removed

When logs are cleaned up:
- ✅ Log entries with timestamps older than the retention period
- ❌ Malformed log entries are preserved (to prevent data loss)
- ❌ Recent log entries within the retention period

### Compliance Benefits

- **GDPR Article 5(1)(e)**: Storage limitation - personal data kept no longer than necessary
- **Right to erasure**: Old personal data (email addresses) automatically removed
- **Data minimization**: Only relevant recent data is retained
- **Audit trail**: Sufficient retention period for security and operational needs

## Privacy Considerations

- Logs contain user email addresses (from Cloudflare authentication)
- Logs show which users created, accessed, modified, and deleted instances
- **GDPR Compliance**: Logs are automatically cleaned up after 90 days (configurable)
- Consider your specific privacy policy and data retention requirements
- For stricter privacy requirements, reduce `LOG_RETENTION_DAYS` to a lower value

## Testing

Run the logging test suite:

```bash
# Test basic logging functionality
python3 test_logging.py

# Test GDPR log retention functionality
python3 test_log_retention.py
```

**Basic logging tests verify:**
- Logger can be created
- Events are logged correctly
- Log rotation works
- Filtering by event type works
- Integration with the main app is correct

**GDPR retention tests verify:**
- Retention period configuration
- Old log cleanup (removes entries older than retention period)
- Cleanup on initialization
- Cleanup with rotated log files
- Unlimited retention mode (retention_days=0)
- Malformed entries are preserved

## Example Use Cases

### Audit Trail
Track who created and deleted instances for accountability:
```bash
cat /logs/interactions.log | jq 'select(.event_type | test("creation|deletion"))'
```

### Usage Analytics
See which instances are being accessed most:
```bash
cat /logs/interactions.log | jq 'select(.event_type == "instance_access") | .server_name' | sort | uniq -c | sort -rn
```

### Admin Activity
Monitor admin operations:
```bash
cat /logs/interactions.log | jq 'select(.user_type == "admin")'
```

### User Activity Timeline
See all actions by a specific user:
```bash
cat /logs/interactions.log | jq 'select(.user_id == "student@example.com") | {timestamp, event_type, server_name}'
```
