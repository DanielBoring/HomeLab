# Prometheus TrueNAS Exporter

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
└── prometheus-truenas-exporter (container)
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
cd prometheus-truenas-exporter
docker compose up -d
```

No `.env` file is needed — there are no configurable environment variables.

Verify the exporter is reachable from within Prometheus:

```sh
docker exec prometheus wget -q -O /dev/null http://prometheus-truenas-exporter:9100/metrics
```

This reads the complete response without printing it. Avoid piping `/metrics`
through `head`: closing the connection early can generate hundreds of
`error encoding and sending metric family` / `connection reset by peer` errors
per request. The container healthcheck also reads the full response and preserves
`wget`'s exit status.

## TrueNAS exporter troubleshooting

- **Filesystem permission errors under `/mnt/.ix-apps/docker/`:** these are
  Docker's internal mounts, often duplicate views of datasets already monitored
  at `/mnt/Data` and `/mnt/SSD`. The Compose configuration excludes these paths
  while retaining Node Exporter's default mount exclusions. It does not exclude
  the datasets' primary mountpoints or require changes to their ACLs. The `$$`
  in the regex is Compose's escape for a literal `$` passed to Node Exporter.
- **`node_scrape_collector_success` is zero:** this can mean that a collector
  found no applicable data, not just that it encountered an operational failure.
  Check exporter logs for `collector failed` before disabling collectors or
  granting additional privileges. No-data results are logged at debug level.
- **Exporter is up but filesystem metrics are incomplete:** check
  `node_filesystem_device_error` independently of `up`; a successful HTTP scrape
  does not guarantee that every filesystem was accessible.

After updating the stack, redeploy it through your usual Compose or Portainer
workflow. Verify that the encoding-error counter stops increasing and that
filesystem sizes remain available at the primary dataset mountpoints. The image
is pinned to `v1.12.1`, matching the version observed during troubleshooting.

## Prometheus scrape config

The scrape job is already wired in `prometheus/prometheus.yml`:

```yaml
- job_name: node
  static_configs:
    - targets: ["prometheus-truenas-exporter:9100"]
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
        - "prometheus-truenas-exporter:9100"  # TrueNAS (container, monitoring network)
        - "10.0.5.21:9100"              # pmox1
        - "10.0.5.22:9100"              # pmox2
        - "10.0.5.23:9100"              # pmox3
```
