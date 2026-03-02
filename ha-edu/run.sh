#!/usr/bin/env bash
set -e

# -------------------------------------------------------
# HA-Edu add-on entrypoint
# Reads options from the HA Supervisor and starts Gunicorn
# -------------------------------------------------------

# Export add-on options as environment variables
export BASE_PORT
export HA_IMAGE
export LOG_RETENTION_DAYS
export DOCKER_HOST_IP
export DATA_FILE="${DATA_FILE:-/data/instances.json}"
export LOG_DIR="${LOG_DIR:-/data/logs}"

CONFIG_PATH="/data/options.json"

if [ -f "$CONFIG_PATH" ]; then
    BASE_PORT=$(python3 -c "import json; print(json.load(open('$CONFIG_PATH')).get('BASE_PORT', 8123))")
    HA_IMAGE=$(python3 -c "import json; print(json.load(open('$CONFIG_PATH')).get('HA_IMAGE', 'ghcr.io/home-assistant/home-assistant:stable'))")
    LOG_RETENTION_DAYS=$(python3 -c "import json; print(json.load(open('$CONFIG_PATH')).get('LOG_RETENTION_DAYS', 90))")
    DOCKER_HOST_IP=$(python3 -c "import json; print(json.load(open('$CONFIG_PATH')).get('DOCKER_HOST_IP', '172.30.32.1'))")

    # Optional settings
    ADMIN_PASSWORD=$(python3 -c "import json; print(json.load(open('$CONFIG_PATH')).get('ADMIN_PASSWORD', ''))")
    TEACHER_USERNAME=$(python3 -c "import json; print(json.load(open('$CONFIG_PATH')).get('TEACHER_USERNAME', ''))")
    TEACHER_PASSWORD=$(python3 -c "import json; print(json.load(open('$CONFIG_PATH')).get('TEACHER_PASSWORD', ''))")
    MAX_INSTANCES=$(python3 -c "import json; print(json.load(open('$CONFIG_PATH')).get('MAX_INSTANCES', 0))")
    ONBOARDING_CACHE_TTL=$(python3 -c "import json; print(json.load(open('$CONFIG_PATH')).get('ONBOARDING_CACHE_TTL', 60))")

    export ADMIN_PASSWORD TEACHER_USERNAME TEACHER_PASSWORD MAX_INSTANCES ONBOARDING_CACHE_TTL
fi

# Ensure data directories exist
mkdir -p "$(dirname "$DATA_FILE")"
mkdir -p "$LOG_DIR"

echo "Starting HA-Edu portal on port 5000 ..."
exec gunicorn \
    --bind 0.0.0.0:5000 \
    --workers 4 \
    --worker-class gevent \
    --timeout 120 \
    wsgi:application
