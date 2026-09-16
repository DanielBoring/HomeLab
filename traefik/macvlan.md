# Macvlan Host Isolation

## The Problem

Traefik runs on a Docker macvlan network (`10.0.5.0/24`, parent `enp8s0`, IP `10.0.5.5`). TrueNAS (the Docker host) cannot communicate with containers on its own macvlan networks — this is a deliberate Linux kernel macvlan driver limitation.

The macvlan driver drops all frames exchanged between the parent interface (`enp8s0`) and its macvlan children, regardless of IP or subnet configuration. Even though TrueNAS has `10.0.5.10` on `enp8s0` and both IPs are in the same `/24`, the ARP reply from the Traefik container is dropped by the driver before it reaches the host network stack.

**Symptom:** Tailscale remote access times out. TrueNAS is the Tailscale subnet router — incoming Tailscale traffic arrives at TrueNAS and is forwarded toward `10.0.5.5`, but the kernel drops it. Traefik never sees the request, so the `lan-only` IP allowlist is never even reached.

**Not the cause:** The `lan-only` middleware already includes `100.64.0.0/10` (Tailscale CGNAT range) and `10.0.0.0/20` (LAN).

## Why the Shim Works

A macvlan shim is a second macvlan interface created on TrueNAS, also attached to `enp8s0`. Unlike the parent interface, macvlan children in bridge mode can communicate with each other. The shim gives TrueNAS a child-side presence on the macvlan network, so traffic flows child→child (allowed) instead of parent→child (blocked).

## Fix

### Step 1 — Test manually (SSH into TrueNAS)

```bash
ip link add macvlan-shim link enp8s0 type macvlan mode bridge
ip addr add 10.0.5.2/32 dev macvlan-shim
ip link set macvlan-shim up
ip route add 10.0.5.0/24 dev macvlan-shim
```

Verify with `ping 10.0.5.5` from a remote Tailscale device. Should succeed immediately.

The shim IP uses `/32` (not `/24`) to avoid conflicting with Docker's connected route for `10.0.5.0/24`. The explicit route covers the full subnet.

### Step 2 — Persist via TrueNAS Init Script

TrueNAS Scale → **System → Advanced → Init/Shutdown Scripts → Add**

| Field | Value |
|---|---|
| Type | Post Init |
| Command | `ip link add macvlan-shim link enp8s0 type macvlan mode bridge; ip addr add 10.0.5.2/32 dev macvlan-shim; ip link set macvlan-shim up; ip route add 10.0.5.0/24 dev macvlan-shim` |

Runs after boot and Docker start. The `;` separators allow later commands to run even if an interface already exists from a previous run.

## Notes

- Confirm the parent interface name with `ip addr show` on TrueNAS — `enp8s0` is what's in `compose.yaml` but verify it matches.
- If TrueNAS's `10.0.5.10` address were on a **different physical NIC** connected to the same switch segment (not `enp8s0`), traffic would travel through the switch and bypass the macvlan driver — no shim needed. The shim is only required because the host IP is on the same parent interface.
- This issue only affects host→macvlan traffic. Other hosts on the LAN can reach `10.0.5.5` normally via the switch.
