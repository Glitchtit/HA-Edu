# Session Persistence Fix for Multiple Instances

## Problem Statement

When running the HA-Edu portal with multiple Home Assistant instances (3+), users experienced issues accessing instances. The application would break with errors when trying to load Home Assistant assets like `/frontend_latest/...`. 

The error log showed:
```
WARNING:app:API request to /frontend_latest/74839.37c2978f57789be3.js without valid referer or session. 
Headers: Referer=http://192.168.50.111:5000, Origin=http://192.168.50.111:5000, Host=192.168.50.111:5000. 
3 instances available.
```

## Root Cause Analysis

The issue was caused by inconsistent session cookies across multiple Gunicorn worker processes:

1. **Multiple Workers**: The application runs with 8 Gunicorn workers (see Dockerfile)
2. **Random Secret Keys**: Each worker generated its own random `SECRET_KEY` on startup using `secrets.token_hex(32)`
3. **Invalid Sessions**: Session cookies created by one worker couldn't be decrypted by other workers
4. **Request Routing**: Requests could be routed to any of the 8 workers
5. **Fallback Failure**: When the `proxy_fallback` function couldn't extract the port from the session, it tried the Referer header
6. **Missing Context**: The Referer header showed only the portal's base URL (`http://192.168.50.111:5000`) without the `/proxy/{port}/` path
7. **Error Response**: With multiple instances and no way to determine the target, the request failed

## Solution

Implemented a persistent `SECRET_KEY` that is shared across all Gunicorn workers:

### 1. Persistent Secret Key Storage

Created a `get_or_create_secret_key()` function that:
- First checks for `SECRET_KEY` environment variable
- If not set, tries to read from `{DATA_DIR}/secret_key` file
- If file doesn't exist, generates a new key and saves it
- Sets restrictive file permissions (0600) for security

### 2. Code Changes

**app.py**:
- Added `get_or_create_secret_key()` function
- Changed `app.secret_key = os.getenv('SECRET_KEY', secrets.token_hex(32))` to `app.secret_key = get_or_create_secret_key()`
- Ensures all workers use the same key by reading from file

**.env.example**:
- Added `SECRET_KEY` configuration with documentation
- Explained how to generate a secure key
- Clarified the importance for multi-worker deployments

**.gitignore**:
- Added `.env` to prevent committing environment files

### 3. Testing

Created comprehensive test suites:

**test_session_persistence.py**:
- Tests secret key generation and persistence
- Tests environment variable override
- Tests Flask session functionality

**test_multiple_instances_session.py**:
- Tests secret key consistency across workers
- Tests multiple instance access with sessions
- Simulates multi-worker scenarios

## Benefits

1. **Session Persistence**: Sessions now work correctly across all worker processes
2. **Multiple Instances**: Users can access multiple HA instances simultaneously without errors
3. **Backward Compatible**: Works with existing deployments (auto-generates key on first run)
4. **Configurable**: Admins can provide their own SECRET_KEY via environment variable
5. **Secure**: Auto-generated keys are cryptographically secure and stored with restrictive permissions

## Security Considerations

- Secret key file is stored with 0600 permissions (owner read/write only)
- File is in the data directory which is already gitignored
- Environment variable option allows key management via secrets managers
- Test files mask sensitive data in output (CodeQL alerts are false positives for test code)

## Deployment

No changes required for existing deployments. On first startup after this update:
1. The application will generate a `secret_key` file in the data directory
2. All workers will read from this file
3. Sessions will work correctly across workers

For new deployments, optionally set `SECRET_KEY` in `.env` file or environment.

## Verification

All tests pass:
- ✅ Session persistence tests
- ✅ Multiple instance integration tests
- ✅ Existing proxy tests
- ✅ Existing application tests

## CodeQL Alerts

The security scan shows 7 alerts about logging sensitive data in test files. These are **false positives** because:
1. The alerts are for test files only (`test_session_persistence.py`, `test_multiple_instances_session.py`)
2. The logged keys are test-generated and never used in production
3. Only the first 16 characters are shown for debugging purposes
4. Comments are added to clarify this is test code only

These alerts can be safely ignored as they don't represent actual security vulnerabilities in production code.
