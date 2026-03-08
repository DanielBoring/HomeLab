# Termix Docker Compose Setup

This directory contains the Docker Compose configuration for running [Termix](https://github.com/lukegus/termix), a modern web-based terminal emulator for accessing your home lab systems from anywhere.

## Overview

Termix provides a secure, browser-based terminal interface that allows you to:
- Access your systems remotely without SSH port exposure
- Manage multiple terminal sessions in tabs
- Access your home lab through a web browser
- Maintain persistent connections and session history

## Quick Start

### 1. Ensure storage directory exists

The configuration uses a bind mount to persist terminal data:

```bash
# Create the data directory if it doesn't exist
sudo mkdir -p /mnt/SSD/Containers/termix

# Set appropriate permissions (adjust UID/GID as needed)
sudo chown -R $USER:$USER /mnt/SSD/Containers/termix
```

### 2. Start the service

```bash
# From the termix directory
docker compose up -d
```

### 3. Verify it's running

```bash
# Check container status
docker compose ps

# View logs
docker compose logs -f termix

# Access the application
# Open http://localhost:8090 in your browser
```

## Configuration

### Ports

| Host Port | Container Port | Description |
|-----------|----------------|-------------|
| 8090 | 8080 | Web interface for Termix |

**Note**: The service is exposed on port 8090 on your host to avoid conflicts with other services that commonly use port 8080.

### Volumes

Data persistence is configured using a bind mount:

| Local Path | Container Path | Purpose |
|------------|----------------|---------|
| `/mnt/SSD/Containers/termix` | `/app/data` | Terminal session data, history, and configuration |

### Environment Variables

| Variable | Value | Description |
|----------|-------|-------------|
| `PORT` | `8080` | Internal port Termix listens on inside the container |

### Network

The service uses a dedicated bridge network (`termix-network`) for network isolation and can communicate with other services on the same Docker network if needed.

## Accessing Termix

### Local Access

Once the container is running, access Termix at:

```
http://localhost:8090
```

### Remote Access

For secure remote access, consider one of these options:

#### Option 1: Reverse Proxy (Recommended)

Use a reverse proxy like Nginx, Traefik, or Caddy with HTTPS:

```yaml
# Example Traefik labels (add to compose.yaml)
labels:
  - "traefik.enable=true"
  - "traefik.http.routers.termix.rule=Host(`termix.yourdomain.com`)"
  - "traefik.http.routers.termix.entrypoints=websecure"
  - "traefik.http.routers.termix.tls.certresolver=letsencrypt"
  - "traefik.http.services.termix.loadbalancer.server.port=8080"
```

#### Option 2: VPN Access

Access through a VPN like WireGuard or Tailscale to keep the service on your private network without exposing it to the internet.

#### Option 3: SSH Tunnel

Create an SSH tunnel for secure access:

```bash
ssh -L 8090:localhost:8090 user@your-homelab-server
```

Then access at `http://localhost:8090` on your local machine.

## Usage

### Creating Terminal Sessions

1. Open Termix in your browser
2. Click "New Session" or use the keyboard shortcut
3. Configure connection settings (host, port, credentials)
4. Connect to your target system

### Managing Sessions

- **Multiple Tabs**: Open multiple terminal sessions in browser tabs
- **Session Persistence**: Sessions are saved and can be restored
- **Copy/Paste**: Use browser copy/paste functionality
- **Full Terminal Features**: Supports colors, cursor movement, and most terminal features

## Maintenance

### Viewing Logs

Check application logs for troubleshooting:

```bash
# Follow logs in real-time
docker compose logs -f termix

# View last 100 lines
docker compose logs --tail=100 termix

# View logs from last hour
docker compose logs --since 1h termix
```

### Updating Termix

To update to the latest version:

```bash
# Pull the latest image
docker compose pull

# Recreate container with new image
docker compose up -d

# Check logs for any issues
docker compose logs -f termix
```

### Backing Up Data

Your terminal data is stored in `/mnt/SSD/Containers/termix`:

```bash
# Stop the container
docker compose down

# Backup data
tar -czf termix-backup-$(date +%Y%m%d).tar.gz /mnt/SSD/Containers/termix

# Restart the container
docker compose up -d
```

### Restoring from Backup

```bash
# Stop the container
docker compose down

# Restore data
tar -xzf termix-backup-YYYYMMDD.tar.gz -C /

# Verify ownership and permissions
sudo chown -R $USER:$USER /mnt/SSD/Containers/termix

# Restart the container
docker compose up -d
```

## Troubleshooting

### Container Won't Start

Check if the data directory exists and has correct permissions:

```bash
# Verify directory exists
ls -la /mnt/SSD/Containers/termix

# Fix permissions if needed
sudo chown -R $USER:$USER /mnt/SSD/Containers/termix
```

### Port Already in Use

If port 8090 is already in use:

```bash
# Check what's using the port
sudo lsof -i :8090
# or
sudo netstat -tulpn | grep 8090

# Either stop the conflicting service or change the port in compose.yaml:
# ports:
#   - "8091:8080"  # Use a different host port
```

### Cannot Connect to Terminal Session

1. **Check network connectivity**:
   ```bash
   # From inside the container
   docker compose exec termix ping <target-host>
   ```

2. **Verify firewall rules** on target systems allow connections from the Termix container

3. **Check logs** for connection errors:
   ```bash
   docker compose logs -f termix
   ```

### Permission Denied Errors

If you encounter permission issues with the data directory:

```bash
# Check current permissions
ls -la /mnt/SSD/Containers/termix

# Fix ownership
sudo chown -R $USER:$USER /mnt/SSD/Containers/termix

# Ensure proper permissions
chmod -R 755 /mnt/SSD/Containers/termix
```

### Browser Compatibility Issues

Termix works best with modern browsers:
- **Recommended**: Chrome 90+, Firefox 88+, Safari 14+, Edge 90+
- Clear browser cache if experiencing display issues
- Disable browser extensions that might interfere with terminal rendering

## Security Considerations

### Authentication

Termix itself may not include authentication. To secure access:

1. **Use a reverse proxy** with authentication (Nginx, Caddy, Traefik)
2. **Deploy behind a VPN** (WireGuard, Tailscale, OpenVPN)
3. **Use firewall rules** to restrict access by IP
4. **Never expose directly** to the public internet without authentication

### Network Security

- The container runs on an isolated Docker network
- Only port 8090 is exposed to the host
- Use HTTPS when accessing remotely (via reverse proxy)
- Consider implementing fail2ban for brute-force protection

### Session Data

- Terminal session data is stored in `/mnt/SSD/Containers/termix`
- Ensure this directory has restrictive permissions (700 or 755)
- Regular backups should be encrypted if they contain sensitive data
- Consider using encrypted storage for the data directory

## Advanced Configuration

### Custom Network Configuration

To connect Termix to other Docker networks:

```yaml
networks:
  termix-network:
    driver: bridge
  other-network:
    external: true

services:
  termix:
    networks:
      - termix-network
      - other-network
```

### Resource Limits

To limit resource usage:

```yaml
services:
  termix:
    deploy:
      resources:
        limits:
          cpus: '1.0'
          memory: 512M
        reservations:
          cpus: '0.5'
          memory: 256M
```

### Custom Environment Variables

Add additional environment variables as needed:

```yaml
environment:
  PORT: "8080"
  LOG_LEVEL: "info"  # Example: adjust logging verbosity
  # Add other variables as supported by Termix
```

## Integration with Other Services

### Using with SSH Bastion

Termix can serve as a web-based SSH bastion:

1. Configure SSH keys inside the Termix container
2. Access target systems via SSH through the web interface
3. Maintain multiple persistent SSH sessions

### Connecting to Docker Networks

To access other containerized services:

```yaml
networks:
  termix-network:
    driver: bridge
  homelab-network:
    external: true
    name: homelab-network

services:
  termix:
    networks:
      - termix-network
      - homelab-network
```

## Upgrading

### Minor Updates

For regular updates:

```bash
docker compose pull
docker compose up -d
```

### Major Version Updates

Check the [Termix changelog](https://github.com/lukegus/termix/releases) before major updates:

1. **Backup data** first
2. **Review breaking changes** in release notes
3. **Test in staging** if possible
4. **Update and monitor** logs carefully

## Additional Resources

- [Termix GitHub Repository](https://github.com/lukegus/termix)
- [Docker Compose Documentation](https://docs.docker.com/compose/)
- [Web-based Terminal Security Best Practices](https://owasp.org/www-community/controls/Web_Terminal_Security)

## Support

For issues with:
- **Termix application**: [GitHub Issues](https://github.com/lukegus/termix/issues)
- **This Docker Compose setup**: Check the HomeLab repository

## License

This configuration is part of the HomeLab project. See the repository LICENSE file for details.

---

**Security Notice**: Always implement proper authentication and use HTTPS when accessing Termix remotely. Never expose terminal access directly to the public internet without security measures.
