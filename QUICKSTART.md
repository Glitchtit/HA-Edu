# Quick Start Guide - HA-Edu Portal

## Overview
HA-Edu is a web portal for managing multiple Home Assistant demo instances for educational purposes.

## Deployment Options

### Option 1: Docker Compose (Recommended)

1. Clone the repository:
```bash
git clone https://github.com/Glitchtit/HA-Edu.git
cd HA-Edu
```

2. Start the portal:
```bash
docker-compose up -d
```

3. Access the portal at `http://localhost:5000`

### Option 2: Unraid Docker Container

1. In Unraid, go to Docker tab and click "Add Container"
2. Configure the following settings:

**Basic Settings:**
- Name: `ha-edu-portal`
- Repository: Build from `/mnt/user/appdata/ha-edu` (after cloning repo)
- Network Type: `bridge`

**Port Mappings:**
- Container Port: `5000` → Host Port: `5000` (WebUI)
- Note: HA instance ports are assigned dynamically, no need to pre-allocate

**Volume Mappings:**
- Container Path: `/var/run/docker.sock` → Host Path: `/var/run/docker.sock`
- Container Path: `/data` → Host Path: `/mnt/user/appdata/ha-edu/data`

**Environment Variables:**
- `BASE_PORT`: `8123` (starting port for dynamic assignment)
- `HA_IMAGE`: `ghcr.io/home-assistant/home-assistant:stable`
- `ADMIN_PASSWORD`: (optional) For admin reset functionality

3. Click "Apply" and start the container
4. Access via WebUI icon or `http://[Unraid-IP]:5000`

### Option 3: Manual Docker Build

```bash
# Build the image
docker build -t ha-edu-portal .

# Create data directory
mkdir -p ./data

# Run the container
docker run -d \
  --name ha-edu-portal \
  -p 5000:5000 \
  -v /var/run/docker.sock:/var/run/docker.sock \
  -v $(pwd)/data:/data \
  -e BASE_PORT=8123 \
  -e HA_IMAGE=ghcr.io/home-assistant/home-assistant:stable \
  ha-edu-portal
```

## Usage

### Creating a New Instance

1. Click the **"+ Add New Instance"** button
2. Enter a **Server Name** (e.g., "Student-Lab-01")
3. Enter a **Password** for the instance
4. Click **"Create"**
5. Wait 1-2 minutes for Home Assistant to start
6. Click **"Access"** to open the instance

### Accessing an Instance

- Click the **"Access"** button on any instance card
- The instance will open in a new browser tab
- Use the password you set during creation

### Deleting an Instance

1. Click the **"Delete"** button on the instance card
2. Confirm the deletion
3. The instance and its data will be removed

### Using Teacher Access (Optional)

If the teacher access feature is enabled (by setting `TEACHER_USERNAME` and `TEACHER_PASSWORD`):

1. **Wait for students to complete onboarding**: Students must go through the Home Assistant onboarding wizard and create their account first
2. Click the **"👨‍🏫 Teacher"** button on the instance card
3. Enter the **Admin Password**
4. Confirm to add teacher access
5. The teacher can now log in to that instance using the configured teacher credentials
6. A **"👨‍🏫 Teacher Access"** badge will appear on the instance card

**Benefits:**
- Teachers can monitor student progress without disrupting their learning
- Students retain full admin access to their instances
- Preserves the educational value of students doing onboarding themselves
- Teacher account is a secondary admin, not a replacement

## Port Management

The portal dynamically assigns ports starting from BASE_PORT (default: 8123):
- **Portal UI**: Port 5000
- **Instance 1**: Port 8123
- **Instance 2**: Port 8124
- **Instance 3**: Port 8125
- **... and so on**

When an instance is deleted, its port becomes available for reuse by new instances.

## Network Isolation

- **Internet Access**: ✅ Instances can access the internet
- **LAN Access**: ❌ Instances are isolated from host LAN
- **Device Discovery**: ❌ Cannot discover devices on main network
- **External Access**: Via Cloudflare tunnel (e.g., edu.wredlund.fi)

## Firewall Configuration

Ensure the following ports are accessible:
- Port 5000 (Portal UI)
- Ports starting from 8123 onwards (dynamically assigned HA instances)
- For Cloudflare tunnel: Only port 5000 needs to be accessible to cloudflared

## Troubleshooting

### Container won't start
- Verify Docker socket is accessible: `ls -l /var/run/docker.sock`
- Check Docker daemon is running: `docker ps`
- Review logs: `docker logs ha-edu-portal`

### Can't create instances
- Check Docker socket permissions
- Verify available disk space: `df -h`
- Ensure Home Assistant image can be pulled: `docker pull ghcr.io/home-assistant/home-assistant:stable`

### Instance not accessible after creation
- Wait 1-2 minutes for Home Assistant to fully start
- Check if container is running: `docker ps | grep ha-edu`
- Verify firewall allows the port
- Check instance port assignment in the portal UI

## Configuration Options

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `BASE_PORT` | `8123` | Starting port for dynamic instance assignment |
| `DATA_FILE` | `/data/instances.json` | Instance metadata storage path |
| `HA_IMAGE` | `ghcr.io/home-assistant/home-assistant:stable` | Home Assistant image |
| `ADMIN_PASSWORD` | (empty) | Optional admin password for reset functionality |
| `TEACHER_USERNAME` | (empty) | Optional username for teacher admin account |
| `TEACHER_PASSWORD` | (empty) | Optional password for teacher admin account |

### Changing Configuration

1. Stop the portal: `docker-compose down` or `docker stop ha-edu-portal`
2. Edit `docker-compose.yml` or update environment variables
3. Start the portal: `docker-compose up -d` or `docker start ha-edu-portal`

## Best Practices

1. **Port Management**: Ports are dynamically assigned and reused when instances are deleted
2. **Backups**: Backup `/data/instances.json` to preserve instance metadata
3. **Monitoring**: Check Docker logs regularly for issues
4. **Updates**: Keep the Home Assistant image updated
5. **Security**: Use Cloudflare tunnel with authentication for external access
6. **Network Isolation**: Instances are isolated from LAN but have internet access

## Support

For issues or questions:
- Check the [README.md](README.md) for detailed documentation
- Review Docker logs: `docker logs ha-edu-portal`
- Open an issue on GitHub

## License

This project is open source and available for educational use.
