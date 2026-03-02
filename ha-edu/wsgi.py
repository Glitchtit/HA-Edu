"""WSGI entry point for the HA-Edu Portal application.

This module applies gevent monkey-patching before importing the Flask app
to avoid MonkeyPatchWarning about SSL being imported before monkey-patching.

This is the recommended approach per gevent documentation:
https://www.gevent.org/api/gevent.monkey.html
"""

# Apply gevent monkey-patching FIRST, before any other imports
# This must be done before importing any modules that use SSL, socket, etc.
from gevent import monkey
monkey.patch_all()

# Now import the Flask app (after monkey-patching is complete)
from app import app

# Expose the app object for Gunicorn
# Gunicorn will look for an 'application' variable by default
application = app
