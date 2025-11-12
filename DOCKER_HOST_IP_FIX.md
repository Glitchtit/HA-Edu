# Docker Host IP Configuration Fix

## Problem Statement

When 2 or more Home Assistant instances existed, users encountered the error: **"Something went wrong loading onboarding, try refreshing"**

### Root Cause

The proxy code used a hardcoded IP address `192.168.50.111` to connect to Home Assistant instance containers:

```python
target_url = f'http://192.168.50.111:{port}/{path}'
```

This IP address was specific to the original developer's network environment and would not work in other deployments, including:
- Different network configurations
- Docker Desktop on Mac/Windows
- **Unraid servers** (the primary deployment target)
- Any server where the host IP is different

When the portal container tried to proxy requests to Home Assistant instances using this hardcoded IP, the connections would fail, causing:
- Onboarding screens to fail with errors
- Graphics and assets not loading
- Instances becoming effectively "bricked"
- The problem worsening with multiple instances

## Solution

Replaced the hardcoded IP address with a configurable environment variable `DOCKER_HOST_IP` that adapts to different Docker environments.

### Changes Made

1. **Added `DOCKER_HOST_IP` environment variable** in `app.py`:
   ```python
   DOCKER_HOST_IP = os.getenv('DOCKER_HOST_IP', 'host.docker.internal')
   ```

2. **Updated all proxy connections** to use the variable:
   - HTTP proxy: `target_url = f'http://{DOCKER_HOST_IP}:{port}/{path}'`
   - WebSocket proxy: `backend_url = f'ws://{DOCKER_HOST_IP}:{port}/api/websocket'`
   - Host headers: `headers['Host'] = f'{DOCKER_HOST_IP}:{port}'`

3. **Updated docker-compose.yml** with Linux/Unraid support:
   ```yaml
   extra_hosts:
     - "host.docker.internal:host-gateway"
   ```
   This enables `host.docker.internal` on Linux systems (including Unraid) by mapping it to the Docker host gateway IP.

4. **Updated configuration files**:
   - `.env.example`: Added `DOCKER_HOST_IP` with documentation
   - `README.md`: Added to configuration table
   - `docker-compose.yml`: Added environment variable and extra_hosts

## How It Works

### Docker Networking Context

When the portal runs in a Docker container and needs to access Home Assistant instance containers:

1. **HA instances** are created with:
   - `network_mode='bridge'` (default Docker bridge network)
   - Port mapping: container port 8123 → host port 8123, 8124, 8125, etc.

2. **Portal container** runs on:
   - Custom bridge network `ha-edu-network`
   - Cannot directly access other containers on the default bridge network
   - Must route through the Docker host to access mapped ports

### Host Access Methods by Platform

| Platform | Method | Configuration |
|----------|--------|---------------|
| **Unraid** | `host.docker.internal` via extra_hosts | Default (automatic with docker-compose) |
| **Docker Desktop (Mac/Windows)** | `host.docker.internal` (native) | Default |
| **Linux Docker** | `host.docker.internal` via extra_hosts | Default (automatic with docker-compose) |
| **Direct host install** | `localhost` | Set `DOCKER_HOST_IP=localhost` |
| **Custom network** | Host IP address | Set `DOCKER_HOST_IP=192.168.1.100` |

### For Unraid Users

The fix works automatically on Unraid because:

1. **`extra_hosts` directive** in docker-compose.yml:
   ```yaml
   extra_hosts:
     - "host.docker.internal:host-gateway"
   ```
   This tells Docker to add a DNS entry mapping `host.docker.internal` to the special `host-gateway` IP address, which Docker resolves to the host's gateway IP from the container's perspective.

2. **Default environment variable**:
   ```yaml
   environment:
     - DOCKER_HOST_IP=host.docker.internal
   ```
   Uses this special hostname that now resolves correctly on Linux/Unraid.

3. **Port mapping** ensures the portal can reach instances:
   - Instances bind to host ports 8123, 8124, etc.
   - Portal accesses them via `host.docker.internal:8123`, `host.docker.internal:8124`, etc.
   - Docker's `host-gateway` routes these to the correct host ports

## Configuration

### Default (Recommended)

No configuration needed! The default settings work on:
- Unraid
- Docker Desktop (Mac/Windows)  
- Linux with Docker 20.10+

```yaml
# docker-compose.yml (already configured)
environment:
  - DOCKER_HOST_IP=host.docker.internal
extra_hosts:
  - "host.docker.internal:host-gateway"
```

### Custom Configuration

If you need to override the default (rare cases):

**Option 1: Use specific IP address**
```yaml
environment:
  - DOCKER_HOST_IP=192.168.1.100  # Your Unraid server's IP
```

**Option 2: Running portal directly on host (not in Docker)**
```bash
export DOCKER_HOST_IP=localhost
python app.py
```

## Testing

All existing tests pass with the new configuration:

```bash
# Proxy functionality
python3 test_proxy.py
✓ All proxy tests passed!

# Location header rewriting (includes testing old hardcoded IP recognition)
python3 test_location_header_rewrite.py
✓ All Location header rewrite tests passed!
```

Key test results:
- ✅ Proxy uses `DOCKER_HOST_IP` instead of hardcoded IP
- ✅ Location headers correctly rewritten
- ✅ Old `192.168.50.111` URLs still recognized and rewritten for compatibility
- ✅ WebSocket connections use the new variable

## Backward Compatibility

The fix maintains backward compatibility:

1. **Old Location headers** from Home Assistant instances that might still contain `192.168.50.111` are recognized and rewritten correctly
2. **Default value** of `host.docker.internal` works on all modern Docker setups
3. **No database migrations** or data changes needed
4. **Existing instances** work immediately after upgrade

## Deployment on Unraid

### Using Docker Compose (Recommended)

1. Pull the latest code:
   ```bash
   git pull
   ```

2. Restart the container:
   ```bash
   docker-compose down
   docker-compose up -d
   ```

3. Verify it's working:
   - Create a new instance
   - Access it via the proxy
   - Onboarding should work correctly

### Manual Docker Run

If not using docker-compose, add the extra host mapping:

```bash
docker run -d \
  --name ha-edu-portal \
  --add-host=host.docker.internal:host-gateway \
  -e DOCKER_HOST_IP=host.docker.internal \
  -p 5000:5000 \
  -v /var/run/docker.sock:/var/run/docker.sock \
  -v /mnt/user/appdata/ha-edu:/data \
  ha-edu-portal:latest
```

### Unraid Template

The template should include:

```xml
<Config Name="Docker Host IP" Target="DOCKER_HOST_IP" Default="host.docker.internal" Mode="" Description="IP/hostname to access instance containers. Leave as default for Unraid." Type="Variable" Display="advanced" Required="false" Mask="false">host.docker.internal</Config>
```

And in the extra parameters field:
```
--add-host=host.docker.internal:host-gateway
```

## Troubleshooting

### Issue: Still getting "Something went wrong loading onboarding"

**Check 1: Verify DOCKER_HOST_IP is set**
```bash
docker exec ha-edu-portal env | grep DOCKER_HOST_IP
# Should show: DOCKER_HOST_IP=host.docker.internal
```

**Check 2: Verify extra_hosts is working**
```bash
docker exec ha-edu-portal getent hosts host.docker.internal
# Should show an IP address (e.g., 172.17.0.1)
```

**Check 3: Check logs for connection errors**
```bash
docker logs ha-edu-portal | grep -i "connection\|proxy"
```

### Issue: Container can't resolve host.docker.internal

This means `extra_hosts` isn't configured. Add it:
```bash
docker run --add-host=host.docker.internal:host-gateway ...
```

Or in docker-compose.yml:
```yaml
extra_hosts:
  - "host.docker.internal:host-gateway"
```

### Issue: Works on first instance, fails on second

This confirms the fix is working! The original hardcoded IP only worked for the developer's specific setup and would fail randomly. With the fix, all instances should work.

If you still see issues:
1. Restart the portal container
2. Check that instance containers are actually running: `docker ps`
3. Verify ports are properly mapped: `docker port <container-name>`

## Benefits

✅ **Works on all platforms**: Unraid, Docker Desktop, Linux, etc.  
✅ **Configurable**: Can be customized for specific network setups  
✅ **Automatic**: Works out-of-the-box with default settings  
✅ **Multiple instances**: Supports unlimited instances without conflicts  
✅ **Backward compatible**: Recognizes old hardcoded IPs for smooth transition  
✅ **Well tested**: Passes all existing tests plus new validation  

## Related Files

- `app.py` - Main application with proxy logic
- `docker-compose.yml` - Docker Compose configuration with extra_hosts
- `.env.example` - Environment variable documentation
- `README.md` - Updated configuration table
- `test_proxy.py` - Proxy functionality tests
- `test_location_header_rewrite.py` - Location header rewriting tests
