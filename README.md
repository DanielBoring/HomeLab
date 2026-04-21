# HomeLab

A collection of self-hosted services and infrastructure configurations for my personal home lab environment. This repository contains Docker Compose configurations, deployment scripts, and documentation for various services.

## Overview

This repository serves as the central configuration hub for my home lab infrastructure, emphasizing:
- **Infrastructure as Code**: All service configurations are version-controlled
- **Security Best Practices**: Secrets management using environment variables
- **Docker-First Approach**: Containerized services for easy deployment and management
- **Documentation**: Comprehensive setup guides for each service

## Services

### Traefik
Reverse proxy and TLS termination layer. Creates the shared `traefik` Docker network used by services that need to be exposed via domain names.

- **Location**: [`/traefik`](traefik/)
- **Access**: `10.0.5.5` (macvlan — dedicated LAN IP), dashboard at `https://<TRAEFIK_DOMAIN>/dashboard/`
- **Documentation**: See [traefik/README.md](traefik/README.md)
- **Deploy first** — other services depend on the `traefik` network

### Homepage
Self-hosted dashboard with service tiles, API integrations, and Docker auto-discovery.

- **Location**: [`/homepage`](homepage/)
- **Access**: `https://homepage.virtuallyboring.com` (via Traefik)
- **Documentation**: See [homepage/README.md](homepage/README.md)

### Arcane
Self-hosted application management platform for homelabs.

- **Location**: [`/arcane`](arcane/)
- **Port**: 3552
- **Documentation**: See [arcane/README.md](arcane/README.md)

### Termix
Web-based terminal emulator for remote system access.

- **Location**: [`/termix`](termix/)
- **Port**: 8090
- **Documentation**: See [termix/README.md](termix/README.md)

### Monitoring Stack
Prometheus + Grafana for metrics collection and visualization.

- **Location**: [`/monitoring-stack`](monitoring-stack/)
- **Ports**: 9090 (Prometheus), 3000 (Grafana)
- **Network**: Creates the shared `monitoring` Docker network used by dependent services

### Unpoller
Polls UniFi network controller and exposes metrics to Prometheus.

- **Location**: [`/unpoller`](unpoller/)
- **Ports**: 9130 (Prometheus scrape endpoint), 37288 (web UI — disabled by default)
- **Requires**: `monitoring-stack` deployed first (joins the `monitoring` network)
- **Controller**: UniFi OS device at `https://10.0.1.1`

### Prometheus PVE Exporter
Exports Proxmox VE cluster and node metrics to Prometheus.

- **Location**: [`/prometheus-pve-exporter`](prometheus-pve-exporter/)
- **Port**: 9221 (Prometheus scrape endpoint)
- **Requires**: `monitoring-stack` deployed first (joins the `monitoring` network)
- **Documentation**: See [prometheus-pve-exporter/README.md](prometheus-pve-exporter/README.md)

### Semaphore
Self-hosted UI for running Ansible, Terraform, and OpenTofu playbooks with scheduling and access control.

- **Location**: [`/semaphore`](semaphore/)
- **Port**: 3003
- **Documentation**: See [semaphore/README.md](semaphore/README.md)

### Uptime Kuma
Self-hosted uptime monitoring for services via HTTP/HTTPS, TCP, DNS, and more.

- **Location**: [`/uptime-kuma`](uptime-kuma/)
- **Access**: `https://uptime-kuma.virtuallyboring.com` (via Traefik)
- **Documentation**: See [uptime-kuma/README.md](uptime-kuma/README.md)

### Tailscale
Tailscale node that advertises subnet routes and acts as a VPN exit node for the tailnet.

- **Location**: [`/tailscale`](tailscale/)
- **Requires**: Auth key from the Tailscale admin console
- **Documentation**: See [tailscale/README.md](tailscale/README.md)

### Calibre
Calibre desktop GUI (KasmVNC) and Calibre-Web for ebook library management and browser-based reading.

- **Location**: [`/calibre`](calibre/)
- **Ports**: 8085/8086 (Calibre desktop GUI), 8081 (Calibre content server), 8083 (Calibre-Web)
- **Documentation**: See [calibre/README.md](calibre/README.md)

### Changedetection.io
Website change detection and monitoring with full JavaScript rendering via Playwright/Chrome.

- **Location**: [`/changedetection`](changedetection/)
- **Port**: 5000
- **Documentation**: See [changedetection/README.md](changedetection/README.md)

### Dozzle
Real-time Docker log viewer. Streams container logs to a browser UI — stateless, no log storage.

- **Location**: [`/dozzle`](dozzle/)
- **Access**: `https://<DOZZLE_DOMAIN>` (via Traefik)
- **Documentation**: See [dozzle/README.md](dozzle/README.md)

### Loki
Log aggregation stack (Loki + Promtail). Promtail ships container and systemd journal logs into Loki; Grafana is the query UI.

- **Location**: [`/loki`](loki/)
- **Port**: 3100 (Loki ingest — internal only)
- **Requires**: `monitoring-stack` deployed first (Grafana datasource)
- **Documentation**: See [loki/README.md](loki/README.md)

### Nextcloud
Self-hosted file sync and collaboration platform.

- **Location**: [`/nextcloud`](nextcloud/)
- **Access**: `https://<NEXTCLOUD_DOMAIN>` (via Traefik)
- **Documentation**: See [nextcloud/README.md](nextcloud/README.md)

### Paperless-NGX
Document management system — scan, index, and archive documents with OCR and full-text search.

- **Location**: [`/paperless-ngx`](paperless-ngx/)
- **Access**: `https://<PAPERLESS_DOMAIN>` (via Traefik)
- **Documentation**: See [paperless-ngx/readme.md](paperless-ngx/readme.md)

### Open WebUI
Web UI for interacting with self-hosted LLM models via Ollama.

- **Location**: [`/openwebui`](openwebui/)
- **Access**: `https://<OPENWEBUI_DOMAIN>` (via Traefik)
- **Ollama host**: Remote instance at `PwnBot.virtuallyboring.com:11434`
- **Documentation**: See [openwebui/README.md](openwebui/README.md)

## Quick Start

### Prerequisites

- Docker Engine 20.10+
- Docker Compose V2
- Linux host with sufficient storage for container volumes

### General Deployment Pattern

Each service follows a consistent structure:

```bash
# Navigate to service directory
cd <service-name>

# Copy environment template (if exists)
cp .env.example .env  # Only for services requiring secrets

# Edit configuration
nano .env  # Customize as needed

# Start the service
docker compose up -d

# Check status
docker compose ps
docker compose logs -f
```

## Repository Structure

```
HomeLab/
├── traefik/             # Reverse proxy and TLS termination
│   ├── compose.yaml     # Docker Compose configuration
│   ├── traefik.yml      # Traefik static configuration
│   ├── .env.example     # Environment template
│   └── README.md        # Service documentation
├── homepage/            # Self-hosted dashboard
│   ├── compose.yaml     # Docker Compose configuration
│   ├── .env.example     # Environment template
│   └── README.md        # Service documentation
├── arcane/              # Application management platform
│   ├── compose.yaml     # Docker Compose configuration
│   ├── .env.example     # Environment template
│   └── README.md        # Service documentation
├── termix/              # Web-based terminal emulator
│   ├── compose.yaml     # Docker Compose configuration
│   └── README.md        # Service documentation
├── monitoring-stack/    # Prometheus + Grafana
│   ├── compose.yaml     # Docker Compose configuration
│   ├── prometheus.yml   # Prometheus scrape config
│   ├── .env.example     # Environment template
│   └── README.md        # Service documentation
├── unpoller/            # UniFi metrics exporter
│   ├── compose.yaml     # Docker Compose configuration
│   ├── .env.example     # Environment template
│   └── README.md        # Service documentation
├── semaphore/           # Ansible/Terraform UI
│   ├── compose.yaml     # Docker Compose configuration
│   ├── .env.example     # Environment template
│   └── README.md        # Service documentation
├── uptime-kuma/         # Uptime monitoring
│   ├── compose.yaml     # Docker Compose configuration
│   └── README.md        # Service documentation
├── tailscale/           # Tailscale VPN node
│   ├── compose.yaml     # Docker Compose configuration
│   ├── .env.example     # Environment template
│   └── README.md        # Service documentation
├── calibre/             # Calibre + Calibre-Web ebook manager
│   ├── compose.yaml     # Docker Compose configuration
│   └── README.md        # Service documentation
├── changedetection/     # Website change detection and monitoring
│   ├── compose.yaml     # Docker Compose configuration
│   └── README.md        # Service documentation
├── dozzle/              # Real-time Docker log viewer
│   ├── compose.yaml     # Docker Compose configuration
│   ├── .env.example     # Environment template
│   └── README.md        # Service documentation
├── loki/                # Log aggregation (Loki + Promtail)
│   ├── compose.yaml     # Docker Compose configuration
│   ├── loki-config.yaml
│   ├── promtail-config.yaml
│   ├── .env.example     # Environment template
│   └── README.md        # Service documentation
├── nextcloud/           # Self-hosted file sync and collaboration
│   ├── compose.yaml     # Docker Compose configuration
│   ├── .env.example     # Environment template
│   └── README.md        # Service documentation
├── paperless-ngx/       # Document management with OCR
│   ├── compose.yaml     # Docker Compose configuration
│   ├── .env.example     # Environment template
│   └── readme.md        # Service documentation
├── openwebui/           # Web UI for Ollama LLM models
│   ├── compose.yaml     # Docker Compose configuration
│   ├── .env.example     # Environment template
│   └── README.md        # Service documentation
├── prometheus-pve-exporter/  # Proxmox VE metrics exporter
│   ├── compose.yaml     # Docker Compose configuration
│   ├── .env.example     # Environment template
│   └── README.md        # Service documentation
├── .gitignore           # Git ignore patterns (protects secrets)
├── LICENSE              # MIT License
└── README.md            # This file
```

## Security

### Secrets Management

This repository follows security best practices:

- **Environment Variables**: Secrets are stored in `.env` files (gitignored)
- **Templates**: `.env.example` files provide configuration templates
- **Never Committed**: Actual secrets are never committed to version control
- **Unique Per Service**: Each service manages its own secrets

### Protected Files

The following files are automatically excluded from version control:
- `.env`, `.env.local`, `.env.*.local` - Environment files with secrets
- `compose.override.yaml` - Docker override files that may contain secrets
- `*.log` - Log files that might contain sensitive information
- IDE and OS-specific files

### Best Practices

1. **Always check before committing**:
   ```bash
   git status  # Verify no .env files are staged
   ```

2. **Generate strong secrets**:
   ```bash
   openssl rand -hex 32  # For encryption keys
   openssl rand -base64 32  # For passwords
   ```

3. **Rotate secrets regularly** - Change passwords and keys quarterly

4. **Backup securely** - Encrypt backups of `.env` files:
   ```bash
   gpg --symmetric --cipher-algo AES256 .env
   ```

## Storage Configuration

Services are configured to use persistent storage at `/mnt/SSD/Containers/`:

- **Traefik Certs**: `/mnt/SSD/Containers/traefik/certs`
- **Homepage Config**: `/mnt/SSD/Containers/homepage`
- **Arcane Data**: `/mnt/SSD/Containers/arcane`
- **Arcane Database**: `/mnt/SSD/Containers/arcane-postgres`
- **Termix Data**: `/mnt/SSD/Containers/termix`
- **Prometheus Data**: `/mnt/SSD/Containers/prometheus`
- **Grafana Data**: `/mnt/SSD/Containers/grafana`
- **Semaphore Data**: `/mnt/SSD/Containers/semaphore/data`
- **Semaphore Config**: `/mnt/SSD/Containers/semaphore/config`
- **Semaphore Tmp**: `/mnt/SSD/Containers/semaphore/tmp`
- **Uptime Kuma Data**: `/mnt/SSD/Containers/uptime-kuma`
- **Tailscale State**: `/mnt/SSD/Containers/tailscale`
- **Calibre Config**: `/mnt/SSD/Containers/calibre`
- **Calibre-Web Config**: `/mnt/SSD/Containers/calibre-web`
- **Changedetection Data**: `/mnt/SSD/Containers/changedetection`

Ensure this path exists and has appropriate permissions before deploying services.

## Deployment

Services are deployed and managed via **Portainer GitOps**:

1. Push changes to this repository on GitHub
2. Portainer polls GitHub every 5 minutes and automatically pulls changes and redeploys affected stacks
3. For immediate deployment (e.g. during troubleshooting), trigger a manual **Force Update** in Portainer

Environment variables are stored per-stack in Portainer — not in `.env` files on the host.

## Maintenance

### Backing Up Data

```bash
cd <service-directory>
docker compose down
tar -czf backup-$(date +%Y%m%d).tar.gz /mnt/SSD/Containers/<service-name>
docker compose up -d
```

### Monitoring

```bash
# View all running containers
docker ps

# Check specific service logs
cd <service-directory>
docker compose logs -f

# View resource usage
docker stats
```

## Troubleshooting

### Common Issues

**Port conflicts**:
```bash
# Check what's using a port
sudo lsof -i :<port-number>
# or
sudo netstat -tulpn | grep <port-number>
```

**Permission errors**:
```bash
# Check current user/group IDs
id -u  # User ID
id -g  # Group ID

# Update PUID/PGID in .env files accordingly
```

**Container won't start**:
```bash
# View detailed logs
docker compose logs <service-name>

# Verify configuration
docker compose config

# Check for missing environment variables
grep -v '^#' .env | grep -v '^$'
```

## Resources

- [Docker Documentation](https://docs.docker.com/)
- [Docker Compose Documentation](https://docs.docker.com/compose/)
- [OWASP Secrets Management](https://cheatsheetseries.owasp.org/cheatsheets/Secrets_Management_Cheat_Sheet.html)

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Author

Daniel Boring

---

**Note**: This repository contains configuration files and documentation. Actual secrets and sensitive data are stored locally and never committed to version control.
