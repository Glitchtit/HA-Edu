import os
import json
from flask import Flask, render_template, request, jsonify
import docker
from datetime import datetime

app = Flask(__name__)
client = docker.from_env()

# Configuration
DATA_FILE = os.getenv('DATA_FILE', '/data/instances.json')
BASE_PORT = int(os.getenv('BASE_PORT', '8123'))
MAX_INSTANCES = int(os.getenv('MAX_INSTANCES', '15'))
HA_IMAGE = os.getenv('HA_IMAGE', 'ghcr.io/home-assistant/home-assistant:stable')

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
    """Get next available port for a new instance"""
    instances = load_instances()
    used_ports = [inst['port'] for inst in instances.values()]
    
    for i in range(MAX_INSTANCES):
        port = BASE_PORT + i
        if port not in used_ports:
            return port
    return None

@app.route('/')
def index():
    """Main page with instance management UI"""
    instances = load_instances()
    return render_template('index.html', instances=instances, max_instances=MAX_INSTANCES)

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
    
    # Check if we've reached max instances
    if len(instances) >= MAX_INSTANCES:
        return jsonify({'error': f'Maximum number of instances ({MAX_INSTANCES}) reached'}), 400
    
    # Get available port
    port = get_available_port()
    if port is None:
        return jsonify({'error': 'No available ports'}), 500
    
    try:
        # Create container
        container_name = f'ha-edu-{server_name.lower().replace(" ", "-")}'
        
        container = client.containers.run(
            HA_IMAGE,
            name=container_name,
            detach=True,
            ports={'8123/tcp': port},
            environment={
                'TZ': 'UTC'
            },
            volumes={
                f'ha-edu-{container_name}': {'bind': '/config', 'mode': 'rw'}
            },
            restart_policy={'Name': 'unless-stopped'}
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
        return jsonify({'error': f'Failed to create instance: {str(e)}'}), 500

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
        return jsonify({'error': f'Failed to delete instance: {str(e)}'}), 500

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

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)
