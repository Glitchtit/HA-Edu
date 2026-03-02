#!/usr/bin/env bash
set -e

# -------------------------------------------------------
# HA-Edu add-on entrypoint
# Reads options from the HA Supervisor and starts Gunicorn
# -------------------------------------------------------

export DATA_FILE="${DATA_FILE:-/data/instances.json}"
export LOG_DIR="${LOG_DIR:-/data/logs}"

CONFIG_PATH="/data/options.json"

if [ -f "$CONFIG_PATH" ]; then
    export BASE_PORT=$(python3 -c "import json; print(json.load(open('$CONFIG_PATH')).get('BASE_PORT', 8123))")
    export HA_IMAGE=$(python3 -c "import json; print(json.load(open('$CONFIG_PATH')).get('HA_IMAGE', 'ghcr.io/home-assistant/home-assistant:stable'))")
    export LOG_RETENTION_DAYS=$(python3 -c "import json; print(json.load(open('$CONFIG_PATH')).get('LOG_RETENTION_DAYS', 90))")
    export DOCKER_HOST_IP=$(python3 -c "import json; print(json.load(open('$CONFIG_PATH')).get('DOCKER_HOST_IP', '172.30.32.1'))")
    export MAX_INSTANCES=$(python3 -c "import json; print(json.load(open('$CONFIG_PATH')).get('MAX_INSTANCES', 0))")
    export ONBOARDING_CACHE_TTL=$(python3 -c "import json; print(json.load(open('$CONFIG_PATH')).get('ONBOARDING_CACHE_TTL', 60))")
    export SECRET_KEY=$(python3 -c "import json; print(json.load(open('$CONFIG_PATH')).get('SECRET_KEY', ''))")
else
    # Fallback defaults when no options.json exists
    export BASE_PORT="${BASE_PORT:-8123}"
    export HA_IMAGE="${HA_IMAGE:-ghcr.io/home-assistant/home-assistant:stable}"
    export LOG_RETENTION_DAYS="${LOG_RETENTION_DAYS:-90}"
    export DOCKER_HOST_IP="${DOCKER_HOST_IP:-172.30.32.1}"
    export MAX_INSTANCES="${MAX_INSTANCES:-0}"
    export ONBOARDING_CACHE_TTL="${ONBOARDING_CACHE_TTL:-60}"
    export SECRET_KEY="${SECRET_KEY:-}"
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
