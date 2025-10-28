import os
import json
import logging
import secrets
import re
from flask import Flask, render_template, request, jsonify, Response, stream_with_context, session
import docker
from datetime import datetime
import requests

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Disable Flask's default static folder to avoid conflicts with Home Assistant's /static/ paths
app = Flask(__name__, static_folder=None)
# Set a secret key for session management
app.secret_key = os.getenv('SECRET_KEY', secrets.token_hex(32))
client = docker.from_env()

# Configuration
DATA_FILE = os.getenv('DATA_FILE', '/data/instances.json')
BASE_PORT = int(os.getenv('BASE_PORT', '8123'))
# MAX_INSTANCES removed - no limit on instances, ports assigned dynamically
HA_IMAGE = os.getenv('HA_IMAGE', 'ghcr.io/home-assistant/home-assistant:stable')
ADMIN_PASSWORD = os.getenv('ADMIN_PASSWORD', '')
MASTER_CONFIG_PATH = os.path.join(os.path.dirname(__file__), 'master_configuration.yaml')

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
    """
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
        temp_container.stop()
        temp_container.remove()
        
        logger.info(f'Successfully copied master configuration to volume {volume_name}')
        return True
        
    except Exception as e:
        logger.error(f'Failed to copy master configuration to volume {volume_name}: {str(e)}', exc_info=True)
        # Clean up on error
        try:
            temp_container.stop()
            temp_container.remove(force=True)
        except:
            pass
        return False

@app.route('/')
def index():
    """Main page with instance management UI"""
    instances = load_instances()
    # Update status for each instance by checking actual container state
    update_instances_status(instances)
    # No max_instances limit - show active count only
    return render_template('index.html', instances=instances)

@app.route('/api/instances', methods=['GET'])
def get_instances():
    """API endpoint to get all instances with real-time status"""
    instances = load_instances()
    # Update status for each instance by checking actual container state
    update_instances_status(instances)
    return jsonify(instances)

@app.route('/api/instances', methods=['POST'])
def create_instance():
    """API endpoint to create a new Home Assistant instance"""
    # Check if instance creation is enabled
    settings = load_settings()
    if not settings.get('instance_creation_enabled', True):
        return jsonify({'error': 'Instance creation is currently disabled'}), 403
    
    data = request.json
    server_name = data.get('server_name', '').strip()
    
    if not server_name:
        return jsonify({'error': 'Server name is required'}), 400
    
    instances = load_instances()
    
    # Check if server name already exists
    if server_name in instances:
        return jsonify({'error': 'Server name already exists'}), 400
    
    # Get available port (no limit check - dynamic port assignment)
    port = get_available_port()
    
    try:
        # Create container
        container_name = f'ha-edu-{server_name.lower().replace(" ", "-")}'
        volume_name = container_name
        
        # Copy master configuration to the volume before starting the container
        copy_master_config_to_volume(volume_name)
        
        # Network configuration: Create container with bridge network for internet access
        # but isolated from host LAN. This works with Cloudflare tunnel setup.
        container = client.containers.run(
            HA_IMAGE,
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
        
        # Save instance info
        instances[server_name] = {
            'container_id': container.id,
            'container_name': container_name,
            'port': port,
            'created_at': datetime.now().isoformat(),
            'status': 'running'
        }
        save_instances(instances)
        
        return jsonify({
            'message': 'Instance created successfully',
            'server_name': server_name,
            'port': port,
            'url': f'/proxy/{port}/'
        }), 201
        
    except Exception as e:
        logger.error(f'Failed to create instance: {str(e)}', exc_info=True)
        return jsonify({'error': 'Failed to create instance. Please try again or contact support.'}), 500

@app.route('/api/instances/<server_name>', methods=['DELETE'])
def delete_instance(server_name):
    """API endpoint to delete an instance (requires admin password)"""
    if not ADMIN_PASSWORD:
        return jsonify({'error': 'Admin password not configured'}), 403
    
    data = request.json or {}
    admin_password = data.get('admin_password', '')
    
    # Use constant-time comparison to prevent timing attacks
    if not secrets.compare_digest(admin_password, ADMIN_PASSWORD):
        return jsonify({'error': 'Invalid admin password'}), 401
    
    instances = load_instances()
    
    if server_name not in instances:
        return jsonify({'error': 'Instance not found'}), 404
    
    try:
        instance = instances[server_name]
        
        # Stop and remove container
        try:
            container = client.containers.get(instance['container_id'])
            container.stop()
            container.remove()
        except docker.errors.NotFound:
            pass  # Container already removed
        
        # Remove from instances
        del instances[server_name]
        save_instances(instances)
        
        return jsonify({'message': 'Instance deleted successfully'}), 200
        
    except Exception as e:
        logger.error(f'Failed to delete instance: {str(e)}', exc_info=True)
        return jsonify({'error': 'Failed to delete instance. Please try again or contact support.'}), 500

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
    """API endpoint to reset an instance to default HA image (requires admin password)"""
    if not ADMIN_PASSWORD:
        return jsonify({'error': 'Admin password not configured'}), 403
    
    data = request.json
    admin_password = data.get('admin_password', '')
    
    # Use constant-time comparison to prevent timing attacks
    if not secrets.compare_digest(admin_password, ADMIN_PASSWORD):
        return jsonify({'error': 'Invalid admin password'}), 401
    
    instances = load_instances()
    
    if server_name not in instances:
        return jsonify({'error': 'Instance not found'}), 404
    
    try:
        instance = instances[server_name]
        container_name = instance['container_name']
        port = instance['port']
        
        # Stop and remove existing container
        try:
            container = client.containers.get(instance['container_id'])
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
        
        # Create a new container with the same configuration
        # Network configuration: Use bridge network for isolation from host LAN
        new_container = client.containers.run(
            HA_IMAGE,
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
        
        return jsonify({
            'message': 'Instance reset successfully',
            'server_name': server_name
        }), 200
        
    except Exception as e:
        logger.error(f'Failed to reset instance: {str(e)}', exc_info=True)
        return jsonify({'error': 'Failed to reset instance. Please try again or contact support.'}), 500

@app.route('/api/admin/check', methods=['GET'])
def check_admin():
    """API endpoint to check if admin password is configured"""
    return jsonify({'admin_enabled': bool(ADMIN_PASSWORD)}), 200

@app.route('/api/instances/delete-all', methods=['POST'])
def delete_all_instances():
    """API endpoint to delete all instances (requires admin password)"""
    if not ADMIN_PASSWORD:
        return jsonify({'error': 'Admin password not configured'}), 403
    
    data = request.json or {}
    admin_password = data.get('admin_password', '')
    
    # Use constant-time comparison to prevent timing attacks
    if not secrets.compare_digest(admin_password, ADMIN_PASSWORD):
        return jsonify({'error': 'Invalid admin password'}), 401
    
    instances = load_instances()
    
    if not instances:
        return jsonify({'message': 'No instances to delete'}), 200
    
    deleted_count = 0
    failed_count = 0
    
    try:
        # Delete all instances
        for server_name, instance in list(instances.items()):
            try:
                # Stop and remove container
                try:
                    container = client.containers.get(instance['container_id'])
                    container.stop()
                    container.remove()
                except docker.errors.NotFound:
                    pass  # Container already removed
                
                deleted_count += 1
            except Exception as e:
                logger.error(f'Failed to delete instance {server_name}: {str(e)}')
                failed_count += 1
        
        # Clear all instances
        save_instances({})
        
        return jsonify({
            'message': f'Successfully deleted {deleted_count} instance(s)',
            'deleted_count': deleted_count,
            'failed_count': failed_count
        }), 200
        
    except Exception as e:
        logger.error(f'Failed to delete all instances: {str(e)}', exc_info=True)
        return jsonify({'error': 'Failed to delete all instances. Please try again or contact support.'}), 500

@app.route('/api/settings/instance-creation', methods=['GET'])
def get_instance_creation_status():
    """API endpoint to get instance creation status"""
    settings = load_settings()
    return jsonify({
        'instance_creation_enabled': settings.get('instance_creation_enabled', True)
    }), 200

@app.route('/api/settings/instance-creation', methods=['POST'])
def set_instance_creation_status():
    """API endpoint to set instance creation status (requires admin password)"""
    if not ADMIN_PASSWORD:
        return jsonify({'error': 'Admin password not configured'}), 403
    
    data = request.json or {}
    admin_password = data.get('admin_password', '')
    enabled = data.get('enabled', True)
    
    # Use constant-time comparison to prevent timing attacks
    if not secrets.compare_digest(admin_password, ADMIN_PASSWORD):
        return jsonify({'error': 'Invalid admin password'}), 401
    
    settings = load_settings()
    settings['instance_creation_enabled'] = enabled
    save_settings(settings)
    
    return jsonify({
        'message': 'Instance creation status updated successfully',
        'instance_creation_enabled': enabled
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
    # Store the port in session for fallback requests
    session['proxy_port'] = port
    
    # Verify that the port belongs to a valid instance
    instances = load_instances()
    valid_port = False
    for inst in instances.values():
        if inst['port'] == port:
            valid_port = True
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
    
    # Build the target URL
    target_url = f'http://192.168.50.111:{port}/{path}'
    
    # Get query string if present
    if request.query_string:
        target_url += f'?{request.query_string.decode("utf-8")}'
    
    # Log the proxied request for debugging
    logger.info(f'Proxying {request.method} request to: {target_url}')
    
    # Check if this is a WebSocket upgrade request
    if request.headers.get('Upgrade', '').lower() == 'websocket':
        return render_proxy_error(
            400,
            'WebSocket Not Supported',
            'WebSocket connections are not supported through the proxy.',
            details='The proxy can only forward regular HTTP requests. WebSocket connections require direct access to the instance.',
            suggestions=[
                'Use the direct port access if WebSocket support is needed',
                'Most Home Assistant features work without WebSocket',
                'WebSocket is mainly used for real-time updates'
            ]
        )
    
    try:
        # Forward the request to the HA instance
        # Copy headers but modify Host and other proxy-specific headers
        headers = {}
        for key, value in request.headers.items():
            # Skip hop-by-hop headers and encoding headers that can cause issues
            if key.lower() not in ['host', 'connection', 'keep-alive', 'accept-encoding']:
                headers[key] = value

        # Set the correct Host header for the backend
        headers['Host'] = f'192.168.50.111:{port}'
        
        # Add proxy headers that HA needs
        headers['X-Forwarded-For'] = request.remote_addr
        headers['X-Forwarded-Proto'] = request.scheme
        headers['X-Forwarded-Host'] = request.host
        headers['X-Forwarded-Prefix'] = f'/proxy/{port}'
        headers['X-Ingress-Path'] = f'/proxy/{port}'
        
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
        for key, value in resp.headers.items():
            # Skip hop-by-hop headers and encoding headers
            if key.lower() not in ['connection', 'keep-alive', 'proxy-authenticate', 
                                'proxy-authorization', 'te', 'trailers', 'transfer-encoding', 
                                'upgrade', 'content-encoding', 'content-length']:
                if key.lower() == 'content-type':
                    content_type = value.lower()
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
                base_tag = f'<base href="/proxy/{port}/">'
                
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

if __name__ == '__main__':
    # Clean up orphaned containers on startup
    logger.info('Starting HA-Edu Portal...')
    cleanup_orphaned_containers()
    app.run(host='0.0.0.0', port=5000, debug=False)
