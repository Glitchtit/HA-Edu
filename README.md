# HA-Edu
Educational Portal for Home Assistant

A web-based portal for managing multiple Home Assistant demo instances for educational purposes. Perfect for classroom environments where students need their own isolated Home Assistant instances.

## Features

- 🚀 **Easy Instance Creation**: Create new Home Assistant instances with a simple web interface - no password required
- 🔑 **Admin Password Protected**: Admin password required for deleting and resetting instances
- 🔐 **Role-Based Access Control**: Control admin access via local network or Cloudflare Zero Trust email authentication
- 👨‍🏫 **Teacher Access**: Optional feature to add teacher admin accounts to student instances after onboarding
- ♻️ **Instance Reset**: Reset any instance to default HA image using admin password
- 📊 **Instance Management**: View and manage unlimited instances
- 📝 **Interaction Logging**: Comprehensive logging of all user and admin interactions (create, delete, access, etc.)
- 🐳 **Docker Based**: Fully containerized for easy deployment on Unraid or any Docker host
- 🔄 **Automatic Port Assignment**: Dynamically assigns ports starting from BASE_PORT (default: 8123)
- ♻️ **Port Reuse**: Automatically reuses ports from deleted instances
- 🌐 **Network Isolation**: Instances have internet access but are isolated from host LAN
- 📱 **Responsive UI**: Clean, modern interface that works on all devices
- ☁️ **Cloudflare Tunnel Ready**: Designed to work with Cloudflare tunnel for secure external access
- 🔀 **Built-in Proxy**: Access all instances through a single endpoint without exposing individual ports

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

#### Option 1: Using Template (Recommended)

1. In Unraid's Docker tab, click "Add Container"
2. In the "Template" dropdown, select "ha-edu-portal" or add the template URL:
   ```
   https://raw.githubusercontent.com/Glitchtit/HA-Edu/main/ha-edu.xml
   ```
3. Configure the settings as needed (all environment variables have sensible defaults)
4. Click "Apply" to create the container

#### Option 2: Manual Configuration

1. Add a new container in Unraid's Docker tab
2. Configure the following settings:
   - **Repository**: Build from this repository or use a pre-built image
   - **Port**: `5000` (WebUI)
   - **Ports for HA instances**: Dynamic - no need to pre-allocate ports
   - **Volume Mappings**:
     - Container Path: `/var/run/docker.sock` → Host Path: `/var/run/docker.sock`
     - Container Path: `/data` → Host Path: `/mnt/user/appdata/ha-edu`
   - **Environment Variables**:
     - `BASE_PORT`: `8123` (starting port for instances, assigned dynamically)
     - `HA_IMAGE`: `ghcr.io/home-assistant/home-assistant:stable`
     - `ADMIN_PASSWORD`: (optional) Admin password for reset functionality
     - `ADMINS`: (optional) Comma-separated list of email addresses for admin access via Cloudflare Zero Trust
   - **Network Mode**: `bridge` (for proper isolation)

### Admin Access Control

The portal supports fine-grained admin access control based on network location and Cloudflare Zero Trust authentication:

**Admin access is granted if:**
- User is accessing from the local network (`192.168.50.0/24` subnet), OR
- User is authenticated via Cloudflare Zero Trust with an email address in the `ADMINS` environment variable

**Configuration:**
```bash
# Example: Grant admin access to specific email addresses
ADMINS=admin@example.com,teacher@example.com
```

**How it works:**
- When users access the portal through Cloudflare Zero Trust, Cloudflare sets the `Cf-Access-Authenticated-User-Email` header
- The portal checks if this email is in the approved `ADMINS` list (case-insensitive)
- Users without admin access won't see the unlock button or admin controls
- Local network users (192.168.50.x) always have admin access regardless of the `ADMINS` setting

**Security features:**
- Email comparison is case-insensitive
- Supports reverse proxy configurations (checks `X-Forwarded-For` header)
- Admin buttons are hidden client-side for non-admin users
- Server-side validation ensures only authorized users can perform admin actions

### Network Isolation & Cloudflare Tunnel

The portal is designed to work with Cloudflare tunnel for secure external access:
- **Internet Access**: ✅ Instances can access the internet (via NAT)
- **LAN Access**: ❌ Instances are isolated from the host's LAN network
- **Device Discovery**: ❌ Instances cannot discover devices on the main network
- **External Access**: ✅ Via Cloudflare tunnel (e.g., edu.wredlund.fi)
- **Port Exposure**: ✅ No need to expose individual instance ports - built-in proxy routes all traffic through port 5000

#### Proxy Feature

The portal includes a built-in proxy that allows all Home Assistant instances to be accessed through the portal's single endpoint (port 5000). When users click "Access" on an instance, they're redirected to `/proxy/<port>/` which internally forwards all requests to the appropriate Home Assistant instance.

**Benefits:**
- ✅ Only port 5000 needs to be exposed through Cloudflare tunnel
- ✅ No need to configure individual ports for each instance
- ✅ Works seamlessly with firewall restrictions
- ✅ Simplified network configuration

**Technical Details:**
- The proxy forwards all HTTP methods (GET, POST, PUT, DELETE, etc.)
- Query strings and URL paths are preserved
- Response headers and status codes are passed through correctly
- Validates that requested ports belong to actual instances
- WebSocket upgrade requests are forwarded to the backend (the backend handles the websocket protocol)

To set up Cloudflare tunnel:
1. Install cloudflared on your Unraid server
2. Create a tunnel and point it to the portal (port 5000)
3. Configure authentication in Cloudflare dashboard
4. Users access instances through the portal UI via the tunnel - all instance access automatically goes through the proxy

### Manual Docker Build

```bash
# Build the image
docker build -t ha-edu-portal .

# Run the container
docker run -d \
  --name ha-edu-portal \
  -p 5000:5000 \
  -v /var/run/docker.sock:/var/run/docker.sock \
  -v $(pwd)/data:/data \
  -e BASE_PORT=8123 \
  ha-edu-portal
```

## Usage

### Creating a New Instance

1. Click the "**+ Add New Instance**" button
2. Enter a **Server Name** (e.g., "Student-Lab-01")
3. Click "**Create**"
4. Wait for the instance to be created (may take 1-2 minutes)
5. Click "**Access**" to open the Home Assistant instance

### Deleting an Instance (Admin Only)

Deleting an instance requires the admin password:

1. Click the "**Delete**" button on the instance card
2. Enter the **Admin Password**
3. Confirm the deletion
4. The instance and its data will be removed

### Resetting an Instance (Admin Only)

If an admin password is configured, you can reset any instance to its default state:

1. Click the "**Reset**" button on the instance card (only visible when admin password is set)
2. Enter the **Admin Password**
3. Confirm the reset
4. The instance will be completely reset to a fresh Home Assistant installation
5. **Warning**: This will delete all data and configurations for that instance!

### Teacher Access (Optional Feature)

The Teacher Access feature allows instructors to add a secondary admin account to student instances for monitoring purposes. This preserves the educational value of students going through onboarding themselves while giving teachers access.

**Requirements:**
- Both `TEACHER_USERNAME` and `TEACHER_PASSWORD` environment variables must be configured
- Admin password must be configured
- Students must complete the onboarding process first

**How to use:**

1. Students create and set up their instances using the onboarding wizard
2. After students complete onboarding, click the "**👨‍🏫 Teacher**" button on the instance card
3. Enter the **Admin Password**
4. Confirm to create the teacher admin account
5. Teacher can now log in using the configured teacher credentials

**Key Features:**
- Teacher account is created as a secondary administrator
- Student's account and data remain unchanged
- Teacher can monitor student progress and configurations
- Cannot be added until student completes onboarding
- Instance cards show a "👨‍🏫 Teacher Access" badge when enabled

## Configuration

Environment variables can be configured to customize the portal:

| Variable | Default | Description |
|----------|---------|-------------|
| `BASE_PORT` | `8123` | Starting port number for HA instances (dynamically assigned) |
| `DATA_FILE` | `/data/instances.json` | Path to store instance data |
| `LOG_DIR` | `/logs` | Path to store interaction logs |
| `HA_IMAGE` | `ghcr.io/home-assistant/home-assistant:stable` | Home Assistant Docker image to use |
| `ADMIN_PASSWORD` | (empty) | **Required** admin password for delete and reset operations. If not set, delete and reset operations will fail |
| `TEACHER_USERNAME` | (empty) | *Optional* Username for teacher admin account. Required for Teacher Access feature |
| `TEACHER_PASSWORD` | (empty) | *Optional* Password for teacher admin account. Required for Teacher Access feature |
| `ADMINS` | (empty) | *Optional* Comma-separated list of admin email addresses for Cloudflare authentication |
| `MAX_INSTANCES` | `0` (unlimited) | *Optional* Maximum instances per non-admin user (0 = unlimited) |

For more details on interaction logging, see [LOGGING.md](LOGGING.md).

## Architecture

The portal consists of:
- **Flask Web Application**: Provides the UI and API
- **Built-in Proxy Server**: Routes all instance traffic through the portal
- **Docker SDK**: Manages Home Assistant containers
- **Instance Storage**: JSON-based storage for instance metadata

Each Home Assistant instance:
- Runs in its own Docker container
- Has a dedicated volume for configuration
- Is accessible on a unique dynamically-assigned port (internal)
- Accessible via the proxy at `/proxy/<port>/` (external)
- Uses bridge network mode for isolation from host LAN
- Has internet access but cannot discover LAN devices
- Runs in demo mode for educational purposes
- Starts with a pre-configured master configuration that includes:
  - 5 demo lights
  - 1 weather entity
  - 1 thermostat
  - 2 device trackers
  - 1 camera
  - 2 buttons

## Master Configuration

The portal uses a master `configuration.yaml` file that is automatically copied to each new instance or reset instance. This configuration enables Home Assistant's demo mode and provides sample entities for educational purposes.

The master configuration includes:
- **Demo Platform**: Enables all demo integrations
- **5 Lights**: Demo Light 1-5 for testing automations and controls
- **Weather**: Demo weather entity for location-based scenarios
- **Climate**: Demo thermostat for temperature control learning
- **Device Trackers**: 2 demo trackers for presence detection scenarios
- **Camera**: Demo camera for media and security scenarios
- **Buttons**: 2 input buttons for triggering automations

When an instance is created or reset, this master configuration is automatically deployed, ensuring a consistent starting point for all users.

## Port Assignment

Ports are assigned dynamically for internal container communication:
- Portal UI: `5000` (exposed externally)
- HA Instance 1: `8123` (BASE_PORT, internal only)
- HA Instance 2: `8124` (BASE_PORT + 1, internal only)
- HA Instance 3: `8125` (BASE_PORT + 2, internal only)
- ... and so on

When an instance is deleted, its port becomes available for reuse by new instances.

**Note**: With the built-in proxy, only port 5000 needs to be exposed externally. All instances are accessed via `/proxy/<port>/` through the portal.

## Security Considerations

- The portal requires access to the Docker socket (`/var/run/docker.sock`)
- Consider running behind a reverse proxy with authentication (e.g., Cloudflare tunnel)
- **Admin password is required** for delete and reset operations - store securely (e.g., in Unraid environment variables)
- Admin password provides elevated access for managing all instances
- Limit network access to trusted networks only
- **Network Isolation**: Instances are isolated from host LAN but have internet access
- **Proxy Security**: The proxy validates that requested ports belong to actual instances before forwarding
- **Cloudflare Tunnel**: Recommended for secure external access with authentication
- Instances cannot discover or access devices on the host's network

## Troubleshooting

### Container won't start
- Check that Docker socket is accessible
- Check logs: `docker logs ha-edu-portal`

### Can't create instances
- Ensure Docker socket permissions are correct
- Check available disk space
- Verify Docker can pull the Home Assistant image
- Check if ports are available (firewall rules)

### Instance not accessible
- Wait 1-2 minutes for Home Assistant to fully start
- Check the container is running: `docker ps`
- Check the proxy error message in browser (502 usually means instance is still starting)
- For debugging, you can still access instances directly via their ports if they're exposed

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
├── app.py                        # Main Flask application with proxy
├── master_configuration.yaml     # Master HA config with demo entities
├── templates/
│   └── index.html               # Web UI template
├── static/                      # Static assets (if needed)
├── Dockerfile                   # Container definition
├── docker-compose.yml           # Compose configuration
├── requirements.txt             # Python dependencies
├── test_app.py                  # Application tests
├── test_proxy.py                # Proxy functionality tests
├── test_proxy_integration.py    # Proxy integration tests
├── test_master_config.py        # Master configuration tests
└── README.md                    # This file
```

## License

This project is open source and available for educational use.

## Contributing

Contributions are welcome! Please feel free to submit issues or pull requests.

## Support

For issues or questions, please open an issue on GitHub.
