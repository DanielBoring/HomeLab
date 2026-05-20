# Copilot Instructions — HomeLab

## Overview

This is a Docker Compose-based homelab with 40+ self-hosted services running on TrueNAS SCALE. Each service is a self-contained directory deployed independently. Development and editing happens on Windows; the runtime target is Linux.

## Service Directory Convention

Every service directory follows this layout:

```
service-name/
├── compose.yaml          # Docker Compose definition (required)
├── .env.example          # Environment variable template (required, use this name for new services)
└── README.md             # Service-specific documentation (required)
```

Some services have additional config files (e.g., `traefik.yml`, `prometheus.yml`, `config.alloy`). The `.env.example` naming is preferred for new services — some older services still use `example.env`.

## Compose File Standards

All compose services should include these baseline settings:

```yaml
services:
  my-service:
    image: vendor/image:vX.Y.Z      # Always pin to a specific version, never :latest
    container_name: my-service
    restart: unless-stopped
    user: "3001:3001"                # Standard UID:GID unless the image requires root
    security_opt:
      - no-new-privileges:true
    cap_drop:
      - ALL
    logging:
      driver: json-file
      options:
        max-size: "10m"
        max-file: "3"
    healthcheck:
      test: [...]                    # Service-appropriate health endpoint
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 30s
```

When a service is exposed via Traefik, add these labels:

```yaml
    labels:
      - "traefik.enable=true"
      - "traefik.docker.network=traefik"
      - "traefik.http.routers.<service>.rule=Host(`${SERVICE_DOMAIN}`)"
      - "traefik.http.routers.<service>.entrypoints=websecure"
      - "traefik.http.routers.<service>.tls.certresolver=letsencrypt"
      - "traefik.http.routers.<service>.middlewares=secure-headers@file,lan-only@file"
      - "traefik.http.routers.<service>.service=<service>@docker"
      - "traefik.http.services.<service>.loadbalancer.server.port=<PORT>"
```

## Network Dependencies & Deploy Order

Two stacks create shared Docker networks that other services depend on:

| Stack | Creates Network | Type |
|-------|----------------|------|
| `traefik/` | `traefik` | bridge |
| `prometheus/` | `monitoring` | bridge |

**Deploy order matters:** Docker Compose validates external networks at startup and fails immediately if they don't exist.

Required order:
1. **traefik** — creates `traefik` network (most services depend on this)
2. **prometheus** — creates `monitoring` network
3. **loki**, **grafana**, **alloy**, **unpoller**, exporters — join `monitoring` as external
4. All other services — join `traefik` as external

Services that join a network as `external: true` cannot start until the owning stack is up.

## Host Paths & Ownership

All persistent container data lives under:

```
/mnt/SSD/Containers/<service-name>/
```

Standard ownership is `3001:3001` (matches the `user:` directive in compose). When creating a new service, the host directory must be created and owned before first deploy:

```bash
mkdir -p /mnt/SSD/Containers/<service-name>
chown -R 3001:3001 /mnt/SSD/Containers/<service-name>
```

Named volumes use `local` driver with bind to these paths:

```yaml
volumes:
  my-data:
    driver: local
    driver_opts:
      type: none
      device: /mnt/SSD/Containers/<service-name>
      o: bind
```

## Environment

- **Runtime:** TrueNAS SCALE (Debian-based Linux)
- **Development/editing:** Windows (PowerShell). Avoid shell constructs that break in PowerShell (e.g., `$var:suffix` is invalid — use `${var}` or separate the colon).
- **Reverse proxy:** Traefik v3 on macvlan IP `10.0.5.5`, TLS via Cloudflare DNS challenge
- **Monitoring:** Prometheus + Grafana + Loki + Alloy (replaced Promtail)
