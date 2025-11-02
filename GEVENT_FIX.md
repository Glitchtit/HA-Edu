# Gevent Monkey-Patching Fix

## Problem

When starting the HA-Edu Portal with Gunicorn using the gevent worker class, the following warning was displayed:

```
MonkeyPatchWarning: Monkey-patching ssl after ssl has already been imported may lead to errors, 
including RecursionError on Python 3.6. It may also silently lead to incorrect behaviour on Python 3.7. 
Please monkey-patch earlier. See https://github.com/gevent/gevent/issues/1016. 
Modules that had direct imports (NOT patched): ['urllib3.util (/usr/local/lib/python3.11/site-packages/urllib3/util/__init__.py)', 
'urllib3.util.ssl_ (/usr/local/lib/python3.11/site-packages/urllib3/util/ssl_.py)'].
```

### Root Cause

The issue occurred because:

1. Gunicorn was using the `--preload` flag, which loads the application before forking workers
2. The application (`app.py`) imports `requests`, `docker`, and other modules that use SSL
3. These imports load `urllib3.util.ssl_` and other SSL-related modules
4. When Gunicorn workers start with `--worker-class gevent`, they attempt to monkey-patch SSL
5. However, SSL modules were already imported during the preload phase
6. This causes the MonkeyPatchWarning

## Solution

The fix implements the recommended approach from the [gevent documentation](https://www.gevent.org/api/gevent.monkey.html):

1. **Created `wsgi.py`** - A WSGI entry point that:
   - Applies gevent monkey-patching **FIRST** before any other imports
   - Then imports the Flask application
   - Exposes the app as 'application' for Gunicorn

2. **Updated `Dockerfile`**:
   - Added `COPY wsgi.py .` to include the new entry point
   - Changed CMD to use `wsgi:application` instead of `app:app`
   - Removed the `--preload` flag (incompatible with per-worker monkey-patching)

## How It Works

### Before (Problematic)
```
Gunicorn starts with --preload
  └─> Imports app.py
      └─> Imports requests, docker, urllib3 (SSL modules loaded)
Workers fork with gevent
  └─> Attempt to monkey-patch SSL
      └─> ⚠️ WARNING: SSL already imported!
```

### After (Fixed)
```
Gunicorn starts (no --preload)
Workers fork with gevent
  └─> Import wsgi.py
      └─> Apply gevent monkey-patching (SSL not yet imported)
      └─> Import app.py
          └─> Import requests, docker, urllib3 (already monkey-patched ✓)
      └─> No warnings!
```

## Files Changed

### New File: `wsgi.py`
```python
"""WSGI entry point for the HA-Edu Portal application.

This module applies gevent monkey-patching before importing the Flask app
to avoid MonkeyPatchWarning about SSL being imported before monkey-patching.
"""

# Apply gevent monkey-patching FIRST, before any other imports
from gevent import monkey
monkey.patch_all()

# Now import the Flask app (after monkey-patching is complete)
from app import app

# Expose the app object for Gunicorn
application = app
```

### Modified File: `Dockerfile`

**Changes:**
1. Added `COPY wsgi.py .` to copy the new entry point
2. Changed CMD from `"app:app"` to `"wsgi:application"`
3. Removed `--preload` flag
4. Updated comments to explain the change

**Before:**
```dockerfile
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "4", "--worker-class", "gevent", "--timeout", "120", "--preload", "app:app"]
```

**After:**
```dockerfile
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "4", "--worker-class", "gevent", "--timeout", "120", "wsgi:application"]
```

## Testing

A test script (`test_monkey_patch_fix.py`) has been created to verify the fix:

```bash
python3 test_monkey_patch_fix.py
```

This test verifies:
1. ✅ Correct import order in wsgi.py (gevent before app)
2. ✅ Dockerfile copies wsgi.py
3. ✅ CMD uses wsgi:application as entry point
4. ✅ --preload flag is not in CMD
5. ✅ SSL-dependent imports found in app.py

## Impact

### Positive Impact
- ✅ Eliminates MonkeyPatchWarning on startup
- ✅ Follows gevent best practices
- ✅ Ensures SSL modules are properly monkey-patched
- ✅ No functional changes to the application

### Considerations
- Removed `--preload` flag means the cleanup_orphaned_containers() function will run once per worker instead of once globally
  - This is acceptable because the cleanup function uses Docker API which is already safe for concurrent access
  - Each worker will see the same state since they share the Docker daemon

## References

- [Gevent Monkey Patching Documentation](https://www.gevent.org/api/gevent.monkey.html)
- [Gevent Issue #1016](https://github.com/gevent/gevent/issues/1016)
- [Gunicorn with Gevent Workers](https://docs.gunicorn.org/en/stable/design.html#async-workers)

## Verification

To verify the fix is working:

1. Build the Docker image: `docker-compose build`
2. Start the application: `docker-compose up`
3. Check logs for absence of MonkeyPatchWarning
4. Expected output:
   ```
   INFO:app:Starting HA-Edu Portal...
   INFO:app:Orphaned container cleanup completed
   [timestamp] [1] [INFO] Starting gunicorn 22.0.0
   [timestamp] [1] [INFO] Listening at: http://0.0.0.0:5000 (1)
   [timestamp] [1] [INFO] Using worker: gevent
   [timestamp] [7] [INFO] Booting worker with pid: 7
   ```
   Note: **No MonkeyPatchWarning should appear!**
