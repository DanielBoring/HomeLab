# Tailscale

Runs a Tailscale node inside a container, advertising subnet routes and acting as an exit node for your tailnet.

https://tailscale.com/docs/features/containers/docker

## Overview

| Setting | Value |
|---|---|
| Image | `tailscale/tailscale:latest` |
| Network mode | Dedicated Docker bridge network with `net_admin` + `/dev/net/tun` |
| Exit node | Enabled (`--advertise-exit-node`) |
| Subnet routes | `10.0.0.0/20` (configurable) |
| State | `/mnt/SSD/Containers/tailscale` |

## Prerequisites

- A Tailscale account and tailnet
- An auth key from the [Tailscale admin console](https://login.tailscale.com/admin/settings/keys)
- `/dev/net/tun` available on the host (standard on Linux)
- Upstream DNS servers `10.0.6.2` and `10.0.6.3` reachable from the Docker host, or adjust the `dns:` entries in `compose.yaml`

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

First inspect the node's status and follow the supported Tailscale reauthentication flow. Do not routinely delete state: it contains the node identity and registration.

If a deliberate identity reset is necessary, arrange alternative host access first. Stop the stack and preserve the complete directory in a protected backup rather than deleting it. Recreate the required directory with its original ownership before redeployment, then reauthenticate and review the new identity's approvals/routes in the admin console. The reset can interrupt remote access and may register a different node.

```bash
docker compose down
mv /mnt/SSD/Containers/tailscale "/mnt/SSD/Containers/tailscale.pre-reset-$(date +%Y%m%d-%H%M%S)"
```

Do not start the stack until directory preparation, an appropriate authentication method, and a rollback/access plan are ready. Keep the preserved state private.
