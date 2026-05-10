# TrueNAS Node Exporter

Prometheus Node Exporter exposes hardware and OS-level metrics from the TrueNAS host — CPU, memory, disk I/O, filesystem usage, network throughput, and more. Without it, Prometheus only sees metrics from services running inside Docker containers; Node Exporter fills the gap with visibility into the underlying machine.

[https://github.com/prometheus/node_exporter](https://github.com/prometheus/node_exporter)

## What it exposes

| Metric group | Examples |
|---|---|
| CPU | usage by mode (user, system, iowait, idle), load average |
| Memory | total, available, cached, swap |
| Disk I/O | reads/writes per second, latency, queue depth |
| Filesystem | used/free bytes per mount point |
| Network | bytes in/out, errors, drops per interface |
| System | uptime, open file descriptors, context switches |

## Architecture

```
TrueNAS host
│
├── /proc, /sys, /  ← mounted read-only into container as /host
│
└── truenas-node-exporter (container)
      │   reads host metrics via --path.rootfs=/host
      │   pid: host  (sees host process table)
      └── :9100 (monitoring network only)
            │
            └── Prometheus ──→ Grafana
```

Node Exporter runs without Traefik exposure — Prometheus reaches it directly by container name on the shared `monitoring` bridge network.

## Why `pid: host` and `--path.rootfs=/host`

By default, a container only sees its own namespace. Two settings correct this:

- **`pid: host`** — shares the host's process namespace, so CPU and memory metrics cover all TrueNAS processes, not just the container's own PID tree.
- **`--path.rootfs=/host`** with `/:/host:ro` — Node Exporter reads `/host/proc`, `/host/sys`, and `/host/dev` instead of the container's virtual equivalents. This gives accurate disk I/O, filesystem, and network stats for the real hardware.

## Prerequisites

The `monitoring` Docker network must exist (created by the `prometheus/` stack). Deploy Prometheus first if you haven't already.

## Deployment

```sh
cd truenas-node-exporter
docker compose up -d
```

No `.env` file is needed — there are no configurable environment variables.

Verify the exporter is reachable from within Prometheus:

```sh
docker exec prometheus wget -qO- http://truenas-node-exporter:9100/metrics | head -20
```

## Prometheus scrape config

The scrape job is already wired in `prometheus/prometheus.yml`:

```yaml
- job_name: node
  static_configs:
    - targets: ["truenas-node-exporter:9100"]
```

After starting the container, reload Prometheus without a restart:

```sh
curl -X POST http://prometheus:9090/-/reload
```

## Grafana dashboard

Import **dashboard ID 1860** (Node Exporter Full) from the Grafana dashboard library. It provides pre-built panels for every metric group above and works out of the box with the `job="node"` label this scrape config produces.

In Grafana: **Dashboards → Import → Enter ID `1860` → Load → Select your Prometheus datasource → Import**

## Adding more hosts

Node Exporter is a per-host agent — one instance per machine. For other hosts (e.g. Proxmox nodes), install it natively:

```sh
# On each Proxmox node (Debian-based)
apt install prometheus-node-exporter
systemctl enable --now prometheus-node-exporter
```

Then add each host to the `node` job in `prometheus/prometheus.yml`:

```yaml
- job_name: node
  static_configs:
    - targets:
        - "truenas-node-exporter:9100"  # TrueNAS (container, monitoring network)
        - "10.0.5.21:9100"              # pmox1
        - "10.0.5.22:9100"              # pmox2
        - "10.0.5.23:9100"              # pmox3
```
