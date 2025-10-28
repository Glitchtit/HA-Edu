# HA-Edu
Educational Portal for Home Assistant

A web-based portal for managing multiple Home Assistant demo instances for educational purposes. Perfect for classroom environments where students need their own isolated Home Assistant instances.

## Features

- 🚀 **Easy Instance Creation**: Create new Home Assistant instances with a simple web interface
- 🔐 **Password Protected**: Each instance can have its own password
- 🔑 **Admin Password**: Optional admin password for managing all instances
- ♻️ **Instance Reset**: Reset any instance to default HA image using admin password
- 📊 **Instance Management**: View and manage up to 15 concurrent instances
- 🐳 **Docker Based**: Fully containerized for easy deployment on Unraid or any Docker host
- 🔄 **Automatic Port Assignment**: Systematically assigns ports from 8123-8137
- 📱 **Responsive UI**: Clean, modern interface that works on all devices

## Quick Start

### Prerequisites

- Docker and Docker Compose installed
- Access to Docker socket (for container management)

### Deployment with Docker Compose

1. Clone this repository:
```bash
git clone https://github.com/Glitchtit/HA-Edu.git
cd HA-Edu
```

2. Start the portal:
```bash
docker-compose up -d
```

3. Access the portal at `http://localhost:5000`

### Deployment on Unraid

1. Add a new container in Unraid's Docker tab
2. Configure the following settings:
   - **Repository**: Build from this repository or use a pre-built image
   - **Port**: `5000` (WebUI)
   - **Ports for HA instances**: `8123-8137` (15 instances)
   - **Volume Mappings**:
     - Container Path: `/var/run/docker.sock` → Host Path: `/var/run/docker.sock`
     - Container Path: `/data` → Host Path: `/mnt/user/appdata/ha-edu`
   - **Environment Variables**:
     - `BASE_PORT`: `8123` (starting port for instances)
     - `MAX_INSTANCES`: `15` (maximum number of instances)
     - `HA_IMAGE`: `ghcr.io/home-assistant/home-assistant:stable`
     - `ADMIN_PASSWORD`: (optional) Admin password for reset functionality

### Manual Docker Build

```bash
# Build the image
docker build -t ha-edu-portal .

# Run the container
docker run -d \
  --name ha-edu-portal \
  -p 5000:5000 \
  -p 8123-8137:8123-8137 \
  -v /var/run/docker.sock:/var/run/docker.sock \
  -v $(pwd)/data:/data \
  -e BASE_PORT=8123 \
  -e MAX_INSTANCES=15 \
  ha-edu-portal
```

## Usage

### Creating a New Instance

1. Click the "**+ Add New Instance**" button
2. Enter a **Server Name** (e.g., "Student-Lab-01")
3. Enter a **Password** for the instance
4. Click "**Create**"
5. Wait for the instance to be created (may take 1-2 minutes)
6. Click "**Access**" to open the Home Assistant instance

### Deleting an Instance

1. Click the "**Delete**" button on the instance card
2. Confirm the deletion
3. The instance and its data will be removed

### Resetting an Instance (Admin Only)

If an admin password is configured, you can reset any instance to its default state:

1. Click the "**Reset**" button on the instance card (only visible when admin password is set)
2. Enter the **Admin Password**
3. Confirm the reset
4. The instance will be completely reset to a fresh Home Assistant installation
5. **Warning**: This will delete all data and configurations for that instance!

## Configuration

Environment variables can be configured to customize the portal:

| Variable | Default | Description |
|----------|---------|-------------|
| `BASE_PORT` | `8123` | Starting port number for HA instances |
| `MAX_INSTANCES` | `15` | Maximum number of concurrent instances |
| `DATA_FILE` | `/data/instances.json` | Path to store instance data |
| `HA_IMAGE` | `ghcr.io/home-assistant/home-assistant:stable` | Home Assistant Docker image to use |
| `ADMIN_PASSWORD` | (empty) | Admin password for reset functionality. If not set, reset buttons are hidden |

## Architecture

The portal consists of:
- **Flask Web Application**: Provides the UI and API
- **Docker SDK**: Manages Home Assistant containers
- **Instance Storage**: JSON-based storage for instance metadata

Each Home Assistant instance:
- Runs in its own Docker container
- Has a dedicated volume for configuration
- Is accessible on a unique port (8123-8137)
- Runs in demo mode for educational purposes

## Port Assignment

Ports are assigned sequentially:
- Portal UI: `5000`
- HA Instance 1: `8123`
- HA Instance 2: `8124`
- ...
- HA Instance 15: `8137`

## Security Considerations

- The portal requires access to the Docker socket (`/var/run/docker.sock`)
- Consider running behind a reverse proxy with authentication
- Password storage is simplified for educational use - enhance for production
- Admin password provides elevated access - store securely (e.g., in Unraid environment variables)
- Admin password enables reset of any instance, even after student passwords change
- Limit network access to trusted networks only

## Troubleshooting

### Container won't start
- Check that Docker socket is accessible
- Verify port range 8123-8137 is available
- Check logs: `docker logs ha-edu-portal`

### Can't create instances
- Ensure Docker socket permissions are correct
- Check available disk space
- Verify Docker can pull the Home Assistant image

### Instance not accessible
- Wait 1-2 minutes for Home Assistant to fully start
- Check the container is running: `docker ps`
- Verify firewall rules allow the port

## Development

### Local Development Setup

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run the application
python app.py
```

### File Structure

```
HA-Edu/
├── app.py                 # Main Flask application
├── templates/
│   └── index.html        # Web UI template
├── static/               # Static assets (if needed)
├── Dockerfile            # Container definition
├── docker-compose.yml    # Compose configuration
├── requirements.txt      # Python dependencies
└── README.md            # This file
```

## License

This project is open source and available for educational use.

## Contributing

Contributions are welcome! Please feel free to submit issues or pull requests.

## Support

For issues or questions, please open an issue on GitHub.
