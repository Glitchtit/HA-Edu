# HA-Edu

A web-based portal for managing multiple Home Assistant demo instances in educational settings. Designed for classrooms and workshops where each student needs an isolated Home Assistant environment to learn with.

## Features

- **One-click instance creation** -- students create their own Home Assistant instance from a simple web interface
- **Role-based access control** -- admin privileges are derived from the Home Assistant Owner role when running as an add-on, or from a local user/password system in standalone mode
- **Teacher access** -- optionally inject a secondary admin account into student instances so instructors can monitor progress without disrupting student work
- **Instance lifecycle management** -- create, delete, reset, restart, lock/unlock, start-all, stop-all, and delete-all operations
- **Built-in reverse proxy** -- all instance traffic is routed through a single endpoint; individual container ports do not need to be exposed
- **Dynamic port assignment** -- ports are allocated automatically starting from a configurable base port and reused when instances are deleted
- **Network isolation** -- instances run in a bridge network with internet access but no visibility into the host LAN
- **Interaction logging with configurable retention** -- all user and admin actions are logged; logs are automatically pruned after a configurable number of days (default 90) for GDPR compliance
- **Dark mode support** -- the interface adapts to the browser's preferred color scheme
- **Responsive design** -- works on desktops, tablets, and phones
- **WebSocket proxying** -- the built-in proxy forwards WebSocket connections so the Home Assistant frontend works without modification

## Installation

### Home Assistant Add-on (recommended)

The portal runs as a native Home Assistant add-on and appears in the sidebar.

1. In Home Assistant, navigate to **Settings > Add-ons > Add-on Store**.
2. Open the three-dot menu in the top-right corner and select **Repositories**.
3. Add the repository URL:
   ```
   https://github.com/Glitchtit/HA-Edu
   ```
4. Locate the **HA-Edu** add-on in the store and click **Install**.
5. Open the **Configuration** tab to adjust options (HA image, base port, max instances, etc.).
6. Start the add-on. A new **HA-Edu** entry will appear in the sidebar.

When running as an add-on, authentication is handled automatically by Home Assistant Ingress. Each Home Assistant user receives a dedicated app account on first access. Users whose HA account has the **Owner** role are granted admin privileges in the portal.

### Standalone Docker

#### Prerequisites

- Docker and Docker Compose
- Access to the Docker socket

#### Docker Compose

```bash
git clone https://github.com/Glitchtit/HA-Edu.git
cd HA-Edu
docker-compose up -d
```

The portal will be available at `http://localhost:5000`.

#### Manual Docker Build

```bash
docker build -t ha-edu-portal .

docker run -d \
  --name ha-edu-portal \
  -p 5000:5000 \
  -v /var/run/docker.sock:/var/run/docker.sock \
  -v $(pwd)/data:/data \
  -e BASE_PORT=8124 \
  ha-edu-portal
```

In standalone mode the portal provides its own login and registration system. The first registered user is automatically assigned the admin role.

## Usage

### Creating an instance

1. Click **+ Add New Instance**.
2. Enter a server name (for example, `Student-Lab-01`).
3. Click **Create**.
4. Wait one to two minutes for the Home Assistant container to start.
5. Click **Access** to open the instance.

Each new instance is provisioned with a master configuration that enables demo mode and a set of sample entities (lights, climate, weather, camera, device trackers, and input buttons).

### Admin operations

Admin users have access to additional controls on each instance card:

- **Delete** -- remove the instance and its data.
- **Reset** -- wipe all configuration and restore the instance to its initial demo state.
- **Restart** -- restart the underlying container.
- **Lock / Unlock** -- prevent or allow non-admin users from accessing the instance.

Bulk actions available to admins include **Start All**, **Stop All**, and **Delete All**.

### Teacher access

The teacher access feature lets an instructor add a secondary admin account to a student's Home Assistant instance.

1. Configure teacher credentials in the portal settings (admin-only).
2. Wait for the student to complete the Home Assistant onboarding wizard.
3. Click the **Teacher** button on the instance card and confirm.
4. The instructor can now log in to that instance with the configured teacher credentials.

A **Teacher Access** badge appears on the instance card once the account has been added. The student's own account and data are not affected.

## Configuration

### Add-on options

When running as a Home Assistant add-on, options are set through the add-on **Configuration** tab.

| Option | Default | Description |
|--------|---------|-------------|
| `BASE_PORT` | `8124` | Starting port number for instance containers |
| `HA_IMAGE` | `ghcr.io/home-assistant/home-assistant:stable` | Docker image used for new instances |
| `LOG_RETENTION_DAYS` | `90` | Days to retain interaction logs (0 = unlimited) |
| `DOCKER_HOST_IP` | `172.30.32.1` | IP used by the portal container to reach instance containers |
| `MAX_INSTANCES` | `0` | Maximum instances a non-admin user may create (0 = unlimited) |
| `ONBOARDING_CACHE_TTL` | `60` | Seconds to cache onboarding status checks |
| `SECRET_KEY` | (auto-generated) | Flask session secret; generated and persisted automatically if not set |

### Standalone environment variables

For standalone Docker deployments, configuration is provided through environment variables. See `.env.example` for a full reference. Key variables include:

| Variable | Default | Description |
|----------|---------|-------------|
| `BASE_PORT` | `8124` | Starting port number for instance containers |
| `DATA_FILE` | `/data/instances.json` | Path to the instance metadata file |
| `LOG_DIR` | `/logs` | Directory for interaction logs |
| `LOG_RETENTION_DAYS` | `90` | Days to retain interaction logs (0 = unlimited) |
| `HA_IMAGE` | `ghcr.io/home-assistant/home-assistant:stable` | Docker image used for new instances |
| `MAX_INSTANCES` | `0` | Maximum instances a non-admin user may create (0 = unlimited) |
| `ONBOARDING_CACHE_TTL` | `60` | Seconds to cache onboarding status checks |
| `DOCKER_HOST_IP` | `host.docker.internal` | IP/hostname to reach instance containers from the portal container |
| `SECRET_KEY` | (auto-generated) | Flask session secret; generated and persisted automatically if not set |

## Architecture

The portal is built with:

- **Flask** -- serves the web UI and REST API
- **Gunicorn with gevent workers** -- handles concurrent requests and WebSocket connections
- **Docker SDK for Python** -- creates and manages Home Assistant containers
- **Built-in reverse proxy** -- forwards HTTP and WebSocket traffic to instance containers
- **JSON file storage** -- persists instance metadata and portal settings

Each Home Assistant instance runs in its own Docker container with a dedicated volume. Instances are placed on a bridge network that provides internet access through NAT but prevents communication with the host LAN. All instance traffic is routed through the portal's reverse proxy, so only a single port needs to be exposed.

## Repository Layout

```
HA-Edu/
  repository.yaml               # Home Assistant add-on repository metadata
  ha-edu/                       # Home Assistant add-on package
    config.yaml                 # Add-on manifest (ingress, options, etc.)
    Dockerfile                  # Add-on container build
    build.yaml                  # Multi-architecture build configuration
    run.sh                      # Add-on entrypoint script
    CHANGELOG.md                # Add-on version history
    app.py                      # Flask application
    wsgi.py                     # WSGI entry point
    interaction_logger.py       # Audit logging module
    requirements.txt            # Python dependencies
    master_configuration.yaml   # Default HA configuration for new instances
    templates/                  # HTML templates
  app.py                        # Flask application (standalone deployment)
  Dockerfile                    # Standalone container build
  docker-compose.yml            # Standalone Compose file
  requirements.txt              # Python dependencies (standalone)
  test_*.py                     # Test suite
  README.md                     # This file
```

## Development

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python app.py
```

## Troubleshooting

**Container will not start**
- Verify that the Docker socket is accessible.
- Review container logs: `docker logs ha-edu-portal`.

**Cannot create instances**
- Check Docker socket permissions.
- Confirm that sufficient disk space is available.
- Ensure that the Home Assistant image can be pulled.

**Instance not accessible after creation**
- Allow one to two minutes for Home Assistant to finish starting.
- Verify that the container is running: `docker ps`.
- A 502 error from the proxy typically indicates the instance is still initializing.

## License

This project is open source and available for educational use.

## Contributing

Contributions are welcome. Please open an issue or submit a pull request on GitHub.
