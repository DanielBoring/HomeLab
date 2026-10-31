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
Metrics collection and storage with 30-day retention. Prometheus scrapes monitoring services through the `monitoring` Docker network and Traefik through the `traefik` network. This stack **owns and creates** the shared `monitoring` network that Grafana, Unpoller, and proxmox-exporter attach to.

- **Location**: [`/prometheus`](prometheus/)
- **Access**: `https://<PROMETHEUS_DOMAIN>` (via Traefik, LAN only)
- **Deploy after Traefik and before monitoring consumers**: it joins `traefik` and creates `monitoring` for Grafana, Loki, Alloy, Unpoller, and exporters.
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

### ntopng
Network traffic analysis UI with Redis persistence. This limited stack does not
configure a UniFi NetFlow collector or a Prometheus exporter; joining a network
does not provide those integrations. See its README before expecting LAN-wide
traffic visibility.

- **Location**: [`/ntopng`](ntopng/)
- **Access**: `https://<NTOPNG_DOMAIN>` (via Traefik, LAN only)
- **Ports**: 2055/udp (published but no collector configured), 3000 (internal web UI)
- **Requires**: `prometheus` stack deployed first (joins the `monitoring` network)

### Prometheus Proxmox Exporter
Exports Proxmox VE cluster and node metrics to Prometheus.

- **Location**: [`/prometheus-proxmox-exporter`](prometheus-proxmox-exporter/)
- **Port**: 9221 (Prometheus scrape endpoint)
- **Requires**: `prometheus` stack deployed first (joins the `monitoring` network)
- **Documentation**: See [prometheus-proxmox-exporter/README.md](prometheus-proxmox-exporter/README.md)

### Prometheus TrueNAS Exporter
Node Exporter instance running on the TrueNAS Docker host, exposing host-level CPU, memory, disk, and network metrics to Prometheus via the `monitoring` network.

- **Location**: [`/prometheus-truenas-exporter`](prometheus-truenas-exporter/)
- **Port**: 9100 (Prometheus scrape endpoint — monitoring network only)
- **Requires**: `prometheus` stack deployed first (joins the `monitoring` network)

### Semaphore
Self-hosted UI for running Ansible, Terraform, and OpenTofu playbooks with scheduling and access control.

- **Location**: [`/semaphore`](semaphore/)
- **Port**: 3003
- **Documentation**: See [semaphore/README.md](semaphore/README.md)

### n8n
Self-hosted workflow automation platform. Connects apps, APIs, and services via a node-based visual editor, with PostgreSQL for persistent workflow state.

- **Location**: [`/n8n`](n8n/)
- **Access**: `https://<N8N_DOMAIN>` (via Traefik, LAN only)
- **Port**: 5678 (direct access)
- **Documentation**: See [n8n/README.md](n8n/README.md)

### Uptime Kuma
Self-hosted uptime monitoring for services via HTTP/HTTPS, TCP, DNS, and more.

- **Location**: [`/uptime-kuma`](uptime-kuma/)
- **Access**: `https://<UPTIME_KUMA_DOMAIN>` (via Traefik)
- **Documentation**: See [uptime-kuma/README.md](uptime-kuma/README.md)

### Scrutiny
S.M.A.R.T. drive health monitoring with a web UI and historical trending. Bundles smartctl, an InfluxDB time-series store, and a dashboard into a single omnibus container. Requires raw device access and elevated capabilities (`SYS_RAWIO`, `SYS_ADMIN`) to issue ATA and NVMe passthrough commands.

- **Location**: [`/scrutiny`](scrutiny/)
- **Access**: `https://<SCRUTINY_DOMAIN>` (via Traefik, LAN only)
- **Port**: 8096 (direct access)
- **Documentation**: See [scrutiny/readme.md](scrutiny/readme.md)

### Unbound
Validating, recursive, caching DNS resolver. The explicit configuration in this
repository queries root/authoritative DNS servers rather than a forwarding
provider. It must be installed as described in the service README; an older
generated configuration may still forward queries. Recursion is not encryption
or anonymity: authoritative servers and network observers can see DNS traffic.

- **Location**: [`/unbound`](unbound/)
- **Port**: 5335 (UDP+TCP — DNS only, no web UI)
- **Documentation**: See [unbound/README.md](unbound/README.md)

### Technitium
Feature-rich self-hosted DNS server with a web admin UI. Handles internal DNS resolution for the home lab and supports conditional forwarding, DNS-over-HTTPS/TLS, DNS blocking, and zone management.

- **Location**: [`/technitium`](technitium/)
- **Access**: `https://<TECHNITIUM_DOMAIN>` (via Traefik, LAN only)
- **Ports**: 53 UDP+TCP (DNS), 5380 (internal web UI)
- **Documentation**: See [technitium/README.md](technitium/README.md)

### Home Assistant
Open-source home automation platform. Connects to thousands of devices and services — lights, sensors, locks, cameras, media players — and runs automations entirely locally without cloud dependency.

- **Location**: [`/homeassistant`](homeassistant/)
- **Access**: `https://<HOMEASSISTANT_DOMAIN>` (via Traefik) and `http://<host-ip>:8123` (direct, for companion app)
- **Documentation**: See [homeassistant/README.md](homeassistant/README.md)

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
- **Port**: 3100 (published ingest/API; restrict host access because Loki has no built-in authentication here)
- **Requires**: `prometheus` stack deployed first (joins the `monitoring` network)
- **Documentation**: See [loki/README.md](loki/README.md)

### Grafana Alloy
Telemetry collector that replaces Promtail. Collects Docker logs, systemd journal logs, syslog, and OTLP telemetry, then forwards logs to Loki and metrics to Prometheus.

- **Location**: [`/alloy`](alloy/)
- **Ports**: 514 (syslog UDP/TCP), 4317/4318 (OTLP), debug UI via Traefik
- **Requires**: Traefik and Prometheus to create `traefik` and `monitoring`; Loki running for log ingestion
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

### Bambu Buddy
LAN-only, self-hosted Bambu Lab printer management and print archive service.
Printers are added manually by their DHCP-reserved IP address so the web UI can
remain behind Traefik.

- **Location**: [`/bambuddy`](bambuddy/)
- **Access**: `https://<BAMBUDDY_DOMAIN>` (via Traefik, LAN only)
- **Documentation**: See [bambuddy/README.md](bambuddy/README.md)

### Printventory
LAN-only library manager for 3D-printable files (STL, 3MF, OBJ, STEP) with
thumbnails, search, tagging, and print/filament tracking. The model library is
mounted read-only.

- **Location**: [`/printventory`](printventory/)
- **Access**: `https://<PRINTVENTORY_DOMAIN>` (via Traefik, LAN only)
- **Documentation**: See [printventory/README.md](printventory/README.md)

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

### Homarr
Modern application dashboard with live Docker integration. Auto-discovers running containers, displays service status, and integrates with Sonarr, Radarr, and other arr apps for media stats.

- **Location**: [`/homarr`](homarr/)
- **Access**: `https://<HOMARR_DOMAIN>` (via Traefik, LAN only)
- **Documentation**: See [homarr/README.md](homarr/README.md)

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

### SearXNG
Privacy-respecting metasearch engine. Aggregates results from 70+ search engines without tracking or profiling. Backed by Redis for rate-limiting.

- **Location**: [`/searxng`](searxng/)
- **Access**: `https://<SEARXNG_DOMAIN>` (via Traefik, LAN only)
- **Port**: 8092 (direct access)
- **Documentation**: See [searxng/README.md](searxng/README.md)

### RetroArch
Browser-accessible RetroArch desktop GUI via KasmVNC.

- **Location**: [`/retroarch`](retroarch/)
- **Access**: `https://<RETROARCH_DOMAIN>` (via Traefik, LAN only)
- **Documentation**: See [retroarch/README.md](retroarch/README.md)

### RomM
ROM library manager and game metadata scraper. Organizes game files by platform, fetches cover art and metadata from ScreenScraper, RetroAchievements, SteamGridDB, and Hasheous, then serves a browsable web UI backed by MariaDB.

- **Location**: [`/romm`](romm/)
- **Access**: `https://<ROMM_DOMAIN>` (via Traefik, LAN only)
- **Library**: `/mnt/Data/Media/ROMs`
- **Documentation**: See [romm/README.md](romm/README.md)

### Traefik Manager
Web UI for managing Traefik dynamic configuration.

- **Location**: [`/traefik-manager`](traefik-manager/)
- **Access**: `https://<TRAEFIK_MANAGER_DOMAIN>` (via Traefik)
- **Requires**: Traefik API enabled internally
- **Documentation**: See [traefik-manager/README.md](traefik-manager/README.md)

### Unmanic
Automated media library optimization and transcoding worker.

- **Location**: [`/unmanic`](unmanic/)
- **Access**: `https://<UNMANIC_DOMAIN>` (via Traefik)
- **Port**: 8095 (direct access)
- **Documentation**: See [unmanic/README.md](unmanic/README.md)

## Quick Start

### Prerequisites

- Docker Engine 20.10+
- Docker Compose 2.23.1 or later (Loki uses inline `configs.content`)
- Linux host with sufficient storage for container volumes

Prepare each stack's host files and environment before deployment. Start Traefik
first to create `traefik`, then Prometheus to create `monitoring`, then the
monitoring consumers. Traefik does not depend on `monitoring`; Prometheus reaches
its metrics endpoint at `traefik:8082` through their shared `traefik` bridge.

### General Deployment Pattern

Each service follows a consistent structure:

```bash
# Navigate to service directory
cd <service-name>

# Copy the environment template, including domain and port settings
cp .env.example .env

# Edit configuration
nano .env  # Customize as needed

# Start the service
docker compose up -d

# Check status
docker compose ps
docker compose logs -f
```

## Repository Structure

```text
HomeLab/
├── traefik/                        # Reverse proxy and TLS termination
├── prometheus/                     # Metrics collection (creates monitoring network)
├── grafana/                        # Metrics dashboards and visualization
├── loki/                           # Log aggregation backend
├── alloy/                          # Telemetry collector for logs, syslog, and OTLP
├── unpoller/                       # UniFi metrics exporter
├── ntopng/                         # Real-time network traffic monitoring
├── prometheus-proxmox-exporter/    # Proxmox VE metrics exporter
├── prometheus-truenas-exporter/    # TrueNAS host node exporter
├── dozzle/                         # Real-time Docker log viewer
├── uptime-kuma/                    # Uptime monitoring (HTTP, TCP, DNS)
├── scrutiny/                       # S.M.A.R.T. drive health monitoring
├── nextcloud/                      # Self-hosted file sync and collaboration
├── paperless-ngx/                  # Document management with OCR
├── calibre/                        # Calibre + Calibre-Web ebook manager
├── bambustudio/                    # Browser-accessible Bambu Studio GUI
├── bambuddy/                       # LAN-only Bambu Lab printer management
├── printventory/                   # 3D model library manager
├── retroarch/                      # Browser-accessible RetroArch GUI
├── romm/                           # ROM library manager and scraper
├── changedetection/                # Website change detection and monitoring
├── openwebui/                      # Web UI for Ollama LLM models
├── owncloud/                       # ownCloud Infinite Scale
├── linkwarden/                     # Bookmark manager
├── karakeep/                       # Bookmark/read-it-later service
├── readeck/                        # Read-it-later service
├── searxng/                        # Privacy metasearch engine
├── metube/                         # yt-dlp web UI
├── libation/                       # Audible library downloader
├── homeassistant/                  # Home automation platform
├── tdarr/                          # Distributed media transcoding server
├── tdarr-desktop-node/             # Tdarr GPU worker node (gaming desktop)
├── unmanic/                        # Media optimization worker
├── netbox/                         # Network documentation and IPAM
├── phpipam/                        # Lightweight IP address management
├── unbound/                        # Recursive DNS resolver (Pi-hole upstream)
├── technitium/                     # Self-hosted DNS server with web UI
├── arcane/                         # Application management platform
├── termix/                         # Web-based terminal emulator
├── code-server/                    # Browser-based VS Code
├── gitea/                          # Self-hosted Git service
├── heimdall/                       # Application dashboard
├── homarr/                         # Modern dashboard with Docker integration
├── semaphore/                      # Ansible/Terraform/OpenTofu UI
├── n8n/                            # Workflow automation platform
├── pegaprox/                       # Proxmox VE web management UI
├── traefik-manager/                # Traefik dynamic config manager
├── tailscale/                      # Tailscale VPN node (subnet router)
├── .gitignore                      # Git ignore patterns (protects secrets)
├── LICENSE                         # MIT License
└── README.md                       # This file
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
- `.env` and every `.env.*` variant (`.env.local`, `.env.prod`, `.env.bak`, …) - Environment files with secrets. The one exception is `.env.example`, the committed template (`!.env.example`, GitHub's standard dotenv pattern)
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
   openssl rand -hex 32     # URL-safe passwords; follow each app's format requirements
   ```

3. **Rotate credentials deliberately** - Follow each application's supported
   password/account procedure and update dependent connection settings together.
   Database initialization variables do not change existing accounts. Preserve
   persistent encryption keys unless a verified migration re-encrypts existing
   data; replacing a key can make stored credentials unreadable.

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
- **Dozzle Data**: `/mnt/SSD/Containers/dozzle`
- **Tailscale State**: `/mnt/SSD/Containers/tailscale`
- **Calibre Config**: `/mnt/SSD/Containers/calibre`
- **Calibre-Web Config**: `/mnt/SSD/Containers/calibre-web`
- **Bambu Studio Data**: `/mnt/SSD/Containers/bambustudio`
- **Bambu Buddy Data**: `/mnt/SSD/Containers/bambuddy/data`
- **Bambu Buddy Logs**: `/mnt/SSD/Containers/bambuddy/logs`
- **Printventory Data**: `/mnt/SSD/Containers/printventory/data`
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
- **Technitium Config**: `/mnt/SSD/Containers/technitium/config`
- **Technitium Logs**: `/mnt/SSD/Containers/technitium/logs`
- **Homarr Data**: `/mnt/SSD/Containers/homarr`
- **n8n Data**: `/mnt/SSD/Containers/n8n/data`
- **n8n Database**: `/mnt/SSD/Containers/n8n/postgres`
- **ntopng Data**: `/mnt/SSD/Containers/ntopng`
- **ntopng Redis**: `/mnt/SSD/Containers/ntopng/redis`
- **RomM Resources**: `/mnt/SSD/Containers/romm/resources`
- **RomM Redis**: `/mnt/SSD/Containers/romm/redis-data`
- **RomM Assets**: `/mnt/SSD/Containers/romm/assets`
- **RomM Config**: `/mnt/SSD/Containers/romm/config`
- **RomM Database**: `/mnt/SSD/Containers/romm/db`
- **Scrutiny Config**: `/mnt/SSD/Containers/scrutiny/config`
- **Scrutiny InfluxDB**: `/mnt/SSD/Containers/scrutiny/influxdb`
- **SearXNG Config**: `/mnt/SSD/Containers/searxng/config`

Ensure this path exists and has appropriate permissions before deploying services.

## Deployment

Services are deployed and managed via **Portainer GitOps**:

1. Push changes to this repository on GitHub
2. Portainer polls GitHub every 5 minutes and automatically pulls changes and redeploys affected stacks
3. For immediate deployment (e.g. during troubleshooting), trigger a manual **Force Update** in Portainer

For Portainer deployments, settings are stored per-stack in Portainer. Host CLI
examples instead require a private `.env` (or equivalent exported settings) and
the same project name as the deployed stack. Portainer variables are not
automatically available to a CLI run.

## Maintenance

### Image Updates

Dependabot opens weekly pull requests for image version updates through
[.github/dependabot.yml](.github/dependabot.yml). The `docker-compose` entry uses
`directories: ["/*"]` to cover every top-level service directory, including new
ones. GitHub Actions dependencies have a separate weekly update entry.

On October 12, 2026, image references for 48 services in 32 stacks were frozen
to registry manifests verified against their running TrueNAS images. This
selects the already-running software, not a newer release. The remaining 26
services in 16 stacks were absent from that inventory; their references remain
unchanged and must not be treated as verified pins.

An image **digest** (`@sha256:...`) is an exact content fingerprint. For 35
services, a release tag was also verified and recorded as
`repository:version@sha256:...`. For 13 services without a verified release
tag, the reference is `repository@sha256:...`; do not invent a version from a
build label. Registry manifest digests are pullable references; local Docker
image IDs are not interchangeable with them.

Dependabot reads the files in GitHub, not the images running on TrueNAS. Its
Compose parser supports version tags and digest references, but a digest alone
does not identify a release number or whether an update is breaking. For a
digest-only proposal, verify the upstream release and update stream before
approving it. Unpinned moving tags still need a separate running-image inventory
and version-selection plan.

Keep image references literal in Compose. Even where Dependabot parses a
`${VARIABLE:-default}` reference, an override in `.env` or Portainer can make
an updated default ineffective. Printventory's image is now managed directly
in Compose, not through `PRINTVENTORY_VERSION`.

> **Merging a Dependabot PR deploys it.** Portainer polls `main` and redeploys changed stacks within about 5 minutes (see [Deployment](#deployment)). Read the release notes and take any pre-upgrade backup (e.g. a database dump) **before** merging. Postgres major-version bumps need a dump and restore, not a plain merge.

To update a pinned image, review the upstream release notes, migration
requirements, and backups, then review a Dependabot PR or change the image
reference in Compose. Update both the version tag and digest when both are
present; changing only the tag leaves the old digest in control. Keep Nextcloud
and its cron service on the same image reference. `docker compose pull` alone
does not advance a pin to a newer release.

Local file edits do not deploy anything. A later Portainer redeployment can
recreate containers and apply other configuration changes in the same revision,
so review the complete change before publishing. Neither image pinning nor a
passing PR check establishes application compatibility or migration safety.

#### Pull request checks

[Compose validation](.github/workflows/compose-validation.yml) runs the
**Validate Compose** job on every pull request, including Dependabot PRs, on
pushes to `main`, and on manual workflow dispatch. It:

- Tests the checker, then validates every Git-tracked or new, non-ignored
  Compose stack with Docker Compose, including all profiles.
- Uses dummy settings, bypasses default `.env` loading and service `env_file`
  resolution, and isolates Docker configuration from local credentials.
  Service `env_file` paths in the validation copy are replaced with an owned
  empty file while retaining their schema/options: some Compose v2 releases
  still require the original file's existence with `--no-env-resolution`.
- Checks digest syntax and matching Nextcloud application/cron images.
- Adds a PR run summary comparing images with the base commit, including
  database-major, repository-change, and unclassifiable-version warnings.

Image warnings require human review; they do not fail the job. The check does
not pull images, contact HomeLab infrastructure, deploy services, run application
health checks, or test database migrations. It cannot establish that an image
exists in its registry or that a tag agrees with its digest.

The workflow uses GitHub-hosted runners, read-only repository permissions, and
no HomeLab secrets. It does not configure merge protection or auto-merge. To
prevent merges with failing checks, a repository owner must separately require
the **Validate Compose** check in a branch protection rule or ruleset after
observing a successful hosted run. A direct push to `main` can be redeployed by
Portainer before its push checks finish.

For a local check, use Python 3.10+ with the pinned dependency in
[requirements.txt](.github/scripts/requirements.txt) and Docker Compose with
`config --no-env-resolution` and `--no-path-resolution` support. The checker
supports independent stack files; `include` and `extends` are rejected to avoid
loading additional settings sources. New required settings may need a typed
dummy value in the checker; a passing dummy check is not a check of actual
Portainer settings. Dependabot also reviews the checker dependency weekly.

From the repository root on **Windows/PowerShell**:

```powershell
python -B -m unittest discover -s .github\scripts -p "test_*.py" -v
python -B .github\scripts\validate_compose.py --base-ref HEAD
```

On **Linux**, use `python3` and `.github/scripts` paths instead. Without
`--base-ref`, the checker validates all current stacks but skips image comparison.

### Retired update monitor

WUD is retired in favor of Dependabot review through GitHub. Its old named volume
`wud_wud-store` and host data at `/mnt/SSD/Containers/wud` are intentionally
preserved for rollback. They are not part of an active stack; do not delete them
or include them in volume-pruning cleanup without a separate retention decision.

### Backing Up Data

There is no safe one-directory backup command for every stack. Use each service's
**Operations and recovery** or **Backup** section to identify its full restore
set. Examples of paths that must not be inferred from the directory name:

| Stack | Restore set includes |
|---|---|
| Arcane | `arcane`, `arcane-postgres`, original encryption/JWT keys and database settings |
| Calibre | `calibre`, `calibre-web`, `/mnt/Data/Media/Books` |
| ownCloud | `ocis/config` and `ocis/data`, not `owncloud` |
| Paperless | `paperless` database, data, media, unprocessed consume files, and secret settings |
| Nextcloud | Entire `nextcloud/html` and `nextcloud/data`, logical SQL dump, original settings; see its staged procedure |
| Media/download services | Their application state **and** any irreplaceable media outside `/mnt/SSD/Containers` |

For a **cold filesystem backup**, on the Linux Docker host:

1. Pause deployment/update automation and writers, including other stacks that
   write to shared media. Confirm the CLI project/settings match the deployment.
2. Stop the stack's containers with `docker compose stop`; do not use `down -v`.
   A shared-network owner should remain deployed: removing its network can fail
   while consumers are attached. Coordinate downtime for consumers separately.
3. With every database/application writer stopped, snapshot or archive **all**
   required paths together. Preserve numeric ownership, modes, ACLs and xattrs.
   Use a private destination outside the data tree and checkout, sufficient free
   space, and fail-fast commands. Do not resume automatically after a failure.
   Copying a running database directory is not a consistent database backup.
4. Verify archive readability/checksums, retain exact Compose/image versions and
   original private settings separately, then resume existing containers with
   `docker compose start`. Review status/logs and the application's own checks.
5. Encrypt private archives/settings and keep a verified copy on separate
   storage. Same-pool snapshots do not protect against loss of that pool.

For a **restore**, first drill on an isolated host using the original versions
and settings. Block user ingress and pause automation; retain the existing tree
or dataset snapshot for rollback. Prepare empty destinations at the exact volume
paths, restore the complete consistent set with its original ownership, and
start databases before applications/jobs. Never extract over a running database
or merge old and restored trees. Cold database files require compatible engine
versions; major database upgrades need their documented logical migration.
If any stage fails, leave services stopped and preserve the failed attempt.

ZFS dataset mount points must not be renamed using ordinary `mv` recipes.
Use supported TrueNAS snapshot/clone recovery instead. Retain dataset properties,
NFSv4 ACLs and encryption recovery material separately: tar ACL/xattr flags are
not a complete dataset backup. Only a successful isolated restore and application
checks establish recoverability; checksums alone do not.

Archives preserve symlinks, not external target data. Inventory shared mounts,
symlinks and PostgreSQL tablespaces before choosing the restore set; include
their targets separately and keep all relevant writers stopped. No generic
archive should be described as complete without that inventory.

### Shared operational safeguards

README shell examples target **Bash on the Linux/TrueNAS Docker host** unless
labelled PowerShell. Run Compose commands from the relevant service directory.
Create host directories and copy required config files before deployment.
Recursive ownership changes are for **fresh paths only**: never apply the
standard `3001:3001` ownership to existing database data or image-specific users.

Traefik's `lan-only` middleware protects only its routers, not published host
ports. Compose ports without a host IP bind to all host interfaces; restrict
them using the host/upstream firewall and never expose unauthenticated admin,
metrics, DNS or log endpoints to the internet. This is an access requirement,
not a claim that the current firewall has been checked.

A Docker socket mount grants powerful daemon control even with `:ro`; filesystem
read-only flags do not restrict Docker API methods. Trust the image and every
user able to operate it. Do not make the socket world-writable.

Before an update, preserve a recoverable backup and review the exact selected
release's migrations. Update reviewed image references, not just `pull`; some
stacks still have unresolved floating images. Disable unattended redeployments
during backup/recovery and never rely on a container healthcheck alone as proof
of correct application state.

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

# Compare the README/image-specific user with the host directory's numeric owners.
# Do not change an existing database tree to your login user's UID/GID.
```

**Container won't start**:
```bash
# View detailed logs
docker compose logs <service-name>

# Verify configuration
docker compose config --quiet

# List assigned setting names only (never print their values)
sed -nE 's/^[[:space:]]*([A-Za-z_][A-Za-z0-9_]*)=.*/\1/p' .env
```

Successful parsing does not check whether passwords, domains or host paths are
correct. Inspect settings privately; do not paste rendered Compose, dotenv
contents, container environments, or unredacted logs into issues.

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
