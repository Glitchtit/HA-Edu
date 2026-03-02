import os
import json
import logging
import secrets
import re
import threading
import bcrypt
import urllib.parse
import ipaddress
import time
from flask import Flask, render_template, request, jsonify, Response, stream_with_context, session
from flask_sock import Sock
import docker
from datetime import datetime
import requests
import simple_websocket
from interaction_logger import interaction_logger

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Disable Flask's default static folder to avoid conflicts with Home Assistant's /static/ paths
app = Flask(__name__, static_folder=None)

def get_or_create_secret_key():
    """Get or create a persistent secret key for session management
    
    This ensures all Gunicorn workers share the same secret key, which is critical
    for session cookies to work correctly across multiple workers.
    
    The secret key is:
    1. Read from SECRET_KEY environment variable if set, OR
    2. Read from secret_key file (in same directory as DATA_FILE) if it exists, OR
    3. Generated and saved to secret_key file for future use
    
    Returns:
        str: The secret key for Flask session management
    """
    # Check environment variable first
    env_secret = os.getenv('SECRET_KEY', '').strip()
    if env_secret:
        logger.info('Using SECRET_KEY from environment variable')
        return env_secret
    
    # Path to store the secret key (in same directory as DATA_FILE)
    data_dir = os.path.dirname(os.getenv('DATA_FILE', '/data/instances.json'))
    secret_key_file = os.path.join(data_dir, 'secret_key')
    
    try:
        # Try to read existing secret key
        if os.path.exists(secret_key_file):
            with open(secret_key_file, 'r') as f:
                key = f.read().strip()
                if key:
                    logger.info(f'Loaded SECRET_KEY from {secret_key_file}')
                    return key
        
        # Generate new secret key
        new_key = secrets.token_hex(32)
        
        # Ensure directory exists
        os.makedirs(data_dir, exist_ok=True)
        
        # Save it for future use
        with open(secret_key_file, 'w') as f:
            f.write(new_key)
        
        # Set restrictive permissions (owner read/write only)
        os.chmod(secret_key_file, 0o600)
        
        logger.info(f'Generated new SECRET_KEY and saved to {secret_key_file}')
        return new_key
        
    except Exception as e:
        logger.error(f'Failed to load or create persistent secret key: {e}. Falling back to temporary key.')
        # Fallback to temporary key (not recommended but better than crashing)
        return secrets.token_hex(32)

# Set a secret key for session management
# Must be consistent across all Gunicorn workers for sessions to work correctly
app.secret_key = get_or_create_secret_key()
client = docker.from_env()

# Initialize WebSocket support
sock = Sock(app)

# Thread lock for port allocation to prevent race conditions when multiple
# students create instances simultaneously
_port_allocation_lock = threading.Lock()

# Semaphore to limit concurrent temporary container operations
# This prevents overwhelming the Docker daemon when many instances are created
# Maximum of 5 concurrent temporary container operations (config copy, onboarding check, teacher account)
# Ensures stable performance even with 15+ instances being created simultaneously
_temp_container_semaphore = threading.Semaphore(5)

# Cache for onboarding status to avoid redundant Docker container checks
# Key: volume_name, Value: (timestamp, onboarded_status)
_onboarding_cache = {}
_onboarding_cache_lock = threading.Lock()

# Configuration
DATA_FILE = os.getenv('DATA_FILE', '/data/instances.json')
BASE_PORT = int(os.getenv('BASE_PORT', '8124'))
# MAX_INSTANCES removed - no limit on instances, ports assigned dynamically
HA_IMAGE = os.getenv('HA_IMAGE', 'ghcr.io/home-assistant/home-assistant:stable')
# Maximum instances for non-admin users (0 or None means unlimited)
MAX_INSTANCES_STR = os.getenv('MAX_INSTANCES', '').strip()
MAX_INSTANCES = int(MAX_INSTANCES_STR) if MAX_INSTANCES_STR else 0
MASTER_CONFIG_PATH = os.path.join(os.path.dirname(__file__), 'master_configuration.yaml')
# Onboarding cache TTL in seconds - how long to cache onboarding status checks
ONBOARDING_CACHE_TTL = int(os.getenv('ONBOARDING_CACHE_TTL', '60'))
# Docker host IP for accessing instance containers from within the portal container
# Use 'host.docker.internal' (Docker Desktop) or 'gateway.docker.internal' (Linux)
# Or set to 'localhost' when running the portal directly on the host (not in Docker)
DOCKER_HOST_IP = os.getenv('DOCKER_HOST_IP', 'host.docker.internal')

# Local image name for student containers to avoid HA Supervisor
# "unsupported software" warning about ghcr.io/home-assistant/home-assistant
STUDENT_IMAGE_REPO = 'local/ha-edu-student'

# Paths that trigger access logging (to avoid logging every asset request)
ACCESS_LOG_PATHS = ['', 'index.html', 'lovelace']

def is_admin_user(request):
    """Check if the current user has admin access
    
    Admin access is granted if the user is logged in with an account
    that has the 'admin' role.
    
    Args:
        request: Flask request object
        
    Returns:
        bool: True if user has admin access, False otherwise
    """
    username = session.get('username')
    if username:
        users = load_users()
        user = users.get(username)
        if user and user.get('role') == 'admin':
            logger.debug(f'Admin access granted for admin user: {username}')
            return True
    
    logger.debug(f'Admin access denied for user: {session.get("username")}')
    return False


def load_data():
    """Load all data from JSON file"""
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r') as f:
            data = json.load(f)
            # Handle legacy format - if data is just instances dict
            if 'instances' not in data and 'settings' not in data:
                return {'instances': data, 'settings': {'instance_creation_enabled': True}}
            return data
    return {'instances': {}, 'settings': {'instance_creation_enabled': True}}

def save_data(data):
    """Save all data to JSON file"""
    os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)
    with open(DATA_FILE, 'w') as f:
        json.dump(data, f, indent=2)

def load_instances():
    """Load instances from JSON file"""
    data = load_data()
    return data.get('instances', {})

def save_instances(instances):
    """Save instances to JSON file"""
    data = load_data()
    data['instances'] = instances
    save_data(data)

def load_settings():
    """Load settings from JSON file"""
    data = load_data()
    return data.get('settings', {'instance_creation_enabled': True})

def save_settings(settings):
    """Save settings to JSON file"""
    data = load_data()
    data['settings'] = settings
    save_data(data)

# ---------------------------------------------------------------------------
# User account management
# ---------------------------------------------------------------------------

def load_users():
    """Load user accounts from JSON file"""
    data = load_data()
    return data.get('users', {})

def save_users(users):
    """Save user accounts to JSON file"""
    data = load_data()
    data['users'] = users
    save_data(data)

def ensure_admin_account():
    """Ensure a default admin account exists.

    On first run, creates an admin account with credentials admin / admin.
    The user will be prompted to change the credentials on first login.
    """
    users = load_users()
    # Check if any admin account already exists
    has_admin = any(u.get('role') == 'admin' for u in users.values())
    if not has_admin:
        users['admin'] = {
            'password_hash': hash_password('admin'),
            'role': 'admin',
            'created_at': datetime.now().isoformat(),
        }
        save_users(users)
        logger.info('Auto-created default admin account (admin / admin)')

def pull_and_retag_image():
    """Pull the HA image and re-tag it for student instances.
    
    Re-tags the image to a local name to prevent HA Supervisor from
    flagging student containers as 'unsupported software'.
    
    Returns:
        str: The image name to use for creating student containers.
    """
    tag = HA_IMAGE.partition(':')[2] or 'latest'
    student_image = f'{STUDENT_IMAGE_REPO}:{tag}'
    
    try:
        logger.info(f'Pulling latest image: {HA_IMAGE}')
        client.images.pull(HA_IMAGE)
    except docker.errors.APIError as e:
        logger.warning(f'Failed to pull latest image, using cached version: {e}')
    
    # Try to re-tag the pulled/cached image
    try:
        image = client.images.get(HA_IMAGE)
        image.tag(STUDENT_IMAGE_REPO, tag)
        logger.info(f'Re-tagged image as: {student_image}')
        return student_image
    except docker.errors.ImageNotFound:
        logger.warning(f'Original image {HA_IMAGE} not found locally')
    
    # Fall back to a previously re-tagged image if available
    try:
        client.images.get(student_image)
        logger.info(f'Using previously re-tagged image: {student_image}')
        return student_image
    except docker.errors.ImageNotFound:
        logger.warning(f'Could not re-tag image, using original: {HA_IMAGE}')
        return HA_IMAGE

def get_available_port():
    """Get next available port for a new instance
    
    Dynamically assigns ports starting from BASE_PORT.
    Reuses ports from deleted instances before assigning new ones.
    Also checks for ports actually in use by running containers.
    """
    instances = load_instances()
    used_ports = set(inst['port'] for inst in instances.values())
    
    # Get ports used by running containers
    try:
        containers = client.containers.list(all=True)
        for container in containers:
            # Check if container has port mappings
            if container.attrs.get('NetworkSettings', {}).get('Ports'):
                ports_dict = container.attrs['NetworkSettings']['Ports']
                for container_port, host_bindings in ports_dict.items():
                    if host_bindings:
                        for binding in host_bindings:
                            if binding and 'HostPort' in binding:
                                try:
                                    host_port = int(binding['HostPort'])
                                    used_ports.add(host_port)
                                except (ValueError, TypeError):
                                    pass
    except Exception as e:
        logger.warning(f'Failed to check running containers for port usage: {str(e)}')
    
    # Start from BASE_PORT and find the first available port
    port = BASE_PORT
    while port in used_ports:
        port += 1
    
    return port

def update_instances_status(instances):
    """Update status for all instances by checking actual container state
    
    Args:
        instances: Dictionary of instances to update (modified in place)
    """
    for server_name, instance in instances.items():
        try:
            container = client.containers.get(instance['container_id'])
            instance['status'] = container.status
        except docker.errors.NotFound:
            instance['status'] = 'removed'
        except docker.errors.APIError as e:
            logger.warning(f'Docker API error getting status for {server_name}: {str(e)}')
            instance['status'] = 'unknown'
        except Exception as e:
            logger.warning(f'Unexpected error getting status for {server_name}: {str(e)}')
            instance['status'] = 'unknown'

def cleanup_orphaned_containers():
    """Clean up containers that are running but not tracked in instances.json
    
    This handles cases where containers were left running from previous sessions
    or when instances.json was lost/corrupted.
    """
    try:
        instances = load_instances()
        tracked_container_ids = set(inst['container_id'] for inst in instances.values())
        
        # Get all containers with ha-edu prefix
        all_containers = client.containers.list(all=True, filters={'name': 'ha-edu-'})
        
        # Track if any instance data was modified to optimize file I/O
        has_instance_updates = False
        for container in all_containers:
            # Skip the portal container itself
            if container.name == 'ha-edu-portal':
                continue
            
            if container.id not in tracked_container_ids:
                logger.info(f'Found orphaned container: {container.name} ({container.id[:12]})')
                try:
                    # Try to find if this container belongs to a tracked instance by name
                    found = False
                    for server_name, inst in instances.items():
                        if inst.get('container_name') == container.name:
                            # Update the instance with correct container ID
                            logger.info(f'Updating instance {server_name} with container ID {container.id[:12]}')
                            inst['container_id'] = container.id
                            inst['status'] = container.status
                            instances[server_name] = inst
                            found = True
                            has_instance_updates = True
                            break
                    
                    if not found:
                        # Truly orphaned - stop and remove
                        logger.info(f'Removing truly orphaned container: {container.name}')
                        if container.status == 'running':
                            container.stop(timeout=10)
                        container.remove()
                except Exception as e:
                    logger.error(f'Failed to handle orphaned container {container.name}: {str(e)}')
        
        # Save instances only once if any updates were made across all containers
        if has_instance_updates:
            save_instances(instances)
        
        logger.info('Orphaned container cleanup completed')
        
    except Exception as e:
        logger.error(f'Failed to cleanup orphaned containers: {str(e)}', exc_info=True)

def copy_master_config_to_volume(volume_name):
    """Copy master configuration.yaml to a Docker volume
    
    Creates a temporary container to copy the master configuration
    into the specified volume's /config directory.
    Uses semaphore to limit concurrent operations.
    """
    # Use semaphore to limit concurrent temporary container operations
    with _temp_container_semaphore:
        temp_container = None
        try:
            # Read the master configuration file
            with open(MASTER_CONFIG_PATH, 'r') as f:
                master_config_content = f.read()
            
            # Pull alpine image if not present
            try:
                client.images.get('alpine:latest')
            except docker.errors.ImageNotFound:
                logger.info('Pulling alpine:latest image...')
                client.images.pull('alpine:latest')
            
            # Create a temporary container with the volume mounted
            # Use alpine image - it's lightweight and has sh
            temp_container = client.containers.create(
                'alpine:latest',
                command=['sh', '-c', 'sleep 30'],
                volumes={volume_name: {'bind': '/config', 'mode': 'rw'}}
            )
            
            # Start the container
            temp_container.start()
            
            # Write the master config and empty files for automations, scripts, and scenes
            # These files are required by the master configuration
            # Use exec_run to write files
            temp_container.exec_run(
                ['sh', '-c', f'cat > /config/configuration.yaml << \'EOF\'\n{master_config_content}\nEOF']
            )
            temp_container.exec_run(['sh', '-c', 'echo "[]" > /config/automations.yaml'])
            temp_container.exec_run(['sh', '-c', 'echo "{}" > /config/scripts.yaml'])
            temp_container.exec_run(['sh', '-c', 'echo "[]" > /config/scenes.yaml'])
            
            # Stop and clean up
            temp_container.stop(timeout=5)
            temp_container.remove()
            
            logger.info(f'Successfully copied master configuration to volume {volume_name}')
            return True
            
        except Exception as e:
            logger.error(f'Failed to copy master configuration to volume {volume_name}: {str(e)}', exc_info=True)
            # Clean up on error
            if temp_container:
                try:
                    temp_container.stop(timeout=5)
                    temp_container.remove(force=True)
                except Exception as cleanup_error:
                    logger.warning(f'Failed to cleanup temp container: {cleanup_error}')
            return False

def check_instance_onboarding_complete(volume_name):
    """Check if a Home Assistant instance has completed onboarding
    
    Checks for the existence of required .storage files in the volume,
    which indicates that at least one user has been created and the
    authentication provider is configured.
    Uses semaphore to limit concurrent operations.
    
    Args:
        volume_name: Name of the Docker volume to check
        
    Returns:
        bool: True if onboarding is complete, False otherwise
    """
    # Use semaphore to limit concurrent temporary container operations
    with _temp_container_semaphore:
        temp_container = None
        try:
            # Pull alpine image if not present
            try:
                client.images.get('alpine:latest')
            except docker.errors.ImageNotFound:
                logger.info('Pulling alpine:latest image...')
                client.images.pull('alpine:latest')
            
            # Create a temporary container to check both required files
            # Both files are needed for create_teacher_account to work
            temp_container = client.containers.create(
                'alpine:latest',
                command=['sh', '-c', 'test -f /config/.storage/auth && test -f /config/.storage/auth_provider.homeassistant && echo "exists" || echo "missing"'],
                volumes={volume_name: {'bind': '/config', 'mode': 'ro'}}
            )
            
            # Start and wait for container
            temp_container.start()
            exit_code = temp_container.wait(timeout=10)
            
            # Get output
            output = temp_container.logs().decode('utf-8').strip()
            
            # Clean up
            temp_container.remove()
            
            return output == 'exists'
            
        except Exception as e:
            logger.error(f'Failed to check onboarding status for volume {volume_name}: {str(e)}', exc_info=True)
            # Clean up on error
            if temp_container:
                try:
                    temp_container.remove(force=True)
                except Exception as cleanup_error:
                    logger.warning(f'Failed to cleanup temp container: {cleanup_error}')
            return False

def check_instance_onboarding_complete_cached(volume_name):
    """Cached wrapper for check_instance_onboarding_complete
    
    Uses an in-memory cache with TTL to avoid redundant Docker container checks
    when checking onboarding status for multiple instances.
    
    Args:
        volume_name: Name of the Docker volume to check
        
    Returns:
        bool: True if onboarding is complete, False otherwise
    """
    current_time = time.time()
    
    # Check cache first
    with _onboarding_cache_lock:
        if volume_name in _onboarding_cache:
            cached_time, cached_status = _onboarding_cache[volume_name]
            # Return cached value if still valid
            if current_time - cached_time < ONBOARDING_CACHE_TTL:
                return cached_status
    
    # Cache miss or expired - perform actual check
    onboarded = check_instance_onboarding_complete(volume_name)
    
    # Update cache
    with _onboarding_cache_lock:
        _onboarding_cache[volume_name] = (current_time, onboarded)
    
    return onboarded

def create_teacher_account(volume_name, teacher_username, teacher_password, reset_if_exists=False):
    """Create a teacher admin account in a Home Assistant instance
    
    Directly manipulates .storage/auth and .storage/auth_provider.homeassistant
    files in the instance volume using a temporary Alpine container.
    Uses semaphore to limit concurrent operations.
    
    Args:
        volume_name: Name of the Docker volume
        teacher_username: Username for the teacher account
        teacher_password: Password for the teacher account
        reset_if_exists: If True, reset the password if the account already exists
        
    Returns:
        tuple: (success: bool, message: str)
    """
    # Use semaphore to limit concurrent temporary container operations
    with _temp_container_semaphore:
        temp_container = None
        try:
            # Pull alpine image if not present
            try:
                client.images.get('alpine:latest')
            except docker.errors.ImageNotFound:
                logger.info('Pulling alpine:latest image...')
                client.images.pull('alpine:latest')
            
            # Create a temporary container with the volume mounted
            temp_container = client.containers.create(
                'alpine:latest',
                command=['sh', '-c', 'sleep 60'],
                volumes={volume_name: {'bind': '/config', 'mode': 'rw'}}
            )
            
            # Start the container
            temp_container.start()
            
            # Install Python in the container for bcrypt hashing
            install_result = temp_container.exec_run(['sh', '-c', 'apk add --no-cache python3 py3-pip'])
            if install_result.exit_code != 0:
                logger.error(f'Failed to install Python in temp container: {install_result.output.decode()}')
                temp_container.stop(timeout=5)
                temp_container.remove()
                return False, 'Failed to install dependencies in temporary container'
            
            # Install bcrypt
            bcrypt_result = temp_container.exec_run(['sh', '-c', 'pip3 install --break-system-packages bcrypt'])
            if bcrypt_result.exit_code != 0:
                logger.error(f'Failed to install bcrypt: {bcrypt_result.output.decode()}')
                temp_container.stop(timeout=5)
                temp_container.remove()
                return False, 'Failed to install bcrypt library'
            
            # Generate bcrypt hash for the password
            hash_script = f"""
import bcrypt
import json
import uuid
import os
import base64
from datetime import datetime, timezone

TEACHER_USERNAME = {teacher_username!r}
TEACHER_PASSWORD = {teacher_password!r}
RESET_IF_EXISTS = {reset_if_exists!r}

now = datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')

def build_entry_from_template(template, base):
    '''Merge structure from template into base with safe defaults.'''
    if not isinstance(template, dict):
        return base

    result = dict(base)
    for key, value in template.items():
        if key in base:
            continue

        if isinstance(value, list):
            result[key] = []
        elif isinstance(value, dict):
            result[key] = dict()
        else:
            result[key] = None

    return result

with open('/config/.storage/auth', 'r') as f:
    auth_data = json.load(f)

with open('/config/.storage/auth_provider.homeassistant', 'r') as f:
    provider_data = json.load(f)

person_path = '/config/.storage/person'
if os.path.exists(person_path):
    with open(person_path, 'r') as f:
        person_data = json.load(f)
else:
    person_data = {{
        'data': {{
            'items': []
        }}
    }}

auth_data.setdefault('data', dict())
auth_users = auth_data['data'].setdefault('users', [])
auth_credentials = auth_data['data'].setdefault('credentials', [])
provider_root = provider_data.setdefault('data', dict())
provider_users_list = provider_root.setdefault('users', [])
person_root = person_data.setdefault('data', dict())
person_items = person_root.setdefault('items', [])

# Check if teacher user already exists
existing_users = [
    u for u in auth_users
    if u.get('username') == TEACHER_USERNAME
]
if existing_users:
    if not RESET_IF_EXISTS:
        print('exists')
        exit(0)
    # Reset existing account - update password in provider
    existing_user = existing_users[0]
    user_id = existing_user['id']
    
    # Generate new password hash
    password_hash_bytes = bcrypt.hashpw(
        TEACHER_PASSWORD.encode('utf-8'),
        bcrypt.gensalt(rounds=12)
    )
    password_hash = base64.b64encode(password_hash_bytes).decode('utf-8')
    
    # Update password in provider
    for provider_entry in provider_users_list:
        if provider_entry.get('user_id') == user_id or provider_entry.get('username') == TEACHER_USERNAME:
            # Update all possible password fields
            password_keys = ['password', 'password_hash', 'hashed_password']
            for key in password_keys:
                if key in provider_entry:
                    provider_entry[key] = password_hash
            break
    
    # Save updated files
    with open('/config/.storage/auth', 'w') as f:
        json.dump(auth_data, f, indent=2)
    
    with open('/config/.storage/auth_provider.homeassistant', 'w') as f:
        json.dump(provider_data, f, indent=2)
    
    with open(person_path, 'w') as f:
        json.dump(person_data, f, indent=2)
    
    print('reset')
    exit(0)

user_id = uuid.uuid4().hex
credential_id = uuid.uuid4().hex
provider_user_id = uuid.uuid4().hex

# Generate bcrypt hash and base64-encode it (required by Home Assistant)
password_hash_bytes = bcrypt.hashpw(
    TEACHER_PASSWORD.encode('utf-8'),
    bcrypt.gensalt(rounds=12)
)
password_hash = base64.b64encode(password_hash_bytes).decode('utf-8')

user_template = auth_users[0] if auth_users else dict()
credential_template = auth_credentials[0] if auth_credentials else dict()
provider_template = provider_users_list[0] if provider_users_list else dict()
person_template = person_items[0] if person_items else dict()

new_user = build_entry_from_template(
    user_template,
    {{
        'id': user_id,
        'group_ids': ['system-admin'],
        'is_owner': False,
        'is_active': True,
        'name': TEACHER_USERNAME,
        'system_generated': False,
        'local_only': False,
        'username': TEACHER_USERNAME,
        'created_at': now
    }}
)

# Ensure list fields don't share references
if 'group_ids' in new_user:
    new_user['group_ids'] = list(new_user.get('group_ids', ['system-admin']))
    if not new_user['group_ids']:
        new_user['group_ids'] = ['system-admin']
    if 'system-admin' not in new_user['group_ids']:
        new_user['group_ids'].append('system-admin')

if 'refresh_tokens' in new_user:
    new_user['refresh_tokens'] = []

if 'credentials' in new_user:
    new_user['credentials'] = []

new_credential = build_entry_from_template(
    credential_template,
    {{
        'id': credential_id,
        'user_id': user_id,
        'auth_provider_type': 'homeassistant',
        'auth_provider_id': None,
        'data': {{'username': TEACHER_USERNAME}},
        'is_active': True,
        'created_at': now,
        'last_used_at': None,
        'last_used_version': None
    }}
)

if isinstance(new_credential.get('data'), dict):
    new_credential['data'] = {{'username': TEACHER_USERNAME}}

provider_base = {{
    'id': provider_user_id,
    'user_id': user_id,
    'username': TEACHER_USERNAME,
    'password': password_hash,
    'name': TEACHER_USERNAME,
    'is_active': True,
    'system_generated': False,
    'local_only': False,
    'created_at': now,
    'last_used_at': None,
    'last_used_version': None
}}

password_keys = [
    'password',
    'password_hash',
    'hashed_password',
]
for key in password_keys:
    if key in provider_template and key not in provider_base:
        provider_base[key] = password_hash

if 'password_cleartext' in provider_template and 'password_cleartext' not in provider_base:
    provider_base['password_cleartext'] = None

if 'password_algorithm' in provider_template and 'password_algorithm' not in provider_base:
    provider_base['password_algorithm'] = provider_template.get('password_algorithm', 'bcrypt') or 'bcrypt'

if 'password_alg' in provider_template and 'password_alg' not in provider_base:
    provider_base['password_alg'] = provider_template.get('password_alg', 'bcrypt') or 'bcrypt'

if 'password_version' in provider_template and 'password_version' not in provider_base:
    provider_base['password_version'] = provider_template['password_version']

new_provider_entry = build_entry_from_template(
    provider_template,
    provider_base
)

for key in password_keys:
    new_provider_entry[key] = provider_base.get(key, password_hash)

if 'password_cleartext' in new_provider_entry:
    new_provider_entry['password_cleartext'] = None

auth_users.append(new_user)
auth_credentials.append(new_credential)
provider_users_list.append(new_provider_entry)

new_person = build_entry_from_template(
    person_template,
    {{
        'id': f'person_{{user_id}}',
        'name': TEACHER_USERNAME,
        'user_id': user_id,
        'device_trackers': [],
        'picture': None,
        'type': 'user'
    }}
)

if 'device_trackers' in new_person:
    new_person['device_trackers'] = []

if 'user_id' not in new_person or new_person['user_id'] is None:
    new_person['user_id'] = user_id

if 'name' not in new_person or not new_person['name']:
    new_person['name'] = TEACHER_USERNAME

person_items.append(new_person)

with open('/config/.storage/auth', 'w') as f:
    json.dump(auth_data, f, indent=2)

with open('/config/.storage/auth_provider.homeassistant', 'w') as f:
    json.dump(provider_data, f, indent=2)

with open(person_path, 'w') as f:
    json.dump(person_data, f, indent=2)

print('success')
"""
        
            # Write the script to the container
            temp_container.exec_run(['sh', '-c', f'cat > /tmp/create_user.py << \'EOF\'\n{hash_script}\nEOF'])
            
            # Run the script
            result = temp_container.exec_run(['python3', '/tmp/create_user.py'])
            
            # Clean up
            temp_container.stop(timeout=5)
            temp_container.remove()
            
            output = result.output.decode('utf-8').strip()
            
            if result.exit_code == 0:
                if output == 'exists':
                    logger.info(f'Teacher account already exists in volume {volume_name}')
                    return False, 'Teacher account already exists'
                elif output == 'reset':
                    logger.info(f'Successfully reset teacher account password in volume {volume_name}')
                    return True, 'Teacher account password reset successfully'
                elif output == 'success':
                    logger.info(f'Successfully created teacher account in volume {volume_name}')
                    return True, 'Teacher account created successfully'
            
            logger.error(f'Failed to create teacher account: {output}')
            return False, 'Failed to create teacher account'
            
        except Exception as e:
            logger.error(f'Failed to create teacher account in volume {volume_name}: {str(e)}', exc_info=True)
            # Clean up on error
            if temp_container:
                try:
                    temp_container.stop(timeout=5)
                    temp_container.remove(force=True)
                except Exception as cleanup_error:
                    logger.warning(f'Failed to cleanup temp container: {cleanup_error}')
            return False, 'An error occurred while creating teacher account'

def hash_password(password):
    """Hash a password using bcrypt
    
    Args:
        password: Plain text password to hash
        
    Returns:
        str: Hashed password
    """
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt(rounds=12)).decode('utf-8')

def verify_password(password, hashed):
    """Verify a password against a bcrypt hash
    
    Args:
        password: Plain text password to verify
        hashed: Bcrypt hash to compare against
        
    Returns:
        bool: True if password matches, False otherwise
    """
    return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))

# Ensure the default admin account exists on startup
ensure_admin_account()

def validate_instance_password(password, instance):
    """Validate password for instance operations (delete/reset)
    
    Checks the instance password (if set when instance was created).
    Admin users bypass this check entirely (handled at the route level).
    
    Args:
        password: Password to validate
        instance: Instance dictionary containing metadata
        
    Returns:
        bool: True if password is valid, False otherwise
    """
    # Check instance password (if set)
    if instance.get('instance_password_hash'):
        return verify_password(password, instance['instance_password_hash'])
    
    return False

def restart_instance_container(container_id):
    """Restart a Docker container
    
    Args:
        container_id: Docker container ID to restart
        
    Returns:
        tuple: (success: bool, message: str)
    """
    try:
        container = client.containers.get(container_id)
        container.restart(timeout=10)
        logger.info(f'Successfully restarted container {container_id[:12]}')
        return True, 'Instance restarted successfully'
    except docker.errors.NotFound:
        logger.error(f'Container {container_id} not found')
        return False, 'Instance not found'
    except docker.errors.APIError as e:
        logger.error(f'Docker API error restarting container {container_id}: {str(e)}')
        return False, 'Failed to restart instance'
    except Exception as e:
        logger.error(f'Unexpected error restarting container {container_id}: {str(e)}', exc_info=True)
        return False, 'An error occurred while restarting instance'

def get_user_identifier(request):
    """Get a unique identifier for the current user
    
    Returns the logged-in username from the session. In classroom settings,
    all students share the same IP address, so account-based tracking is required.
    
    Args:
        request: Flask request object
        
    Returns:
        str: Username, or None if not logged in
    """
    username = session.get('username')
    return username if username else None

def get_user_info_for_logging(request):
    """Get user information for logging purposes
    
    Args:
        request: Flask request object
        
    Returns:
        tuple: (user_id, user_type) where user_type is 'admin' or 'user'
    """
    user_id = get_user_identifier(request)
    user_type = 'admin' if is_admin_user(request) else 'user'
    
    # If no authenticated user, use IP address as fallback
    if not user_id:
        user_id = request.remote_addr or 'unknown'
    
    return user_id, user_type

def can_view_instance(request, instance):
    """Check if the current user can view a specific instance
    
    Users can view instances if:
    1. They have admin access, OR
    2. They created the instance
    
    Args:
        request: Flask request object
        instance: Instance dictionary with metadata
        
    Returns:
        bool: True if user can view the instance
    """
    # Admins and local users can see all instances
    if is_admin_user(request):
        return True
    
    # Get current user identifier
    current_user = get_user_identifier(request)
    
    # Unauthenticated users cannot view instances
    if current_user is None:
        return False
    
    # Check if this user created the instance
    created_by = instance.get('created_by', '')
    
    return current_user == created_by

def can_create_instance(request, instances):
    """Check if the current user can create a new instance
    
    Users can create instances if:
    1. They have admin access (always allowed), OR
    2. MAX_INSTANCES is 0/unset (unlimited for all users), OR
    3. They have fewer instances than MAX_INSTANCES
    
    Args:
        request: Flask request object
        instances: Dictionary of all instances
        
    Returns:
        tuple: (bool: can_create, int: current_count, int: max_allowed)
    """
    # Admins can always create instances regardless of MAX_INSTANCES
    if is_admin_user(request):
        return True, 0, 0
    
    # Get user identifier - required for non-admin users
    user_id = get_user_identifier(request)
    if user_id is None:
        # Unauthenticated users cannot create instances
        return False, 0, 0
    
    # If MAX_INSTANCES is 0 or not set, unlimited instances for all users
    if MAX_INSTANCES == 0:
        return True, 0, 0
    
    # Count instances created by this user
    user_instance_count = sum(1 for inst in instances.values() if inst.get('created_by', '') == user_id)
    
    # Check if user has reached the limit
    can_create = user_instance_count < MAX_INSTANCES
    return can_create, user_instance_count, MAX_INSTANCES

def _resolve_ha_user(ha_user_id, ha_user_name, ha_display_name):
    """Map a Home Assistant user to an app user account.

    Looks up an existing app account linked to *ha_user_id*.  If none is
    found a new account is created automatically.  The HA display-name is
    used to derive a human-friendly app username.

    Returns:
        str: The app username that corresponds to the HA user.
    """
    users = load_users()

    # 1. Check if an existing app user is already linked to this HA user ID
    for uname, u in users.items():
        if u.get('ha_user_id') == ha_user_id:
            return uname

    # 2. No mapping yet – create a new app account
    base_name = ha_display_name or ha_user_name or (
        f'ha_user_{ha_user_id[:8]}' if ha_user_id else 'ha_user'
    )
    # Sanitise to characters allowed by the registration endpoint
    sanitized = re.sub(r'[^a-zA-Z0-9_-]', '_', base_name).strip('_')
    if len(sanitized) < 2:
        sanitized = f'ha_{sanitized}' if sanitized else (
            f'ha_user_{ha_user_id[:8]}' if ha_user_id else 'ha_user'
        )

    # Avoid clashes with existing usernames
    username = sanitized
    counter = 1
    while username in users:
        username = f'{sanitized}_{counter}'
        counter += 1

    users[username] = {
        'password_hash': hash_password(secrets.token_urlsafe(32)),
        'role': 'user',
        'ha_user_id': ha_user_id,
        'ha_user_name': ha_user_name,
        'ha_display_name': ha_display_name,
        'created_at': datetime.now().isoformat(),
        'created_via': 'ingress_auto',
    }
    save_users(users)
    logger.info(
        'Created app user "%s" for HA user %s (id=%s)',
        username, ha_display_name or ha_user_name, ha_user_id,
    )
    return username


@app.before_request
def _ingress_auto_auth():
    """Auto-authenticate users coming through Home Assistant Ingress.

    When the add-on is accessed via Ingress the HA Supervisor has already
    authenticated the user.  We trust the ``X-Ingress-Path`` header
    **only** when the ``SUPERVISOR_TOKEN`` environment variable is present,
    which proves we are running inside the HA Supervisor environment where
    the ingress proxy is the sole entry-point.  The add-on port is not
    exposed by default (``5000/tcp: null``), so external clients cannot
    reach the application to spoof these headers.

    If the Supervisor sends ``X-Remote-User-Id`` / ``X-Remote-User-Name``
    headers (available since Home Assistant 2024.x) the add-on maps the
    HA user to a dedicated app account so that each HA user gets their own
    session.  When these headers are absent (older HA versions) the
    previous behaviour of logging in as the first admin account is
    preserved as a fallback.
    """
    # Only apply when running inside the HA Supervisor environment
    if not os.environ.get('SUPERVISOR_TOKEN'):
        return

    # Only apply when accessed via HA Ingress
    if not request.headers.get('X-Ingress-Path'):
        return

    # --- Per-user identity (newer HA versions) ---
    ha_user_id = request.headers.get('X-Remote-User-Id')
    ha_user_name = request.headers.get('X-Remote-User-Name')
    ha_display_name = request.headers.get('X-Remote-User-Display-Name')

    if ha_user_id:
        app_username = _resolve_ha_user(ha_user_id, ha_user_name, ha_display_name)
        if session.get('username') != app_username:
            session['username'] = app_username
            logger.info(
                'Ingress auto-auth: session set to HA user %s (ha_id=%s)',
                app_username, ha_user_id,
            )
        return

    # --- Fallback: no user-identity headers (older HA) ---
    if session.get('username'):
        return

    users = load_users()
    admin_username = next(
        (uname for uname, u in users.items() if u.get('role') == 'admin'),
        None,
    )
    if admin_username:
        session['username'] = admin_username
        logger.info('Ingress auto-auth: session set to admin user %s (no user headers)', admin_username)


@app.route('/')
def index():
    """Main page with instance management UI"""
    instances = load_instances()
    # Update status for each instance by checking actual container state
    update_instances_status(instances)
    
    # Filter instances based on user access
    is_admin = is_admin_user(request)
    user_id = get_user_identifier(request)
    
    if not is_admin and user_id is not None:
        # Non-admin authenticated users only see their own instances
        instances = {
            name: inst for name, inst in instances.items()
            if inst.get('created_by', '') == user_id
        }
    elif not is_admin and user_id is None:
        # Unauthenticated non-admin users see no instances
        instances = {}
    else:
        # For admins, add onboarding status to each instance
        for server_name, instance in instances.items():
            volume_name = instance.get('container_name', f'ha-edu-{server_name.lower().replace(" ", "-")}')
            instance['onboarded'] = check_instance_onboarding_complete_cached(volume_name)
    
    # Check if user can create more instances
    can_create, user_count, max_allowed = can_create_instance(request, load_instances())
    user_has_instance = not can_create
    
    # Generate tooltip message for create button
    create_button_tooltip = ""
    if user_has_instance:
        if user_id is None:
            create_button_tooltip = "Du måste vara inloggad för att skapa instanser."
        elif max_allowed > 0:
            create_button_tooltip = f"Du har nått gränsen på {max_allowed} instans(er). Ta bort en befintlig instans för att skapa en ny."
        else:
            create_button_tooltip = "Du kan bara ha en instans åt gången. Ta bort din befintliga instans för att skapa en ny."
    
    # Pass admin status, user_has_instance, and max instances info to template
    # X-Ingress-Path is set by Home Assistant when the add-on is accessed through ingress
    ingress_path = request.headers.get('X-Ingress-Path', '')
    ingress_mode = bool(os.environ.get('SUPERVISOR_TOKEN') and ingress_path)
    return render_template('index.html', 
                         instances=instances, 
                         is_admin=is_admin,
                         logged_in=user_id is not None,
                         username=user_id or '',
                         must_change_password=False,
                         user_has_instance=user_has_instance,
                         max_instances=max_allowed,
                         user_instance_count=user_count,
                         create_button_tooltip=create_button_tooltip,
                         ingress_path=ingress_path,
                         ingress_mode=ingress_mode)

@app.route('/api/instances', methods=['GET'])
def get_instances():
    """API endpoint to get all instances with real-time status
    
    Returns only instances the user has permission to see
    """
    instances = load_instances()
    # Update status for each instance by checking actual container state
    update_instances_status(instances)
    
    # Filter instances based on user access
    is_admin = is_admin_user(request)
    if not is_admin:
        # Non-admin users only see their own instances
        user_id = get_user_identifier(request)
        if user_id is None:
            # Unauthenticated users see no instances
            instances = {}
        else:
            instances = {
                name: inst for name, inst in instances.items()
                if inst.get('created_by', '') == user_id
            }
    else:
        # For admins, add onboarding status to each instance
        for server_name, instance in instances.items():
            volume_name = instance.get('container_name', f'ha-edu-{server_name.lower().replace(" ", "-")}')
            instance['onboarded'] = check_instance_onboarding_complete_cached(volume_name)
    
    return jsonify(instances)

@app.route('/api/instances', methods=['POST'])
def create_instance():
    """API endpoint to create a new Home Assistant instance"""
    # Check if instance creation is enabled
    settings = load_settings()
    if not settings.get('instance_creation_enabled', True):
        return jsonify({'error': 'Instance creation is currently disabled'}), 403
    
    # Check if user can create more instances (server-side validation)
    instances = load_instances()
    can_create, user_count, max_allowed = can_create_instance(request, instances)
    
    if not can_create:
        # Get user identifier to determine error message
        user_id = get_user_identifier(request)
        if user_id is None:
            return jsonify({
                'error': 'You must be logged in to create instances.'
            }), 403
        return jsonify({
            'error': f'You have reached the maximum limit of {max_allowed} instance(s). Please delete an existing instance before creating a new one.'
        }), 403
    
    data = request.json
    server_name = data.get('server_name', '').strip()
    instance_password = data.get('instance_password', '').strip()
    
    if not server_name:
        return jsonify({'error': 'Server name is required'}), 400
    
    # Use lock to prevent race conditions when multiple students create instances simultaneously
    # This ensures port allocation and instance registration are atomic operations
    with _port_allocation_lock:
        instances = load_instances()
        
        # Re-check limit inside lock to prevent race condition
        can_create, user_count, max_allowed = can_create_instance(request, instances)
        if not can_create:
            # Get user identifier to determine error message
            user_id = get_user_identifier(request)
            if user_id is None:
                return jsonify({
                    'error': 'You must be logged in to create instances.'
                }), 403
            return jsonify({
                'error': f'You have reached the maximum limit of {max_allowed} instance(s). Please delete an existing instance before creating a new one.'
            }), 403
        
        # Check if server name already exists
        if server_name in instances:
            return jsonify({'error': 'Server name already exists'}), 400
        
        # Get available port (no limit check - dynamic port assignment)
        port = get_available_port()
        
        # Get user identifier
        created_by = get_user_identifier(request)
        
        # Reserve the port immediately by adding a placeholder entry
        # This prevents other concurrent requests from selecting the same port
        container_name = f'ha-edu-{server_name.lower().replace(" ", "-")}'
        instances[server_name] = {
            'container_id': 'pending',
            'container_name': container_name,
            'port': port,
            'created_at': datetime.now().isoformat(),
            'created_by': created_by,
            'status': 'creating'
        }
        save_instances(instances)
    
    # Now create the actual container outside the lock to avoid blocking other requests
    try:
        volume_name = container_name
        
        # Clean up any leftover container with the same name
        # This can happen if a previous instance with the same name failed to delete properly
        try:
            existing_container = client.containers.get(container_name)
            logger.warning(f'Found existing container {container_name}, removing it')
            try:
                existing_container.stop(timeout=5)
            except:
                pass  # Container might already be stopped
            existing_container.remove(force=True)
        except docker.errors.NotFound:
            pass  # No existing container, which is expected
        
        # Clean up any leftover volume with the same name
        # This can happen if a previous instance deletion failed to remove the volume
        try:
            existing_volume = client.volumes.get(volume_name)
            logger.warning(f'Found existing volume {volume_name}, removing it')
            existing_volume.remove(force=True)
        except docker.errors.NotFound:
            pass  # No existing volume, which is expected
        
        # Copy master configuration to the volume before starting the container
        copy_master_config_to_volume(volume_name)
        
        # Pull the latest HA image and re-tag for student use
        student_image = pull_and_retag_image()
        
        # Network configuration: Create container with bridge network for internet access
        # but isolated from host LAN.
        container = client.containers.run(
            student_image,
            name=container_name,
            detach=True,
            ports={'8123/tcp': port},
            environment={
                'TZ': 'UTC'
            },
            volumes={
                volume_name: {'bind': '/config', 'mode': 'rw'}
            },
            restart_policy={'Name': 'unless-stopped'},
            # Use default bridge network for isolation from host LAN
            network_mode='bridge'
        )
        
        # Update instance info with actual container details
        instance_info = {
            'container_id': container.id,
            'container_name': container_name,
            'port': port,
            'created_at': datetime.now().isoformat(),
            'created_by': created_by,
            'status': 'running'
        }
        
        # Hash and store instance password if provided
        if instance_password:
            instance_info['instance_password_hash'] = hash_password(instance_password)
        
        # Update the instance with final info (use lock to prevent race conditions)
        with _port_allocation_lock:
            instances = load_instances()
            instances[server_name] = instance_info
            save_instances(instances)
        
        # Log instance creation
        user_id, user_type = get_user_info_for_logging(request)
        interaction_logger.log_instance_creation(
            server_name=server_name,
            user_id=user_id,
            user_type=user_type,
            port=port,
            container_id=container.id
        )
        
        return jsonify({
            'message': 'Instance created successfully',
            'server_name': server_name,
            'port': port,
            'url': f'/proxy/{port}/'
        }), 201
        
    except Exception as e:
        logger.error(f'Failed to create instance: {str(e)}', exc_info=True)
        # Clean up the placeholder entry on failure (use lock to prevent race conditions)
        try:
            with _port_allocation_lock:
                instances = load_instances()
                if server_name in instances and instances[server_name].get('container_id') == 'pending':
                    del instances[server_name]
                    save_instances(instances)
        except Exception as cleanup_error:
            logger.error(f'Failed to clean up placeholder entry: {str(cleanup_error)}')
        return jsonify({'error': 'Failed to create instance. Please try again or contact support.'}), 500

@app.route('/api/instances/<server_name>', methods=['DELETE'])
def delete_instance(server_name):
    """API endpoint to delete an instance (admin bypasses password; others need instance password)"""
    data = request.json or {}
    password = data.get('password', '')
    
    instances = load_instances()
    
    if server_name not in instances:
        return jsonify({'error': 'Instance not found'}), 404
    
    instance = instances[server_name]
    
    # Check if instance is locked
    if instance.get('locked', False):
        logger.warning(f'Failed deletion attempt for instance {server_name} - instance is locked')
        return jsonify({'error': 'Cannot delete a locked instance. Please unlock it first.'}), 403
    
    # Admin users bypass password check
    if not is_admin_user(request):
        if not password:
            return jsonify({'error': 'Password is required'}), 400
        # Validate password (instance password only)
        if not validate_instance_password(password, instance):
            logger.warning(f'Failed deletion attempt for instance {server_name} - invalid password')
            return jsonify({'error': 'Invalid password'}), 401
    
    logger.info(f'Instance {server_name} deletion authorized')
    
    try:
        # Stop and remove container
        try:
            container = client.containers.get(instance['container_id'])
            container.stop()
            container.remove()
        except docker.errors.NotFound:
            pass  # Container already removed
        
        # Remove the volume to free up storage
        volume_name = instance['container_name']
        try:
            volume = client.volumes.get(volume_name)
            volume.remove()
            logger.info(f'Successfully removed volume {volume_name}')
        except docker.errors.NotFound:
            pass  # Volume doesn't exist or already removed
        except Exception as e:
            logger.warning(f'Failed to remove volume {volume_name}: {str(e)}')
        
        # Log instance deletion
        user_id, user_type = get_user_info_for_logging(request)
        interaction_logger.log_instance_deletion(
            server_name=server_name,
            user_id=user_id,
            user_type=user_type,
            container_id=instance['container_id']
        )
        
        # Remove from instances
        del instances[server_name]
        save_instances(instances)
        
        return jsonify({'message': 'Instance deleted successfully'}), 200
        
    except Exception as e:
        logger.error(f'Failed to delete instance: {str(e)}', exc_info=True)
        return jsonify({'error': 'Failed to delete instance. Please try again or contact support.'}), 500

@app.route('/api/instances/<server_name>/toggle-lock', methods=['POST'])
def toggle_instance_lock(server_name):
    """API endpoint to toggle instance lock state"""
    instances = load_instances()
    
    if server_name not in instances:
        return jsonify({'error': 'Instance not found'}), 404
    
    instance = instances[server_name]
    
    # Toggle the lock state (default to False if not set)
    current_lock_state = instance.get('locked', False)
    instance['locked'] = not current_lock_state
    
    # Save updated instances
    instances[server_name] = instance
    save_instances(instances)
    
    logger.info(f'Instance {server_name} lock state changed to: {instance["locked"]}')
    
    return jsonify({
        'locked': instance['locked'],
        'message': f'Instance {"locked" if instance["locked"] else "unlocked"} successfully'
    }), 200

@app.route('/api/instances/<server_name>/status', methods=['GET'])
def get_instance_status(server_name):
    """API endpoint to get instance status"""
    instances = load_instances()
    
    if server_name not in instances:
        return jsonify({'error': 'Instance not found'}), 404
    
    instance = instances[server_name]
    
    try:
        container = client.containers.get(instance['container_id'])
        status = container.status
        
        # Update status in storage
        instance['status'] = status
        instances[server_name] = instance
        save_instances(instances)
        
        return jsonify({'status': status}), 200
        
    except docker.errors.NotFound:
        instance['status'] = 'removed'
        instances[server_name] = instance
        save_instances(instances)
        return jsonify({'status': 'removed'}), 200

@app.route('/api/instances/<server_name>/reset', methods=['POST'])
def reset_instance(server_name):
    """API endpoint to reset an instance to default HA image (admin bypasses password; others need instance password)"""
    data = request.json or {}
    password = data.get('password', '')
    
    instances = load_instances()
    
    if server_name not in instances:
        return jsonify({'error': 'Instance not found'}), 404
    
    instance = instances[server_name]
    
    # Admin users bypass password check
    if not is_admin_user(request):
        if not password:
            return jsonify({'error': 'Password is required'}), 400
        # Validate password (instance password only)
        if not validate_instance_password(password, instance):
            logger.warning(f'Failed reset attempt for instance {server_name} - invalid password')
            return jsonify({'error': 'Invalid password'}), 401
    
    logger.info(f'Instance {server_name} reset authorized')
    
    try:
        container_name = instance['container_name']
        port = instance['port']
        old_container_id = instance['container_id']
        
        # Stop and remove existing container
        try:
            container = client.containers.get(old_container_id)
            container.stop()
            container.remove()
        except docker.errors.NotFound:
            pass  # Container already removed
        
        # Remove the volume to completely reset the instance
        volume_name = container_name
        try:
            volume = client.volumes.get(volume_name)
            volume.remove()
        except docker.errors.NotFound:
            pass  # Volume doesn't exist or already removed
        
        # Copy master configuration to the volume before starting the container
        copy_master_config_to_volume(volume_name)
        
        # Pull the latest HA image and re-tag for student use
        student_image = pull_and_retag_image()
        
        # Create a new container with the same configuration
        # Network configuration: Use bridge network for isolation from host LAN
        new_container = client.containers.run(
            student_image,
            name=container_name,
            detach=True,
            ports={'8123/tcp': port},
            environment={
                'TZ': 'UTC'
            },
            volumes={
                volume_name: {'bind': '/config', 'mode': 'rw'}
            },
            restart_policy={'Name': 'unless-stopped'},
            network_mode='bridge'
        )
        
        # Update instance info with new container ID
        instance['container_id'] = new_container.id
        instance['status'] = 'running'
        instance['reset_at'] = datetime.now().isoformat()
        instances[server_name] = instance
        save_instances(instances)
        
        # Log instance reset
        user_id, user_type = get_user_info_for_logging(request)
        interaction_logger.log_instance_reset(
            server_name=server_name,
            user_id=user_id,
            user_type=user_type,
            old_container_id=old_container_id,
            new_container_id=new_container.id
        )
        
        return jsonify({
            'message': 'Instance reset successfully',
            'server_name': server_name
        }), 200
        
    except Exception as e:
        logger.error(f'Failed to reset instance: {str(e)}', exc_info=True)
        return jsonify({'error': 'Failed to reset instance. Please try again or contact support.'}), 500

@app.route('/api/instances/<server_name>/restart', methods=['POST'])
def restart_instance(server_name):
    """API endpoint to restart an instance (admin bypasses password; others need instance password)"""
    data = request.json or {}
    password = data.get('password', '')
    
    instances = load_instances()
    
    if server_name not in instances:
        return jsonify({'error': 'Instance not found'}), 404
    
    instance = instances[server_name]
    
    # Admin users bypass password check
    if is_admin_user(request):
        password_valid = True
        logger.info(f'Instance {server_name} restart authorized for admin user')
    else:
        password_valid = False
        if not password:
            return jsonify({'error': 'Password is required'}), 400
        # Check instance password if set
        if instance.get('instance_password_hash'):
            if verify_password(password, instance['instance_password_hash']):
                password_valid = True
                logger.info(f'Instance {server_name} restart authorized with instance password')
    
    if not password_valid:
        logger.warning(f'Failed restart attempt for instance {server_name} - invalid password')
        return jsonify({'error': 'Invalid password'}), 401
    
    try:
        # Restart the container
        success, message = restart_instance_container(instance['container_id'])
        
        if not success:
            return jsonify({'error': message}), 500
        
        # Update status
        instance['status'] = 'restarting'
        instance['last_restarted_at'] = datetime.now().isoformat()
        instances[server_name] = instance
        save_instances(instances)
        
        # Log instance restart
        user_id, user_type = get_user_info_for_logging(request)
        interaction_logger.log_instance_restart(
            server_name=server_name,
            user_id=user_id,
            user_type=user_type,
            container_id=instance['container_id']
        )
        
        return jsonify({
            'message': 'Instance restarted successfully',
            'server_name': server_name
        }), 200
        
    except Exception as e:
        logger.error(f'Failed to restart instance: {str(e)}', exc_info=True)
        return jsonify({'error': 'Failed to restart instance. Please try again or contact support.'}), 500

# ---------------------------------------------------------------------------
# Authentication routes
# ---------------------------------------------------------------------------

@app.route('/api/auth/login', methods=['POST'])
def auth_login():
    """Log in with username and password"""
    data = request.get_json(silent=True) or {}
    username = data.get('username', '').strip()
    password = data.get('password', '')
    
    if not username or not password:
        return jsonify({'error': 'Username and password are required'}), 400
    
    users = load_users()
    user = users.get(username)
    
    if not user or not verify_password(password, user['password_hash']):
        return jsonify({'error': 'Invalid username or password'}), 401
    
    session['username'] = username
    return jsonify({
        'message': 'Login successful',
        'username': username,
        'role': user.get('role', 'user'),
    }), 200

@app.route('/api/auth/register', methods=['POST'])
def auth_register():
    """Create a new user account"""
    data = request.get_json(silent=True) or {}
    username = data.get('username', '').strip()
    password = data.get('password', '')
    
    if not username or not password:
        return jsonify({'error': 'Username and password are required'}), 400
    
    if len(username) < 2:
        return jsonify({'error': 'Username must be at least 2 characters'}), 400
    
    if len(password) < 4:
        return jsonify({'error': 'Password must be at least 4 characters'}), 400
    
    if not re.match(r'^[a-zA-Z0-9_\-]+$', username):
        return jsonify({'error': 'Username may only contain letters, numbers, underscores, and hyphens'}), 400
    
    users = load_users()
    
    if username in users:
        return jsonify({'error': 'Username already taken'}), 409
    
    users[username] = {
        'password_hash': hash_password(password),
        'role': 'user',
        'created_at': datetime.now().isoformat(),
    }
    save_users(users)
    
    session['username'] = username
    logger.info(f'New user account created: {username}')
    return jsonify({
        'message': 'Account created',
        'username': username,
        'role': 'user',
    }), 201

@app.route('/api/auth/logout', methods=['POST'])
def auth_logout():
    """Log out the current user"""
    session.pop('username', None)
    return jsonify({'message': 'Logged out'}), 200

@app.route('/api/auth/status', methods=['GET'])
def auth_status():
    """Return current authentication status"""
    username = session.get('username')
    if not username:
        return jsonify({'logged_in': False}), 200
    users = load_users()
    user = users.get(username, {})
    return jsonify({
        'logged_in': True,
        'username': username,
        'role': user.get('role', 'user'),
    }), 200

@app.route('/api/auth/change-password', methods=['POST'])
def auth_change_password():
    """Change credentials for the logged-in user (or set new admin username on first setup)"""
    username = session.get('username')
    if not username:
        return jsonify({'error': 'Not logged in'}), 401
    
    data = request.get_json(silent=True) or {}
    new_username = data.get('new_username', '').strip()
    new_password = data.get('new_password', '')
    
    if not new_password:
        return jsonify({'error': 'New password is required'}), 400
    
    if len(new_password) < 4:
        return jsonify({'error': 'Password must be at least 4 characters'}), 400
    
    users = load_users()
    user = users.get(username)
    if not user:
        return jsonify({'error': 'User not found'}), 404
    
    # If a new username is provided and it differs, rename the account
    if new_username and new_username != username:
        if not re.match(r'^[a-zA-Z0-9_\-]+$', new_username):
            return jsonify({'error': 'Username may only contain letters, numbers, underscores, and hyphens'}), 400
        if new_username in users:
            return jsonify({'error': 'Username already taken'}), 409
        # Move the user entry to the new key
        del users[username]
        username = new_username
    
    user['password_hash'] = hash_password(new_password)
    users[username] = user
    save_users(users)
    
    session['username'] = username
    logger.info(f'User credentials updated: {username}')
    return jsonify({
        'message': 'Credentials updated',
        'username': username,
    }), 200

@app.route('/api/admin/check', methods=['GET'])
def check_admin():
    """API endpoint to check if admin features are available"""
    return jsonify({'admin_enabled': True}), 200

@app.route('/api/admin/check-access', methods=['GET'])
def check_admin_access():
    """API endpoint to check if the current user has admin access
    
    Returns:
        JSON response with has_admin_access boolean
    """
    has_access = is_admin_user(request)
    logged_in = session.get('username') is not None
    return jsonify({
        'has_admin_access': has_access,
        'logged_in': logged_in,
    }), 200

@app.route('/api/instances/delete-all', methods=['POST'])
def delete_all_instances():
    """API endpoint to delete all instances (requires admin session)"""
    if not is_admin_user(request):
        return jsonify({'error': 'Admin access required'}), 403
    
    instances = load_instances()
    
    if not instances:
        return jsonify({'message': 'No instances to delete'}), 200
    
    deleted_count = 0
    failed_count = 0
    locked_count = 0
    
    try:
        # Delete all unlocked instances
        for server_name, instance in list(instances.items()):
            # Skip locked instances
            if instance.get('locked', False):
                logger.info(f'Skipping locked instance: {server_name}')
                locked_count += 1
                continue
                
            try:
                # Stop and remove container
                try:
                    container = client.containers.get(instance['container_id'])
                    container.stop()
                    container.remove()
                except docker.errors.NotFound:
                    pass  # Container already removed
                
                # Remove the volume to free up storage
                volume_name = instance['container_name']
                try:
                    volume = client.volumes.get(volume_name)
                    volume.remove()
                    logger.info(f'Successfully removed volume {volume_name}')
                except docker.errors.NotFound:
                    pass  # Volume doesn't exist or already removed
                except Exception as e:
                    logger.warning(f'Failed to remove volume {volume_name}: {str(e)}')
                
                # Remove from instances dict
                del instances[server_name]
                deleted_count += 1
            except Exception as e:
                logger.error(f'Failed to delete instance {server_name}: {str(e)}')
                failed_count += 1
        
        # Save updated instances (locked ones remain)
        save_instances(instances)
        
        # Log admin operation
        user_id, user_type = get_user_info_for_logging(request)
        interaction_logger.log_admin_operation(
            operation='delete_all_instances',
            user_id=user_id,
            details={'deleted_count': deleted_count, 'failed_count': failed_count, 'locked_count': locked_count}
        )
        
        message = f'Successfully deleted {deleted_count} instance(s)'
        if locked_count > 0:
            message += f', {locked_count} locked instance(s) were preserved'
        
        return jsonify({
            'message': message,
            'deleted_count': deleted_count,
            'failed_count': failed_count,
            'locked_count': locked_count
        }), 200
        
    except Exception as e:
        logger.error(f'Failed to delete all instances: {str(e)}', exc_info=True)
        return jsonify({'error': 'Failed to delete all instances. Please try again or contact support.'}), 500

@app.route('/api/instances/start-all', methods=['POST'])
def start_all_instances():
    """API endpoint to start all instances (requires admin session)"""
    if not is_admin_user(request):
        return jsonify({'error': 'Admin access required'}), 403
    
    instances = load_instances()
    
    if not instances:
        return jsonify({'message': 'No instances to start'}), 200
    
    started_count = 0
    failed_count = 0
    already_running_count = 0
    
    try:
        for server_name, instance in instances.items():
            try:
                container = client.containers.get(instance['container_id'])
                if container.status == 'running':
                    already_running_count += 1
                    continue
                container.start()
                instance['status'] = 'running'
                started_count += 1
                logger.info(f'Started instance: {server_name}')
            except docker.errors.NotFound:
                logger.warning(f'Container not found for instance {server_name}')
                instance['status'] = 'removed'
                failed_count += 1
            except docker.errors.APIError as e:
                logger.error(f'Failed to start instance {server_name}: {str(e)}')
                failed_count += 1
            except Exception as e:
                logger.error(f'Unexpected error starting instance {server_name}: {str(e)}')
                failed_count += 1
        
        # Save updated instances
        save_instances(instances)
        
        # Log admin operation
        user_id, user_type = get_user_info_for_logging(request)
        interaction_logger.log_admin_operation(
            operation='start_all_instances',
            user_id=user_id,
            details={'started_count': started_count, 'failed_count': failed_count, 'already_running_count': already_running_count}
        )
        
        message = f'Successfully started {started_count} instance(s)'
        if already_running_count > 0:
            message += f', {already_running_count} instance(s) were already running'
        
        return jsonify({
            'message': message,
            'started_count': started_count,
            'failed_count': failed_count,
            'already_running_count': already_running_count
        }), 200
        
    except Exception as e:
        logger.error(f'Failed to start all instances: {str(e)}', exc_info=True)
        return jsonify({'error': 'Failed to start all instances. Please try again or contact support.'}), 500

@app.route('/api/instances/stop-all', methods=['POST'])
def stop_all_instances():
    """API endpoint to stop all instances (requires admin session)"""
    if not is_admin_user(request):
        return jsonify({'error': 'Admin access required'}), 403
    
    instances = load_instances()
    
    if not instances:
        return jsonify({'message': 'No instances to stop'}), 200
    
    stopped_count = 0
    failed_count = 0
    already_stopped_count = 0
    
    try:
        for server_name, instance in instances.items():
            try:
                container = client.containers.get(instance['container_id'])
                if container.status != 'running':
                    already_stopped_count += 1
                    continue
                container.stop(timeout=10)
                instance['status'] = 'exited'
                stopped_count += 1
                logger.info(f'Stopped instance: {server_name}')
            except docker.errors.NotFound:
                logger.warning(f'Container not found for instance {server_name}')
                instance['status'] = 'removed'
                failed_count += 1
            except docker.errors.APIError as e:
                logger.error(f'Failed to stop instance {server_name}: {str(e)}')
                failed_count += 1
            except Exception as e:
                logger.error(f'Unexpected error stopping instance {server_name}: {str(e)}')
                failed_count += 1
        
        # Save updated instances
        save_instances(instances)
        
        # Log admin operation
        user_id, user_type = get_user_info_for_logging(request)
        interaction_logger.log_admin_operation(
            operation='stop_all_instances',
            user_id=user_id,
            details={'stopped_count': stopped_count, 'failed_count': failed_count, 'already_stopped_count': already_stopped_count}
        )
        
        message = f'Successfully stopped {stopped_count} instance(s)'
        if already_stopped_count > 0:
            message += f', {already_stopped_count} instance(s) were already stopped'
        
        return jsonify({
            'message': message,
            'stopped_count': stopped_count,
            'failed_count': failed_count,
            'already_stopped_count': already_stopped_count
        }), 200
        
    except Exception as e:
        logger.error(f'Failed to stop all instances: {str(e)}', exc_info=True)
        return jsonify({'error': 'Failed to stop all instances. Please try again or contact support.'}), 500

@app.route('/api/settings/instance-creation', methods=['GET'])
def get_instance_creation_status():
    """API endpoint to get instance creation status"""
    settings = load_settings()
    return jsonify({
        'instance_creation_enabled': settings.get('instance_creation_enabled', True)
    }), 200

@app.route('/api/settings/instance-creation', methods=['POST'])
def set_instance_creation_status():
    """API endpoint to set instance creation status (requires admin session)"""
    if not is_admin_user(request):
        return jsonify({'error': 'Admin access required'}), 403
    
    data = request.json or {}
    enabled = data.get('enabled', True)
    
    settings = load_settings()
    settings['instance_creation_enabled'] = enabled
    save_settings(settings)
    
    return jsonify({
        'message': 'Instance creation status updated successfully',
        'instance_creation_enabled': enabled
    }), 200

@app.route('/api/settings/teacher-access', methods=['GET'])
def check_teacher_access():
    """API endpoint to check if teacher access feature is enabled"""
    settings = load_settings()
    teacher_username = settings.get('teacher_username', '')
    teacher_password = settings.get('teacher_password', '')
    enabled = bool(teacher_username and teacher_password)
    return jsonify({
        'teacher_access_enabled': enabled,
        'teacher_username': teacher_username if enabled else None
    }), 200

@app.route('/api/settings/teacher-access', methods=['POST'])
def set_teacher_access():
    """API endpoint to configure teacher access credentials (requires admin session)"""
    if not is_admin_user(request):
        return jsonify({'error': 'Admin access required'}), 403
    
    data = request.json or {}
    teacher_username = data.get('teacher_username', '').strip()
    teacher_password = data.get('teacher_password', '').strip()
    
    if not teacher_username or not teacher_password:
        return jsonify({'error': 'Both teacher username and password are required'}), 400
    
    settings = load_settings()
    settings['teacher_username'] = teacher_username
    settings['teacher_password'] = teacher_password
    save_settings(settings)
    
    return jsonify({
        'message': 'Teacher access credentials saved',
        'teacher_username': teacher_username
    }), 200

@app.route('/api/instances/<server_name>/add-teacher-access', methods=['POST'])
def add_teacher_access(server_name):
    """API endpoint to add teacher access to an instance (requires admin session)"""
    if not is_admin_user(request):
        return jsonify({'error': 'Admin access required'}), 403
    
    settings = load_settings()
    teacher_username = settings.get('teacher_username', '')
    teacher_password = settings.get('teacher_password', '')
    
    if not teacher_username or not teacher_password:
        return jsonify({'error': 'Teacher access not configured. Set teacher credentials in the admin settings.'}), 403
    
    instances = load_instances()
    
    if server_name not in instances:
        return jsonify({'error': 'Instance not found'}), 404
    
    instance = instances[server_name]
    
    # Determine if we should reset existing account
    reset_if_exists = instance.get('teacher_access_added', False)
    
    try:
        # Check if instance has completed onboarding
        volume_name = instance['container_name']
        
        if not check_instance_onboarding_complete(volume_name):
            return jsonify({
                'error': 'Instance has not completed onboarding yet. Students must complete the onboarding process before teacher access can be added.'
            }), 400
        
        # Create teacher account (or reset password if already exists)
        success, message = create_teacher_account(volume_name, teacher_username, teacher_password, reset_if_exists=reset_if_exists)
        
        if not success:
            return jsonify({'error': message}), 400
        
        # Update instance metadata
        instance['teacher_access_added'] = True
        instance['teacher_access_added_at'] = datetime.now().isoformat()
        instances[server_name] = instance
        save_instances(instances)
        
        # Log teacher access addition
        user_id, user_type = get_user_info_for_logging(request)
        interaction_logger.log_teacher_access_added(
            server_name=server_name,
            user_id=user_id,
            teacher_username=teacher_username
        )
        
        # Log for audit trail
        logger.info(f'Teacher access added to instance {server_name} by admin. Teacher username: {teacher_username}')
        
        # Automatically restart the instance to apply the teacher account changes
        restart_success, restart_message = restart_instance_container(instance['container_id'])
        
        if not restart_success:
            logger.warning(f'Teacher access added but failed to restart instance {server_name}: {restart_message}')
            return jsonify({
                'message': 'Teacher access added successfully, but instance restart failed. Please restart manually.',
                'teacher_username': teacher_username,
                'restart_warning': restart_message
            }), 200
        
        logger.info(f'Instance {server_name} automatically restarted after teacher access creation')
        
        return jsonify({
            'message': 'Teacher access added successfully and instance restarted',
            'teacher_username': teacher_username
        }), 200
        
    except Exception as e:
        logger.error(f'Failed to add teacher access to instance {server_name}: {str(e)}', exc_info=True)
        return jsonify({'error': 'Failed to add teacher access. Please try again or contact support.'}), 500

@app.route('/api/instances/add-teacher-access-all', methods=['POST'])
def add_teacher_access_all():
    """API endpoint to add teacher access to all instances (requires admin session)"""
    if not is_admin_user(request):
        return jsonify({'error': 'Admin access required'}), 403
    
    settings = load_settings()
    teacher_username = settings.get('teacher_username', '')
    teacher_password = settings.get('teacher_password', '')
    
    if not teacher_username or not teacher_password:
        return jsonify({'error': 'Teacher access not configured. Set teacher credentials in the admin settings.'}), 403
    
    instances = load_instances()
    
    if not instances:
        return jsonify({'error': 'No instances found'}), 404
    
    success_count = 0
    failed_count = 0
    skipped_count = 0
    results = []
    
    for server_name, instance in instances.items():
        try:
            # Check if instance has completed onboarding
            volume_name = instance['container_name']
            
            if not check_instance_onboarding_complete(volume_name):
                logger.info(f'Skipping instance {server_name} - onboarding not complete')
                skipped_count += 1
                results.append({
                    'server_name': server_name,
                    'status': 'skipped',
                    'message': 'Onboarding not complete'
                })
                continue
            
            # Create teacher account (or reset password if already exists)
            # Always use reset_if_exists=True for bulk operation to handle both creation and reset
            success, message = create_teacher_account(volume_name, teacher_username, teacher_password, reset_if_exists=True)
            
            if success:
                # Update instance metadata
                instance['teacher_access_added'] = True
                instance['teacher_access_added_at'] = datetime.now().isoformat()
                instances[server_name] = instance
                
                # Restart the instance to apply changes
                restart_success, restart_message = restart_instance_container(instance['container_id'])
                
                success_count += 1
                results.append({
                    'server_name': server_name,
                    'status': 'success',
                    'message': message,
                    'restarted': restart_success
                })
                
                logger.info(f'Teacher access added to instance {server_name}. Restart: {restart_success}')
            else:
                failed_count += 1
                results.append({
                    'server_name': server_name,
                    'status': 'failed',
                    'message': message
                })
                logger.error(f'Failed to add teacher access to instance {server_name}: {message}')
                
        except Exception as e:
            failed_count += 1
            results.append({
                'server_name': server_name,
                'status': 'error',
                'message': str(e)
            })
            logger.error(f'Exception while adding teacher access to instance {server_name}: {str(e)}', exc_info=True)
    
    # Save all instance updates
    save_instances(instances)
    
    # Log for audit trail
    logger.info(f'Bulk teacher access operation completed. Success: {success_count}, Failed: {failed_count}, Skipped: {skipped_count}')
    
    return jsonify({
        'message': f'Teacher access operation completed. {success_count} succeeded, {failed_count} failed, {skipped_count} skipped.',
        'teacher_username': teacher_username,
        'success_count': success_count,
        'failed_count': failed_count,
        'skipped_count': skipped_count,
        'results': results
    }), 200


def render_proxy_error(status_code, title, message, details=None, suggestions=None) -> tuple:
    """Render a user-friendly HTML error page for proxy errors
    
    Args:
        status_code: HTTP status code (404, 502, 504, etc.)
        title: Error title
        message: Error message
        details: Optional detailed explanation
        suggestions: Optional list of suggestions for the user
    
    Returns:
        tuple: (rendered HTML string, status code)
    """
    # Choose appropriate icon based on status code
    icons = {
        404: '🔍',
        400: '⚠️',
        502: '🔌',
        504: '⏱️',
        500: '⚙️'
    }
    icon = icons.get(status_code, '❌')
    
    return render_template('proxy_error.html',
                          icon=icon,
                          status_code=status_code,
                          title=title,
                          message=message,
                          details=details,
                          suggestions=suggestions), status_code

@app.route('/api/<path:path>', methods=['GET', 'POST', 'PUT', 'DELETE', 'PATCH', 'OPTIONS', 'HEAD'])
@app.route('/auth/<path:path>', methods=['GET', 'POST', 'PUT', 'DELETE', 'PATCH', 'OPTIONS', 'HEAD'])
@app.route('/frontend_latest/<path:path>', methods=['GET'])
@app.route('/static/<path:path>', methods=['GET'])
@app.route('/local/<path:path>', methods=['GET'])
@app.route('/hacsfiles/<path:path>', methods=['GET'])
@app.route('/lovelace/<path:path>', methods=['GET'])
@app.route('/service_worker.js', methods=['GET'])
@app.route('/manifest.json', methods=['GET'])
def proxy_fallback(path=''):
    """Fallback proxy for requests that didn't include /proxy/{port}/ prefix
    
    This happens when Home Assistant's JavaScript makes API calls using relative URLs
    or window.location.origin. We detect which instance by checking the Referer header,
    session cookies, or falling back to single-instance mode.
    """
    port = None
    
    # Strategy 1: Try to extract port from referer URL (e.g., http://domain/proxy/8123/)
    referer = request.headers.get('Referer', '')
    if not referer:
        referer = request.headers.get('Origin', '')
    
    if referer:
        port_match = re.search(r'/proxy/(\d+)', referer)
        if port_match:
            port = int(port_match.group(1))
            logger.debug(f'Extracted port {port} from referer: {referer}')
    
    # Strategy 2: Try to get port from session cookie (set when accessing /proxy/{port}/)
    if port is None and 'proxy_port' in session:
        port = session['proxy_port']
        logger.debug(f'Using port {port} from session cookie')
    
    # Strategy 3: If only one instance exists, use its port
    if port is None:
        instances = load_instances()
        if len(instances) == 1:
            port = list(instances.values())[0]['port']
            logger.info(f'Using single instance port {port} for fallback request to {request.path}')
        else:
            # Multiple instances and can't determine which one - log detailed info
            logger.warning(f'API request to {request.path} without valid referer or session. '
                         f'Headers: Referer={referer}, Origin={request.headers.get("Origin", "")}, '
                         f'Host={request.headers.get("Host", "")}. {len(instances)} instances available.')
            return jsonify({'error': 'Unable to determine target instance. Please access through /proxy/{port}/ URL.'}), 400
    
    # Verify the port belongs to a valid instance
    instances = load_instances()
    valid_port = False
    for inst in instances.values():
        if inst['port'] == port:
            valid_port = True
            break
    
    if not valid_port:
        logger.warning(f'Invalid port {port} requested for {request.path}')
        return jsonify({'error': 'Invalid instance port'}), 404
    
    # Build the full path from the request
    full_path = request.path.lstrip('/')
    
    # Forward to the proxy function
    logger.debug(f'Fallback proxy: Redirecting /{full_path} to port {port}')
    return proxy(port, full_path)

@app.route('/proxy/<int:port>/', defaults={'path': ''}, methods=['GET', 'POST', 'PUT', 'DELETE', 'PATCH', 'OPTIONS', 'HEAD'])
@app.route('/proxy/<int:port>/<path:path>', methods=['GET', 'POST', 'PUT', 'DELETE', 'PATCH', 'OPTIONS', 'HEAD'])
def proxy(port, path):
    """Proxy endpoint to forward requests to Home Assistant instances
    
    This allows users to access HA instances through the portal without
    exposing individual instance ports. All traffic goes through the 
    portal's single endpoint (port 5000).
    """
    # X-Ingress-Path is set by Home Assistant when the add-on is accessed through ingress
    ingress_path = request.headers.get('X-Ingress-Path', '')
    
    # Store the port in session for fallback requests
    session['proxy_port'] = port
    
    # Verify that the port belongs to a valid instance and log access
    instances = load_instances()
    valid_port = False
    server_name = None
    for name, inst in instances.items():
        if inst['port'] == port:
            valid_port = True
            server_name = name
            break
    
    if not valid_port:
        return render_proxy_error(
            404,
            'Instance Not Found',
            f'No Home Assistant instance is running on port {port}.',
            details='This instance may have been deleted or the port number is incorrect.',
            suggestions=[
                'Go back to the portal homepage to see available instances',
                'Check that you are using the correct access link',
                'If the instance was recently deleted, this is expected'
            ]
        )
    
    # Log instance access (only log on initial access, not every request)
    # We'll log on specific paths to avoid excessive logging of assets
    if path in ACCESS_LOG_PATHS:
        user_id, user_type = get_user_info_for_logging(request)
        interaction_logger.log_instance_access(
            server_name=server_name,
            user_id=user_id,
            user_type=user_type,
            access_type='proxy'
        )
    
    # Build the target URL
    target_url = f'http://{DOCKER_HOST_IP}:{port}/{path}'
    
    # Get query string if present
    if request.query_string:
        target_url += f'?{request.query_string.decode("utf-8")}'
    
    # Log the proxied request for debugging
    logger.info(f'Proxying {request.method} request to: {target_url}')
    
    # Check if this is a WebSocket upgrade request
    # Note: We forward the websocket handshake request to the backend even though
    # Flask cannot maintain a persistent websocket connection. This allows the backend
    # to respond with an appropriate error/fallback rather than us blocking it immediately.
    # Home Assistant's frontend can then handle the websocket failure gracefully (e.g., via polling).
    # According to RFC 6455 Section 4.2.1, a valid websocket upgrade requires both headers
    # The Connection header can contain multiple comma-separated values
    connection_tokens = [token.strip().lower() for token in request.headers.get('Connection', '').split(',') if token.strip()]
    is_websocket_upgrade = (request.headers.get('Upgrade', '').lower() == 'websocket' and
                           'upgrade' in connection_tokens)
    if is_websocket_upgrade:
        logger.info(f'WebSocket upgrade request detected for port {port}, forwarding to backend')
    
    try:
        # Forward the request to the HA instance
        # Copy headers but modify Host and other proxy-specific headers
        headers = {}
        skip_headers = ['host', 'keep-alive', 'accept-encoding',
                        'x-forwarded-for', 'x-forwarded-proto', 'x-forwarded-host',
                        'x-ingress-path']
        # For websocket upgrade requests, we need to forward Connection and Upgrade headers
        if not is_websocket_upgrade:
            skip_headers.append('connection')
        
        for key, value in request.headers.items():
            # Skip hop-by-hop headers and encoding headers that can cause issues
            if key.lower() not in skip_headers:
                headers[key] = value

        # Set the correct Host header for the backend
        headers['Host'] = f'{DOCKER_HOST_IP}:{port}'
        
        # Make the request to the backend
        if request.method == 'GET':
            resp = requests.get(target_url, headers=headers, stream=True, timeout=30)
        elif request.method == 'POST':
            resp = requests.post(target_url, headers=headers, data=request.get_data(), 
                               stream=True, timeout=30)
        elif request.method == 'PUT':
            resp = requests.put(target_url, headers=headers, data=request.get_data(), 
                              stream=True, timeout=30)
        elif request.method == 'DELETE':
            resp = requests.delete(target_url, headers=headers, stream=True, timeout=30)
        elif request.method == 'PATCH':
            resp = requests.patch(target_url, headers=headers, data=request.get_data(), 
                                stream=True, timeout=30)
        elif request.method == 'OPTIONS':
            resp = requests.options(target_url, headers=headers, stream=True, timeout=30)
        elif request.method == 'HEAD':
            resp = requests.head(target_url, headers=headers, timeout=30)
        else:
            return render_proxy_error(
                405,
                'Method Not Supported',
                f'The HTTP method {request.method} is not supported by the proxy.',
                details='Only GET, POST, PUT, DELETE, PATCH, OPTIONS, and HEAD methods are supported.',
                suggestions=[
                    'Check that your client is using a supported HTTP method',
                    'Most Home Assistant operations use GET or POST',
                    'If you need this method, please contact support'
                ]
            )
        
        # Build response headers
        response_headers = []
        content_type = None
        # For websocket upgrades, we need to preserve Connection and Upgrade headers
        skip_response_headers = ['proxy-authenticate', 'proxy-authorization', 'te', 
                                'trailers', 'transfer-encoding', 'content-encoding', 'content-length']
        if not is_websocket_upgrade:
            # For regular requests, skip these hop-by-hop headers
            skip_response_headers.extend(['connection', 'keep-alive', 'upgrade'])
        
        for key, value in resp.headers.items():
            # Skip hop-by-hop headers and encoding headers (except for websocket upgrades)
            if key.lower() not in skip_response_headers:
                if key.lower() == 'content-type':
                    content_type = value.lower()
                # Rewrite Location header for redirects to include proxy prefix
                # This is crucial for proxy compatibility
                if key.lower() == 'location':
                    original_value = value
                    # Check if this is a relative path (starts with /) and not already prefixed
                    if value.startswith('/') and not value.startswith(f'{ingress_path}/proxy/{port}/') and not value.startswith(f'/proxy/{port}/'):
                        # Rewrite to include ingress path and /proxy/{port}/ prefix
                        value = f'{ingress_path}/proxy/{port}{value}'
                        logger.debug(f'Rewrote Location header to: {value}')
                    # Handle absolute URLs that point to the backend instance
                    # This prevents users from being kicked back to the app index after onboarding
                    elif value.startswith('http://') or value.startswith('https://'):
                        # Parse the URL to check if it's pointing to our backend
                        # Backend URLs look like: http://{DOCKER_HOST_IP}:{port}/path or http://localhost:{port}/path
                        # or external domain: https://edu.wredlund.fi:{port}/path
                        parsed = urllib.parse.urlparse(value)
                        # Check if this is a redirect to the backend instance (matching both port and hostname)
                        # We need to verify both to avoid false positives (e.g., external services on same port)
                        # Note: The backend can be accessed via multiple hostnames depending on Docker setup
                        is_backend_host = parsed.hostname in [DOCKER_HOST_IP, 'localhost', '127.0.0.1', '192.168.50.111']
                        
                        # Also check if the hostname matches the request's Host header (for external domains)
                        # This handles cases like https://edu.wredlund.fi:8123/ when accessed externally
                        request_host = request.headers.get('Host', '')
                        # Strip port from request Host header if present (format can be "host:port" or just "host")
                        request_hostname = request_host.split(':')[0] if request_host else ''
                        if not is_backend_host and request_hostname and parsed.hostname == request_hostname:
                            is_backend_host = True
                        
                        # parsed.port is None if no port is specified in the URL (e.g., 'http://localhost/')
                        # We intentionally exclude URLs without explicit ports to avoid false positives with standard web services
                        is_backend_port = parsed.port is not None and parsed.port == port
                        
                        if is_backend_host and is_backend_port:
                            # Extract the path and rewrite it
                            path_to_rewrite = parsed.path or '/'
                            # Include query string if present
                            if parsed.query:
                                path_to_rewrite += f'?{parsed.query}'
                            # Include fragment if present
                            if parsed.fragment:
                                path_to_rewrite += f'#{parsed.fragment}'
                            # Rewrite to proxy path
                            value = f'{ingress_path}/proxy/{port}{path_to_rewrite}'
                            logger.debug(f'Rewrote absolute URL Location header from {original_value} to: {value}')
                response_headers.append((key, value))
        
        # Log response status for debugging
        if resp.status_code >= 400:
            logger.warning(f'Backend returned error status {resp.status_code} for {target_url}')
            # Try to log response body for errors
            try:
                error_body = resp.text[:500] if hasattr(resp, 'text') else 'Unable to read response'
                logger.warning(f'Error response body: {error_body}')
            except:
                pass
        
        # For HTML responses, inject a <base> tag to help browsers resolve relative URLs
        # This is crucial for making the proxy work correctly with Home Assistant
        should_rewrite_html = (
            content_type and 
            'text/html' in content_type and 
            resp.status_code == 200 and
            request.method == 'GET'
        )
        
        if should_rewrite_html:
            # Read the full response for HTML rewriting
            try:
                html_content = resp.content
                
                # Limit HTML rewriting to first 50KB to prevent ReDoS attacks
                # The <head> tag is always at the beginning of HTML documents
                max_rewrite_size = 50 * 1024
                if len(html_content) > max_rewrite_size:
                    # Only rewrite the first part, then append the rest
                    html_part = html_content[:max_rewrite_size]
                    html_rest = html_content[max_rewrite_size:]
                    html_str = html_part.decode('utf-8', errors='replace')
                    has_rest = True
                else:
                    html_str = html_content.decode('utf-8', errors='replace')
                    has_rest = False
                
                # Inject a <base> tag right after <head> to set the base URL for relative paths
                # This tells the browser that all relative URLs should be resolved relative to /proxy/{port}/
                # When running through Home Assistant ingress, include the ingress path prefix
                base_tag = f'<base href="{ingress_path}/proxy/{port}/">'
                
                # Use a simple string search and replace to avoid ReDoS
                # Look for <head> or <head attributes> (case-insensitive)
                modified = False
                html_lower = html_str.lower()
                
                # Try to find <head> tag (case-insensitive)
                head_start = html_lower.find('<head')
                if head_start >= 0:
                    # Find the end of the opening <head> tag in the original string
                    # (the position from lowercase search is valid for the original string)
                    head_end = html_str.find('>', head_start)
                    if head_end >= 0:
                        # Insert base tag right after <head>
                        html_str = html_str[:head_end + 1] + base_tag + html_str[head_end + 1:]
                        modified = True
                        logger.debug(f'Injected base tag into HTML response for port {port}')
                
                if not modified:
                    # If no <head> tag found, try <html>
                    html_start = html_lower.find('<html')
                    if html_start >= 0:
                        # Find the end of the opening <html> tag in the original string
                        # (the position from lowercase search is valid for the original string)
                        html_end = html_str.find('>', html_start)
                        if html_end >= 0:
                            html_str = html_str[:html_end + 1] + base_tag + html_str[html_end + 1:]
                            modified = True
                            logger.debug(f'Injected base tag at start of HTML for port {port}')
                
                if modified:
                    # Convert back to bytes
                    html_content = html_str.encode('utf-8')
                    if has_rest:
                        html_content += html_rest
                    
                    # Update content-length header
                    response_headers = [(k, v) for k, v in response_headers if k.lower() != 'content-length']
                    response_headers.append(('Content-Length', str(len(html_content))))
                    
                    # Return the modified HTML content
                    # Note: The content comes from the backend Home Assistant instance,
                    # not from user input. This is safe as we're acting as a reverse proxy.
                    return Response(
                        html_content,
                        status=resp.status_code,
                        headers=response_headers
                    )
                    
            except Exception as e:
                logger.warning(f'Failed to rewrite HTML content: {e}. Falling back to streaming.')
                # Fall through to streaming if rewriting fails
        
        # For non-HTML or if rewriting failed, stream the response back to the client
        def generate():
            for chunk in resp.iter_content(chunk_size=8192):
                if chunk:
                    yield chunk
        
        return Response(
            stream_with_context(generate()),
            status=resp.status_code,
            headers=response_headers
        )
        
    except requests.exceptions.Timeout:
        logger.warning(f'Timeout while proxying to port {port}')
        return render_proxy_error(
            504,
            'Request Timeout',
            'The request to the Home Assistant instance timed out.',
            details=f'The instance on port {port} did not respond within 30 seconds.',
            suggestions=[
                'The instance might be under heavy load or processing a complex request',
                'Try refreshing the page in a few moments',
                'Check if the instance is responding by going back to the portal',
                'If the problem persists, try accessing the instance directly'
            ]
        )
    except requests.exceptions.ConnectionError:
        logger.warning(f'Connection error while proxying to port {port} (instance may still be starting up)')
        return render_proxy_error(
            502,
            'Cannot Connect to Instance',
            'Unable to connect to the Home Assistant instance.',
            details=f'The instance on port {port} may still be starting up or has stopped responding.',
            suggestions=[
                'Wait 1-2 minutes for the instance to fully start up',
                'Refresh this page to try again',
                'Go back to the portal to check the instance status',
                'If you just created this instance, it needs time to initialize',
                'For debugging, you can try direct port access if ports are exposed'
            ]
        )
    except Exception as e:
        logger.error(f'Error proxying request to port {port}: {str(e)}', exc_info=True)
        return render_proxy_error(
            500,
            'Proxy Error',
            'An unexpected error occurred while connecting to the instance.',
            details=f'Technical details: {str(e)}',
            suggestions=[
                'Try refreshing the page',
                'Go back to the portal homepage',
                'If the problem persists, contact support'
            ]
        )

def proxy_websocket_connection(client_ws, backend_url, port):
    """Proxy a WebSocket connection between client and Home Assistant backend
    
    Args:
        client_ws: The client WebSocket connection (flask-sock)
        backend_url: The backend WebSocket URL (ws://...)
        port: The port number for logging
    """
    backend_ws = None
    try:
        # Connect to the backend WebSocket
        logger.info(f'Establishing WebSocket connection to backend: {backend_url}')
        backend_ws = simple_websocket.Client(backend_url)
        logger.info(f'WebSocket connection established for port {port}')
        
        # Create two threads to forward messages in both directions
        client_to_backend_error = []
        backend_to_client_error = []
        
        def forward_client_to_backend():
            """Forward messages from client to backend"""
            try:
                while True:
                    try:
                        # Receive message from client
                        message = client_ws.receive(timeout=0.1)
                        if message is None:
                            continue
                        # Send to backend
                        backend_ws.send(message)
                    except simple_websocket.ConnectionClosed:
                        logger.info(f'Client WebSocket closed for port {port}')
                        break
                    except Exception as e:
                        if 'timeout' not in str(e).lower():
                            logger.warning(f'Error forwarding client->backend for port {port}: {e}')
                            client_to_backend_error.append(e)
                            break
            except Exception as e:
                logger.error(f'Fatal error in client->backend thread for port {port}: {e}')
                client_to_backend_error.append(e)
        
        def forward_backend_to_client():
            """Forward messages from backend to client"""
            try:
                while True:
                    try:
                        # Receive message from backend
                        message = backend_ws.receive(timeout=0.1)
                        if message is None:
                            continue
                        # Send to client
                        client_ws.send(message)
                    except simple_websocket.ConnectionClosed:
                        logger.info(f'Backend WebSocket closed for port {port}')
                        break
                    except Exception as e:
                        if 'timeout' not in str(e).lower():
                            logger.warning(f'Error forwarding backend->client for port {port}: {e}')
                            backend_to_client_error.append(e)
                            break
            except Exception as e:
                logger.error(f'Fatal error in backend->client thread for port {port}: {e}')
                backend_to_client_error.append(e)
        
        # Start forwarding threads
        client_thread = threading.Thread(target=forward_client_to_backend, daemon=True)
        backend_thread = threading.Thread(target=forward_backend_to_client, daemon=True)
        
        client_thread.start()
        backend_thread.start()
        
        # Wait for both threads to complete
        client_thread.join()
        backend_thread.join()
        
        logger.info(f'WebSocket proxy closed for port {port}')
        
    except simple_websocket.ConnectionError as e:
        logger.error(f'Failed to connect to backend WebSocket at {backend_url}: {e}')
        try:
            client_ws.close(reason=1011, message=f'Backend connection failed: {str(e)}')
        except:
            pass
    except Exception as e:
        logger.error(f'Error in WebSocket proxy for port {port}: {e}', exc_info=True)
        try:
            client_ws.close(reason=1011, message='Proxy error')
        except:
            pass
    finally:
        # Clean up connections
        if backend_ws:
            try:
                backend_ws.close()
            except:
                pass

def _websocket_proxy_handler(ws, port=None):
    """Internal WebSocket proxy handler shared by both routes
    
    This handler proxies WebSocket connections from clients to Home Assistant instances.
    It supports both direct paths (/api/websocket) and proxy paths (/proxy/{port}/api/websocket).
    
    Args:
        ws: The WebSocket connection object
        port: Optional port number (if not provided, will be determined from session/instance)
    """
    # If port is not in the URL, try to determine it from session or single instance
    if port is None:
        # Try to get port from session
        if 'proxy_port' in session:
            port = session['proxy_port']
            logger.info(f'Using port {port} from session for WebSocket')
        else:
            # Check if there's only one instance
            instances = load_instances()
            if len(instances) == 1:
                port = list(instances.values())[0]['port']
                logger.info(f'Using single instance port {port} for WebSocket')
            else:
                logger.error(f'Cannot determine target instance for WebSocket. {len(instances)} instances available.')
                ws.close(reason=1008, message='Unable to determine target instance')
                return
    
    # Verify that the port belongs to a valid instance
    instances = load_instances()
    valid_port = False
    for inst in instances.values():
        if inst['port'] == port:
            valid_port = True
            break
    
    if not valid_port:
        logger.warning(f'Invalid port {port} requested for WebSocket')
        ws.close(reason=1008, message=f'Invalid instance port {port}')
        return
    
    # Store port in session for future requests
    session['proxy_port'] = port
    
    # Build the backend WebSocket URL
    backend_url = f'ws://{DOCKER_HOST_IP}:{port}/api/websocket'
    
    logger.info(f'WebSocket proxy established for port {port}')
    
    # Proxy the WebSocket connection
    proxy_websocket_connection(ws, backend_url, port)

@sock.route('/api/websocket')
def websocket_proxy_direct(ws):
    """WebSocket proxy endpoint for direct /api/websocket path"""
    _websocket_proxy_handler(ws, port=None)

@sock.route('/proxy/<int:port>/api/websocket')
def websocket_proxy_with_port(ws, port):
    """WebSocket proxy endpoint for /proxy/{port}/api/websocket path"""
    _websocket_proxy_handler(ws, port=port)

@app.route('/api/logs', methods=['GET'])
def get_interaction_logs():
    """API endpoint to retrieve interaction logs (admin only)
    
    Query parameters:
        limit: Maximum number of log entries to return (default: 100)
        event_type: Filter by event type (optional)
    
    Returns:
        JSON array of log entries
    """
    # Check admin access
    if not is_admin_user(request):
        return jsonify({'error': 'Admin access required'}), 403
    
    # Get query parameters
    limit = request.args.get('limit', 100, type=int)
    event_type = request.args.get('event_type', None)
    
    # Limit to reasonable range
    limit = min(max(limit, 1), 1000)
    
    # Retrieve logs
    logs = interaction_logger.get_logs(limit=limit, event_type=event_type)
    
    return jsonify({
        'logs': logs,
        'count': len(logs)
    }), 200

# Clean up orphaned containers on startup (runs when module is imported)
logger.info('Starting HA-Edu Portal...')
cleanup_orphaned_containers()

if __name__ == '__main__':
    # This block is used when running directly with Python (development mode)
    # In production, Gunicorn will import the app object directly
    app.run(host='0.0.0.0', port=5000, debug=False)
