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

### Prometheus
Metrics collection and storage. Prometheus scrapes targets on the `monitoring` Docker network and retains data for 30 days. This stack **owns and creates** the shared `monitoring` network that Grafana, Unpoller, and pve-exporter attach to.

- **Location**: [`/prometheus`](prometheus/)
- **Access**: `https://<PROMETHEUS_DOMAIN>` (via Traefik, LAN only)
- **Deploy before Grafana, Unpoller, and pve-exporter** — it creates the `monitoring` network
- **Documentation**: See [prometheus/README.md](prometheus/README.md)

### Grafana
Dashboard and visualization layer. Connects to Prometheus (and optionally Loki) over the shared `monitoring` Docker network. The Prometheus datasource is provisioned automatically — no manual setup after first login.

- **Location**: [`/grafana`](grafana/)
- **Access**: `https://<GRAFANA_DOMAIN>` (via Traefik, LAN only)
- **Requires**: `prometheus` stack deployed first
- **Documentation**: See [grafana/README.md](grafana/README.md)

### Unpoller
Polls UniFi network controller and exposes metrics to Prometheus.

- **Location**: [`/unpoller`](unpoller/)
- **Ports**: 9130 (Prometheus scrape endpoint), 37288 (web UI — disabled by default)
- **Requires**: `prometheus` stack deployed first (joins the `monitoring` network)
- **Controller**: UniFi OS device at `https://<UNIFI_CONTROLLER_IP>`

### Prometheus PVE Exporter
Exports Proxmox VE cluster and node metrics to Prometheus.

- **Location**: [`/prometheus-pve-exporter`](prometheus-pve-exporter/)
- **Port**: 9221 (Prometheus scrape endpoint)
- **Requires**: `prometheus` stack deployed first (joins the `monitoring` network)
- **Documentation**: See [prometheus-pve-exporter/README.md](prometheus-pve-exporter/README.md)

### Semaphore
Self-hosted UI for running Ansible, Terraform, and OpenTofu playbooks with scheduling and access control.

- **Location**: [`/semaphore`](semaphore/)
- **Port**: 3003
- **Documentation**: See [semaphore/README.md](semaphore/README.md)

### Uptime Kuma
Self-hosted uptime monitoring for services via HTTP/HTTPS, TCP, DNS, and more.

- **Location**: [`/uptime-kuma`](uptime-kuma/)
- **Access**: `https://<UPTIME_KUMA_DOMAIN>` (via Traefik)
- **Documentation**: See [uptime-kuma/README.md](uptime-kuma/README.md)

### Unbound
Validating, recursive, caching DNS resolver. Resolves queries by walking the DNS tree from root servers directly — no third-party DNS provider ever sees your queries. Used as the upstream recursive resolver for Pi-hole, replacing forwarders like 8.8.8.8 with a fully self-hosted DNS chain.

- **Location**: [`/unbound`](unbound/)
- **Port**: 5335 (UDP+TCP — DNS only, no web UI)
- **Documentation**: See [unbound/README.md](unbound/README.md)

### Home Assistant
Open-source home automation platform. Connects to thousands of devices and services — lights, sensors, locks, cameras, media players — and runs automations entirely locally without cloud dependency.

- **Location**: [`/homeassistant`](homeassistant/)
- **Access**: `https://<HOMEASSISTANT_DOMAIN>` (via Traefik) and `http://<host-ip>:8123` (direct, for companion app)
- **Documentation**: See [homeassistant/README.md](homeassistant/README.md)

### What's Up Docker (WUD)
Watches running containers and notifies you when a newer image is available. Passive by default — it won't touch your containers; it sends Discord notifications and shows a dashboard of what's outdated and by how much.

- **Location**: [`/wud`](wud/)
- **Access**: `https://<WUD_DOMAIN>` (via Traefik, LAN only)
- **Documentation**: See [wud/README.md](wud/README.md)

### phpIPAM
Open-source IP address management tool. Tracks subnet allocations, individual IP assignments, VLANs, VRFs, and devices — a searchable source of truth for network addressing. Lighter-weight than NetBox and purpose-built for IP management.

- **Location**: [`/phpipam`](phpipam/)
- **Access**: `https://<PHPIPAM_DOMAIN>` (via Traefik, LAN only)
- **Port**: 8030 (direct access)
- **Documentation**: See [phpipam/README.md](phpipam/README.md)

### PegaProx
Web-based management interface for Proxmox VE clusters. Aggregates multiple nodes into a single dashboard with live VM monitoring, start/stop/snapshot controls, noVNC console access, and an SSH terminal.

- **Location**: [`/pegaprox`](pegaprox/)
- **Access**: `https://<PEGAPROX_DOMAIN>` (via Traefik, LAN only)
- **Documentation**: See [pegaprox/README.md](pegaprox/README.md)

### Tdarr
Distributed media transcoding automation platform. Scans a media library, applies codec conversion rules (H.265, AV1), and manages a queue of transcode jobs across one or more worker nodes — shrinking library size and reducing Plex transcodes at watch time.

- **Location**: [`/tdarr`](tdarr/)
- **Access**: `https://<TDARR_DOMAIN>` (via Traefik, LAN only)
- **Port**: 8265 (web UI and node communication)
- **Documentation**: See [tdarr/README.md](tdarr/README.md)

### Tdarr Desktop Node
A Tdarr worker node configured for a gaming desktop (NVIDIA RTX 3090). Connects to the Tdarr server on TrueNAS over the LAN and processes transcode jobs using the desktop GPU when available.

- **Location**: [`/tdarr-desktop-node`](tdarr-desktop-node/)
- **Requires**: Tdarr server (`/tdarr`) running on TrueNAS; media accessible via NFS mount
- **Documentation**: See [tdarr-desktop-node/README.md](tdarr-desktop-node/README.md)

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
Log aggregation backend for container, syslog, journal, and OTLP logs. Grafana Alloy ships logs into Loki; Grafana is the query UI.

- **Location**: [`/loki`](loki/)
- **Port**: 3100 (Loki ingest — internal only)
- **Requires**: `prometheus` stack deployed first (joins the `monitoring` network)
- **Documentation**: See [loki/README.md](loki/README.md)

### Grafana Alloy
Telemetry collector that replaces Promtail. Collects Docker logs, systemd journal logs, syslog, and OTLP telemetry, then forwards logs to Loki and metrics to Prometheus.

- **Location**: [`/alloy`](alloy/)
- **Ports**: 514 (syslog UDP/TCP), 4317/4318 (OTLP), debug UI via Traefik
- **Requires**: `prometheus`, `loki`, and `traefik` networks
- **Documentation**: See [alloy/README.md](alloy/README.md)

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
- **Ollama host**: Remote instance at `<OLLAMA_HOST>:11434`
- **Documentation**: See [openwebui/README.md](openwebui/README.md)

### NetBox
IPAM (IP Address Management) and network documentation platform. Tracks IP prefixes, individual addresses, VLANs, devices, racks, and cables — single source of truth for home lab network inventory.

- **Location**: [`/netbox`](netbox/)
- **Access**: `https://<NETBOX_DOMAIN>` (via Traefik, LAN only)
- **Port**: 8060 (direct access)
- **Documentation**: See [netbox/README.md](netbox/README.md)

### Bambu Studio
Browser-accessible Bambu Studio desktop GUI via KasmVNC.

- **Location**: [`/bambustudio`](bambustudio/)
- **Access**: `https://<BAMBUSTUDIO_DOMAIN>` (via Traefik, LAN only)
- **Documentation**: See [bambustudio/README.md](bambustudio/README.md)

### code-server
Browser-based VS Code development environment.

- **Location**: [`/code-server`](code-server/)
- **Access**: `https://<CODESERVER_DOMAIN>` (via Traefik, LAN only)
- **Documentation**: See [code-server/README.md](code-server/README.md)

### Gitea
Self-hosted Git service with PostgreSQL storage and direct SSH clone access.

- **Location**: [`/gitea`](gitea/)
- **Access**: `https://<GITEA_DOMAIN>` (via Traefik), SSH on host port 2222 by default
- **Documentation**: See [gitea/README.md](gitea/README.md)

### Heimdall
Simple application dashboard and service launcher.

- **Location**: [`/heimdall`](heimdall/)
- **Access**: `https://<HEIMDALL_DOMAIN>` (via Traefik)
- **Documentation**: See [heimdall/README.md](heimdall/README.md)

### Karakeep
Bookmark and read-it-later service with Meilisearch and browser capture support.

- **Location**: [`/karakeep`](karakeep/)
- **Access**: `https://<KARAKEEP_DOMAIN>` (via Traefik)
- **Documentation**: See [karakeep/README.md](karakeep/README.md)

### Libation
Audible library downloader for audiobook archival workflows.

- **Location**: [`/libation`](libation/)
- **Output**: `/mnt/Data/Media/Audiobooks`
- **Documentation**: See [libation/README.md](libation/README.md)

### Linkwarden
Collaborative bookmark manager with PostgreSQL persistence.

- **Location**: [`/linkwarden`](linkwarden/)
- **Access**: `https://<LINKWARDEN_DOMAIN>` (via Traefik)
- **Documentation**: See [linkwarden/README.md](linkwarden/README.md)

### MeTube
Web UI for yt-dlp downloads.

- **Location**: [`/metube`](metube/)
- **Access**: `https://<METUBE_DOMAIN>` (via Traefik, LAN only)
- **Port**: 8091 (direct access)
- **Documentation**: See [metube/README.md](metube/README.md)

### ownCloud Infinite Scale
Modern ownCloud deployment using the OCIS container and local POSIX storage.

- **Location**: [`/owncloud`](owncloud/)
- **Access**: `https://<OCIS_DOMAIN>` (via Traefik)
- **Documentation**: See [owncloud/README.md](owncloud/README.md)

### Readeck
Self-hosted read-it-later service.

- **Location**: [`/readeck`](readeck/)
- **Access**: `https://<READECK_DOMAIN>` (via Traefik)
- **Documentation**: See [readeck/README.md](readeck/README.md)

### RetroArch
Browser-accessible RetroArch desktop GUI via KasmVNC.

- **Location**: [`/retroarch`](retroarch/)
- **Access**: `https://<RETROARCH_DOMAIN>` (via Traefik, LAN only)
- **Documentation**: See [retroarch/README.md](retroarch/README.md)

### Traefik Manager
Web UI for managing Traefik dynamic configuration.

- **Location**: [`/traefik-manager`](traefik-manager/)
- **Access**: `https://<TRAEFIK_MANAGER_DOMAIN>` (via Traefik)
- **Requires**: Traefik API enabled internally
- **Documentation**: See [traefik-manager/README.md](traefik-manager/README.md)

### Unmanic
Automated media library optimization and transcoding worker.

- **Location**: [`/umanic`](umanic/)
- **Access**: `https://<UNMANIC_DOMAIN>` (via Traefik)
- **Port**: 8095 (direct access)
- **Documentation**: See [umanic/README.md](umanic/README.md)

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
├── traefik/              # Reverse proxy and TLS termination
├── prometheus/           # Metrics collection (creates monitoring network)
├── grafana/              # Metrics dashboards and visualization
├── loki/                 # Log aggregation backend
├── alloy/                # Telemetry collector for logs, syslog, and OTLP
├── unpoller/             # UniFi metrics exporter
├── prometheus-pve-exporter/  # Proxmox VE metrics exporter
├── dozzle/               # Real-time Docker log viewer
├── uptime-kuma/          # Uptime monitoring (HTTP, TCP, DNS)
├── wud/                  # What's Up Docker — container update notifications
├── nextcloud/            # Self-hosted file sync and collaboration
├── paperless-ngx/        # Document management with OCR
├── calibre/              # Calibre + Calibre-Web ebook manager
├── bambustudio/          # Browser-accessible Bambu Studio GUI
├── retroarch/            # Browser-accessible RetroArch GUI
├── changedetection/      # Website change detection and monitoring
├── openwebui/            # Web UI for Ollama LLM models
├── owncloud/             # ownCloud Infinite Scale
├── linkwarden/           # Bookmark manager
├── karakeep/             # Bookmark/read-it-later service
├── readeck/              # Read-it-later service
├── metube/               # yt-dlp web UI
├── libation/             # Audible library downloader
├── homeassistant/        # Home automation platform
├── tdarr/                # Distributed media transcoding server
├── tdarr-desktop-node/   # Tdarr GPU worker node (gaming desktop)
├── netbox/               # Network documentation and IPAM
├── phpipam/              # Lightweight IP address management
├── unbound/              # Recursive DNS resolver (Pi-hole upstream)
├── arcane/               # Application management platform
├── termix/               # Web-based terminal emulator
├── code-server/          # Browser-based VS Code
├── gitea/                # Self-hosted Git service
├── heimdall/             # Application dashboard
├── semaphore/            # Ansible/Terraform/OpenTofu UI
├── pegaprox/             # Proxmox VE web management UI
├── traefik-manager/      # Traefik dynamic config manager
├── tailscale/            # Tailscale VPN node (subnet router)
├── umanic/               # Media optimization worker
├── .gitignore            # Git ignore patterns (protects secrets)
├── LICENSE               # MIT License
└── README.md             # This file
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
- **Arcane Data**: `/mnt/SSD/Containers/arcane`
- **Arcane Database**: `/mnt/SSD/Containers/arcane-postgres`
- **Termix Data**: `/mnt/SSD/Containers/termix`
- **Prometheus Data**: `/mnt/SSD/Containers/prometheus`
- **Grafana Data**: `/mnt/SSD/Containers/grafana`
- **Grafana Provisioning**: `/mnt/SSD/Containers/grafana/provisioning`
- **Loki Data**: `/mnt/SSD/Containers/loki`
- **Alloy Data**: `/mnt/SSD/Containers/alloy`
- **Semaphore Data**: `/mnt/SSD/Containers/semaphore/data`
- **Semaphore Config**: `/mnt/SSD/Containers/semaphore/config`
- **Semaphore Tmp**: `/mnt/SSD/Containers/semaphore/tmp`
- **Uptime Kuma Data**: `/mnt/SSD/Containers/uptime-kuma`
- **WUD Store**: `/mnt/SSD/Containers/wud`
- **Dozzle Data**: `/mnt/SSD/Containers/dozzle`
- **Tailscale State**: `/mnt/SSD/Containers/tailscale`
- **Calibre Config**: `/mnt/SSD/Containers/calibre`
- **Calibre-Web Config**: `/mnt/SSD/Containers/calibre-web`
- **Bambu Studio Data**: `/mnt/SSD/Containers/bambustudio`
- **RetroArch Data**: `/mnt/SSD/Containers/retroarch`
- **Changedetection Data**: `/mnt/SSD/Containers/changedetection`
- **code-server Data**: `/mnt/SSD/Containers/code-server`
- **Gitea Data**: `/mnt/SSD/Containers/gitea/data`
- **Gitea Database**: `/mnt/SSD/Containers/gitea/db`
- **Heimdall Data**: `/mnt/SSD/Containers/heimdall`
- **Karakeep Data**: `/mnt/SSD/Containers/karakeep/data`
- **Karakeep Meilisearch**: `/mnt/SSD/Containers/karakeep/meilisearch`
- **Libation Config**: `/mnt/SSD/Containers/libation/config`
- **Libation Database**: `/mnt/SSD/Containers/libation/db`
- **Linkwarden Data**: `/mnt/SSD/Containers/linkwarden/data`
- **Linkwarden Database**: `/mnt/SSD/Containers/linkwarden/db`
- **MeTube Config**: `/mnt/SSD/Containers/metube`
- **Nextcloud HTML**: `/mnt/SSD/Containers/nextcloud/html`
- **Nextcloud Data**: `/mnt/SSD/Containers/nextcloud/data`
- **Nextcloud Database**: `/mnt/SSD/Containers/nextcloud/db`
- **Nextcloud Redis**: `/mnt/SSD/Containers/nextcloud/redis`
- **Open WebUI Data**: `/mnt/SSD/Containers/openwebui`
- **ownCloud Config**: `/mnt/SSD/Containers/ocis/config`
- **ownCloud Data**: `/mnt/SSD/Containers/ocis/data`
- **Readeck Data**: `/mnt/SSD/Containers/readeck/data`
- **Paperless Data**: `/mnt/SSD/Containers/paperless/data`
- **Paperless Media**: `/mnt/SSD/Containers/paperless/media`
- **Paperless Consume**: `/mnt/SSD/Containers/paperless/consume`
- **Paperless Export**: `/mnt/SSD/Containers/paperless/export`
- **Paperless Database**: `/mnt/SSD/Containers/paperless/db`
- **Paperless Redis**: `/mnt/SSD/Containers/paperless/redis`
- **Home Assistant Config**: `/mnt/SSD/Containers/homeassistant`
- **Tdarr Server Data**: `/mnt/SSD/Containers/tdarr/server`
- **Tdarr Configs**: `/mnt/SSD/Containers/tdarr/configs`
- **Tdarr Logs**: `/mnt/SSD/Containers/tdarr/logs`
- **Tdarr Transcode Cache**: `/mnt/SSD/Containers/tdarr/transcode-cache`
- **NetBox Database**: `/mnt/SSD/Containers/netbox/db`
- **NetBox Redis**: `/mnt/SSD/Containers/netbox/redis`
- **NetBox Redis Cache**: `/mnt/SSD/Containers/netbox/redis-cache`
- **NetBox Media**: `/mnt/SSD/Containers/netbox/media`
- **NetBox Reports**: `/mnt/SSD/Containers/netbox/reports`
- **NetBox Scripts**: `/mnt/SSD/Containers/netbox/scripts`
- **PegaProx Config**: `/mnt/SSD/Containers/pegaprox/config`
- **PegaProx Logs**: `/mnt/SSD/Containers/pegaprox/logs`
- **phpIPAM Database**: `/mnt/SSD/Containers/phpipam/db`
- **phpIPAM Logo**: `/mnt/SSD/Containers/phpipam/logo`
- **phpIPAM CA**: `/mnt/SSD/Containers/phpipam/ca`
- **Traefik Manager Config**: `/mnt/SSD/Containers/traefik-manager/config`
- **Traefik Manager Backups**: `/mnt/SSD/Containers/traefik-manager/backups`
- **Traefik Dynamic Config**: `/mnt/SSD/Containers/traefik/dynamic`
- **Unmanic Config**: `/mnt/SSD/Containers/unmanic/config`
- **Unmanic Cache**: `/mnt/SSD/Containers/unmanic/cache`
- **Unbound Config**: `/mnt/SSD/Containers/unbound`

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
