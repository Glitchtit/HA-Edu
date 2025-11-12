# GDPR Compliance - HA-Edu Portal

## Overview

The HA-Edu portal implements GDPR (General Data Protection Regulation) compliance through automatic log retention and data minimization practices.

## GDPR Compliance Features

### 1. Storage Limitation (Article 5(1)(e))

**Requirement**: Personal data must be kept for no longer than is necessary for the purposes for which it is processed.

**Implementation**:
- Automatic log retention with a default maximum of **90 days**
- Configurable retention period via `LOG_RETENTION_DAYS` environment variable
- Logs older than the retention period are automatically deleted

### 2. Data Minimization

**What is logged**:
- User identifiers (email addresses from Cloudflare authentication or IP addresses)
- Instance names and operations (create, delete, access, reset, restart)
- Timestamps of all interactions
- Event types (creation, deletion, access, etc.)

**What is NOT logged**:
- User passwords
- Home Assistant configuration data
- Personal sensor data from instances
- Content of communications

### 3. Right to Erasure (Article 17)

**Implementation**:
- Automatic deletion of log entries older than the retention period
- No manual intervention required
- Deletion occurs during:
  - Application startup
  - Log rotation (when files reach 10 MB)

### 4. Technical and Organizational Measures

**Security measures**:
- Log files stored in dedicated `/logs` directory
- Thread-safe log writing to prevent corruption
- Malformed entries preserved to prevent data loss
- Environment-based configuration for easy management

## Configuration

### Default Configuration (GDPR Compliant)

```yaml
environment:
  - LOG_RETENTION_DAYS=90  # 90-day retention (default)
```

### Custom Retention Periods

```yaml
# Shorter retention (30 days)
environment:
  - LOG_RETENTION_DAYS=30

# Longer retention (180 days) - consider your legal requirements
environment:
  - LOG_RETENTION_DAYS=180

# Unlimited retention (NOT recommended for GDPR compliance)
environment:
  - LOG_RETENTION_DAYS=0
```

## How It Works

### Automatic Cleanup Process

1. **On Application Startup**:
   - Logger is initialized
   - Cleanup process runs automatically
   - Old log entries (beyond retention period) are removed

2. **During Log Rotation**:
   - When a log file reaches 10 MB, it's rotated
   - After rotation, cleanup runs automatically
   - All rotated log files are cleaned

3. **Timestamp-Based Removal**:
   - Each log entry has an ISO 8601 timestamp
   - Entries older than `retention_days` are removed
   - Recent entries are preserved

### Which Files Are Cleaned

- `interactions.log` - Main log file
- `interactions.log.1` - First rotated log
- `interactions.log.2` - Second rotated log
- ... up to `interactions.log.10`

### Example Cleanup

With `LOG_RETENTION_DAYS=90`:

```
Before cleanup:
- Entry from 100 days ago → DELETED
- Entry from 85 days ago  → KEPT
- Entry from 10 days ago  → KEPT
- Entry from today        → KEPT
```

## Data Subject Rights

### Right to Access (Article 15)

Users can request their data through the `/api/logs` endpoint (admin-only):

```bash
# Get all logs for a specific user
curl -H "Cf-Access-Authenticated-User-Email: admin@example.com" \
     https://your-portal.com/api/logs?limit=1000 \
| jq '.logs[] | select(.user_id == "student@example.com")'
```

### Right to Erasure (Article 17)

Automatic erasure is implemented:
- All personal data (email addresses) in logs older than 90 days is automatically deleted
- No manual intervention required
- Deletion is irreversible

### Right to Data Portability (Article 20)

Data can be exported in JSON format:

```bash
# Export all logs
curl -H "Cf-Access-Authenticated-User-Email: admin@example.com" \
     https://your-portal.com/api/logs?limit=10000 > logs_export.json
```

## Compliance Checklist

- ✅ **Data Minimization**: Only necessary data is logged
- ✅ **Storage Limitation**: 90-day maximum retention (configurable)
- ✅ **Automatic Deletion**: Old data automatically removed
- ✅ **Right to Access**: API endpoint for data retrieval
- ✅ **Right to Erasure**: Automatic erasure after retention period
- ✅ **Data Portability**: JSON export available
- ✅ **Security**: Thread-safe logging, restricted file permissions
- ✅ **Transparency**: Full documentation of data processing

## Legal Basis for Processing

The legal basis for processing personal data in the HA-Edu portal is:

1. **Legitimate Interest** (Article 6(1)(f)):
   - Security monitoring and incident response
   - System administration and troubleshooting
   - Preventing abuse and unauthorized access

2. **Consent** (Article 6(1)(a)):
   - Users consent to logging when using the portal
   - Clear documentation of what is logged

## Recommendations

1. **Review Retention Period**: Ensure 90 days meets your specific requirements
2. **Document Processing**: Maintain records of processing activities
3. **Privacy Policy**: Include logging in your privacy policy
4. **User Notification**: Inform users about logging practices
5. **Regular Audits**: Periodically review log data and retention

## Testing

Verify GDPR compliance:

```bash
# Run GDPR compliance tests
python3 test_log_retention.py

# Verify retention configuration
docker exec ha-edu-portal env | grep LOG_RETENTION_DAYS
```

## References

- GDPR Article 5: Principles relating to processing of personal data
- GDPR Article 6: Lawfulness of processing
- GDPR Article 15: Right of access by the data subject
- GDPR Article 17: Right to erasure ('right to be forgotten')
- GDPR Article 20: Right to data portability

## Support

For questions about GDPR compliance or data processing:
1. Review the [LOGGING.md](LOGGING.md) documentation
2. Check the configuration in your deployment
3. Contact your data protection officer or legal counsel
