# Open WebUI

Open WebUI running as a Docker container on TrueNAS, connected to a remote Ollama instance.

## Architecture

```
TrueNAS (Docker)               Gaming PC / Remote Host
┌──────────────────────────┐   ┌─────────────────────┐
│  Traefik → Open WebUI    │──▶│  Ollama  :11434     │
│  :8080 (internal)        │   │  (OLLAMA_BASE_URL)  │
└──────────────────────────┘   └─────────────────────┘
        ▲
  https://${OPENWEBUI_DOMAIN}
```

## Prerequisites

Create the data directory before deploying:

```bash
mkdir -p /mnt/SSD/Containers/openwebui
```

## Quick Start

```bash
cp example.env .env
# Edit .env — set OLLAMA_BASE_URL and OPENWEBUI_DOMAIN
docker compose up -d
```

Then open `https://<OPENWEBUI_DOMAIN>`. DNS must resolve the domain to Traefik (`10.0.5.5`) before the UI is reachable.

## Configuration

| Variable          | Description                        | Example                                  |
|-------------------|------------------------------------|------------------------------------------|
| `OLLAMA_BASE_URL` | URL of the remote Ollama instance  | `http://<ollama-host>:11434`             |
| `OPENWEBUI_DOMAIN`| Hostname Traefik routes to the UI  | `openwebui.yourdomain.com`               |

## Ollama Host Requirements

The Ollama instance must be reachable from the TrueNAS host over the network.

### 1. Listen on all interfaces

By default Ollama only binds to `127.0.0.1`. Set `OLLAMA_HOST` to make it accept remote connections:

**Windows — system environment variable (persistent):**
```powershell
[System.Environment]::SetEnvironmentVariable("OLLAMA_HOST", "0.0.0.0", "Machine")
# Restart the Ollama service/app after setting this
```

**Windows — per-session (temporary):**
```powershell
$env:OLLAMA_HOST = "0.0.0.0"
ollama serve
```

**Linux/macOS:**
```bash
OLLAMA_HOST=0.0.0.0 ollama serve
```

### 2. Open port 11434 in the firewall

**Windows Defender (PowerShell, run as Administrator):**
```powershell
New-NetFirewallRule -DisplayName "Ollama" -Direction Inbound -Protocol TCP -LocalPort 11434 -Action Allow
```

### 3. Verify connectivity

From the TrueNAS host:
```bash
curl http://<ollama-host>:11434/api/tags
```

A JSON response listing available models confirms the connection is working.

## Changing the Ollama URL After Deployment

You can update the Ollama connection without restarting the container via the UI:

**Settings > Admin Settings > Connections > Ollama API**

Changes take effect immediately.
