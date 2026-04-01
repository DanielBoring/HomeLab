# Tailscale

Runs a Tailscale node inside a container, advertising subnet routes and acting as an exit node for your tailnet.

https://tailscale.com/docs/features/containers/docker

## Overview

| Setting | Value |
|---|---|
| Image | `tailscale/tailscale:latest` |
| Network mode | Host networking via `net_admin` + `/dev/net/tun` |
| Exit node | Enabled (`--advertise-exit-node`) |
| Subnet routes | `10.0.0.0/20` (configurable) |
| State | `/mnt/SSD/Containers/tailscale` |

## Prerequisites

- A Tailscale account and tailnet
- An auth key from the [Tailscale admin console](https://login.tailscale.com/admin/settings/keys)
- `/dev/net/tun` available on the host (standard on Linux)

## Quick Start

### 1. Copy the environment template

```bash
cp .env.example .env
```

### 2. Edit the .env file

```bash
nano .env
```

| Variable | Required | Description |
|---|---|---|
| `TS_AUTHKEY` | Yes | Auth key from the Tailscale admin console |
| `TS_HOSTNAME` | No | Node name in the admin console (default: `homelab`) |
| `TS_EXTRA_ARGS` | No | Extra flags passed to `tailscale up` |
| `TS_ROUTES` | No | Subnet routes to advertise (default: `10.0.0.0/20`) |

### 3. Create the state directory

```bash
mkdir -p /mnt/SSD/Containers/tailscale
```

### 4. Deploy

```bash
docker compose up -d
```

### 5. Approve subnet routes

After the first successful connection, go to the [Tailscale admin console](https://login.tailscale.com/admin/machines), find the node, and approve the advertised subnet routes.

## Auth Key Types

| Type | When to use |
|---|---|
| Reusable auth key | Simple setup; node registered under your user account |
| OAuth client secret | Preferred for long-running containers; does not expire |

Generate keys at [login.tailscale.com/admin/settings/keys](https://login.tailscale.com/admin/settings/keys).

## Exit Node

This container advertises itself as a Tailscale exit node. To use it, select it in the Tailscale client on any device in your tailnet under **Use exit node**.

## Storage

| Data | Path |
|---|---|
| Tailscale state | `/mnt/SSD/Containers/tailscale` |

State includes the node key and registration — preserving it avoids re-authentication on container restarts.

## Maintenance

### Update image

```bash
docker compose pull
docker compose up -d
```

### Re-authenticate

If the node loses authentication, delete the state directory and redeploy:

```bash
docker compose down
rm -rf /mnt/SSD/Containers/tailscale/*
docker compose up -d
```
