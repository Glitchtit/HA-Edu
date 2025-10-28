import os
import json
import logging
import secrets
from flask import Flask, render_template, request, jsonify
import docker
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
client = docker.from_env()

# Configuration
DATA_FILE = os.getenv('DATA_FILE', '/data/instances.json')
BASE_PORT = int(os.getenv('BASE_PORT', '8123'))
# MAX_INSTANCES removed - no limit on instances, ports assigned dynamically
HA_IMAGE = os.getenv('HA_IMAGE', 'ghcr.io/home-assistant/home-assistant:stable')
ADMIN_PASSWORD = os.getenv('ADMIN_PASSWORD', '')
MASTER_CONFIG_PATH = os.path.join(os.path.dirname(__file__), 'master_configuration.yaml')

def load_instances():
    """Load instances from JSON file"""
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r') as f:
            return json.load(f)
    return {}

def save_instances(instances):
    """Save instances to JSON file"""
    os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)
    with open(DATA_FILE, 'w') as f:
        json.dump(instances, f, indent=2)

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
        
        for container in all_containers:
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
                            break
                    
                    if found:
                        save_instances(instances)
                    else:
                        # Truly orphaned - stop and remove
                        logger.info(f'Removing truly orphaned container: {container.name}')
                        if container.status == 'running':
                            container.stop(timeout=10)
                        container.remove()
                except Exception as e:
                    logger.error(f'Failed to handle orphaned container {container.name}: {str(e)}')
        
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
    # No max_instances limit - show active count only
    return render_template('index.html', instances=instances)

@app.route('/api/instances', methods=['GET'])
def get_instances():
    """API endpoint to get all instances"""
    instances = load_instances()
    return jsonify(instances)

@app.route('/api/instances', methods=['POST'])
def create_instance():
    """API endpoint to create a new Home Assistant instance"""
    data = request.json
    server_name = data.get('server_name', '').strip()
    password = data.get('password', '').strip()
    
    if not server_name or not password:
        return jsonify({'error': 'Server name and password are required'}), 400
    
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
        # Note: Password storage is simplified for educational use.
        # For production, use proper password hashing (e.g., bcrypt)
        instances[server_name] = {
            'container_id': container.id,
            'container_name': container_name,
            'port': port,
            'password': password,
            'created_at': datetime.now().isoformat(),
            'status': 'running'
        }
        save_instances(instances)
        
        return jsonify({
            'message': 'Instance created successfully',
            'server_name': server_name,
            'port': port,
            'url': f'http://{request.host.split(":")[0]}:{port}'
        }), 201
        
    except Exception as e:
        logger.error(f'Failed to create instance: {str(e)}', exc_info=True)
        return jsonify({'error': 'Failed to create instance. Please try again or contact support.'}), 500

@app.route('/api/instances/<server_name>', methods=['DELETE'])
def delete_instance(server_name):
    """API endpoint to delete an instance"""
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

if __name__ == '__main__':
    # Clean up orphaned containers on startup
    logger.info('Starting HA-Edu Portal...')
    cleanup_orphaned_containers()
    app.run(host='0.0.0.0', port=5000, debug=False)
