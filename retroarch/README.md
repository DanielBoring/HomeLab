# RetroArch

RetroArch is an all-in-one emulator frontend that runs classic games across dozens of systems (NES, SNES, PS1, N64, GBA, arcade, and more) through a unified interface. This container runs it as a KasmVNC session accessible from any browser — no local install, no controller driver headaches on the client device.

GPU acceleration is wired up to the Intel Arc GPU for both rendering and VAAPI video encoding of the KasmVNC stream.

[https://docs.linuxserver.io/images/docker-retroarch/]

## Architecture

```
Browser (HTTPS) → Traefik (TLS termination) → retroarch:3000 (KasmVNC HTTP)
                                                      ↓
                                              Intel Arc GPU (VAAPI + EGL)
```

KasmVNC streams the RetroArch GUI to the browser. `/dev/dri` is passed through to the container, giving it access to the Intel Arc for both EGL rendering (`DRINODE`) and VAAPI hardware video encoding (`DRI_NODE`).

ROMs are mounted from the host into `/roms` inside the container. Configure the path in RetroArch under **Settings → Directory → File Browser / Start Directory**.

## Prerequisites

### Host directories

```sh
mkdir -p /mnt/SSD/Containers/retroarch
mkdir -p /mnt/Data/Media/ROMs
```

### Find the correct DRI render node

```sh
ls -la /dev/dri/
```

The Intel Arc render node is typically `/dev/dri/renderD128`. Set `INTEL_DRI_NODE` in `.env` to match. The full `/dev/dri` device tree is passed through so all nodes are available inside the container.

### DNS
Add a record for `retroarch.yourdomain.com` → `10.0.5.5` (Traefik).

## Quick Start

```sh
cp example.env .env
# Fill in RETROARCH_USER, RETROARCH_PASSWORD, verify INTEL_DRI_NODE
docker compose up -d
```

Navigate to `https://retroarch.yourdomain.com` and log in.

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `TZ` | `America/New_York` | Container timezone |
| `PUID` | `3001` | User ID for file permissions |
| `PGID` | `3001` | Group ID for file permissions |
| `RETROARCH_DOMAIN` | — | Public hostname for Traefik routing |
| `RETROARCH_USER` | — | KasmVNC basic auth username |
| `RETROARCH_PASSWORD` | — | KasmVNC basic auth password |
| `INTEL_DRI_NODE` | `/dev/dri/renderD128` | DRI render node for the Intel Arc GPU |
| `ROMS_PATH` | `/mnt/Data/Media/ROMs` | Host path to ROMs directory |

## ROMs Layout

RetroArch expects ROMs organized by system. A common convention:

```
/mnt/Data/Media/ROMs/
├── nes/
├── snes/
├── n64/
├── gba/
├── psx/
├── arcade/   ← MAME/FBNeo ROMs
└── bios/     ← BIOS files (scph1001.bin, etc.)
```

In RetroArch: **Settings → Directory → System / BIOS** → point to `/roms/bios`.

## Switching to Nvidia

If you replace the Intel Arc with an Nvidia GPU:

1. Install and configure `nvidia-container-toolkit` on TrueNAS:
   ```sh
   curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | sudo gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg
   curl -s -L https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list | \
     sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' | \
     sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list
   sudo apt-get update && sudo apt-get install -y nvidia-container-toolkit
   sudo nvidia-ctk runtime configure --runtime=docker
   sudo systemctl restart docker
   ```

2. Nvidia drivers **580+** are required. Check with `nvidia-smi`.

3. Set kernel parameters `nvidia-drm.modeset=1 nvidia_drm.fbdev=1` and reboot.

4. TrueNAS is headless — use a **dummy HDMI plug** so Nvidia DRM initializes without a real display.

5. In `compose.yaml`, swap the GPU config as indicated by the comments:
   - Remove the `devices` block
   - Uncomment the `deploy.resources.reservations.devices` block
   - Swap the active/commented environment variables for `DRINODE`, `DRI_NODE`, `NVIDIA_DRIVER_CAPABILITIES`, and `NVIDIA_VISIBLE_DEVICES`

6. In `.env`, rename `INTEL_DRI_NODE` to `NVIDIA_DRI_NODE` and set it to the correct render node (`ls -la /dev/dri/`).
