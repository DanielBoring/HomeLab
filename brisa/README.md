# Brisa

[Brisa](https://github.com/brunoorsolon/brisa) supplies a web dashboard, temperature curves, manual output overrides, and history for the fan controller on the TrueNAS host. This stack targets the verified SYS FAN2 front-fan pair in a 45HomeLab HL8 with a Minisforum BD790i X3D motherboard.

The HomeLab service directory, container, and Portainer stack are named `brisa`. The startup loader is `/mnt/SSD/Containers/brisa/load-it87.sh`, and Brisa stores its configuration and history in that same directory. The compiled module remains under `/mnt/SSD/Containers/it8613e-fan-control/modules`.

| Component | Responsibility |
|---|---|
| Host `it87` module | Expose IT8613E temperature, RPM, and PWM interfaces through Linux hwmon |
| Brisa container | Read available sensors, apply configured curves, and provide the dashboard |
| TrueNAS Post Init task | Load the matching saved module after boot |

The image is pinned directly in [compose.yaml](compose.yaml), following the repository's [image update policy](../README.md#image-updates). The selected registry digest identifies Brisa 1.0.2, source revision `512d7b2814797610bcc44e21cd92db79fe3cf7f6`. An image-label version does not establish a matching registry tag, so the reference uses the verified digest.

## Current verification

- The community module was built and loaded on TrueNAS 25.10.7, kernel `6.12.105-production+truenas`.
- All six HDD temperatures are readable. A physical test verified `pwm2` as SYS FAN2, with RPM increasing from 1,275 to 1,753 before returning to 1,264 after restoration.
- The module and executable loader are saved on the SSD pool. An enabled Post Init task is registered in the portal with a 30-second timeout.
- The relocated loader at `/mnt/SSD/Containers/brisa/load-it87.sh` passed its syntax check and reported the available controller. A subsequent API query verified task ID 2 with that exact saved path, POSTINIT timing, enabled true, and timeout 30 seconds.
- Brisa deployment, automatic curves, failure behavior, and clean-boot loading remain pending operational verification.

## Host prerequisites

These are on the **TrueNAS Docker host**, independently of Portainer's Git checkout.

```text
/mnt/SSD/Containers/it8613e-fan-control/
  modules/
    6.12.105-production+truenas/
      it87.ko

/mnt/SSD/Containers/brisa/
  load-it87.sh
  config.json         # created by Brisa
  history.db          # created by Brisa
```

The `brisa` directory must exist before deploying. `create_host_path: false` makes a missing directory a deployment error instead of silently creating a new data location. The data directory is already prepared on the target host.

The container needs a host driver exposing the IT8613 controls and the expected temperature sensors. This Compose stack does not build or load kernel modules. Privileged mode and the writable `/sys` bind follow the upstream motherboard-PWM deployment requirements. The dashboard has no built-in authentication in this Brisa version, so this stack publishes it on the configured LAN address. No domain name, Traefik route, or external Docker network is required.

### Preparing another copy of the tested driver

The existing NAS preparation is complete. [load-it87.sh](load-it87.sh) is the standalone, source-controlled startup loader. [scripts/prepare-driver.sh](scripts/prepare-driver.sh) verifies the exact tested module checksum and kernel match, copies the module, installs that loader with mode 0750, and prepares the application directory. Run host commands on TrueNAS.

From a repository checkout on TrueNAS, if file preparation is needed and the tested build artifact still exists:

```bash
sudo bash brisa/scripts/prepare-driver.sh \
  /tmp/it87-test.JpM0cX/driver/it87.ko
```

The script does not register startup tasks or write PWM settings. Its fixed checksum intentionally accepts the artifact already tested. A rebuilt module needs its own provenance and hardware validation before updating that checksum.

In the TrueNAS portal, use **System → Advanced Settings → Init/Shutdown Scripts** to inspect or add this task. Edit the existing matching entry on the target NAS rather than creating a duplicate.

| Field | Value |
|---|---|
| Description | IT8613E Fan Control — Load Driver |
| Type | Script |
| Script | `/mnt/SSD/Containers/brisa/load-it87.sh` |
| When | Post Init |
| Enabled | Checked |
| Timeout | 30 seconds |

### Updating the loader separately

After reviewing a loader change and updating a HomeLab checkout on TrueNAS, run these commands from the repository root. For the first relocation, update the existing portal task's Script field to the new destination after the check succeeds:

```bash
bash -n brisa/load-it87.sh
sudo install -d -m 0750 /mnt/SSD/Containers/brisa
sudo install -m 0750 brisa/load-it87.sh \
  /mnt/SSD/Containers/brisa/load-it87.sh
sudo bash /mnt/SSD/Containers/brisa/load-it87.sh
```

This checks the current controller or loads the saved module if necessary. A later reboot verifies its startup path. Portainer updates the application stack; it does not automatically copy this host script into the portal's configured location. The local `.gitattributes` keeps shell scripts in LF format for Linux.

If no HomeLab checkout is available on TrueNAS yet, the existing installed loader can be copied from `/mnt/SSD/Containers/it8613e-fan-control/load-it87.sh` to the new destination with `install -m 0750`, followed by the same Bash syntax and runtime checks. The loader locates modules through its explicit module directory, so changing its own location requires no module rebuild.

## Deploy through Portainer from Git

Once these files have been committed and pushed to the selected Git reference:

1. Select the **TrueNAS** environment and open **Stacks → Add stack → Repository**.
2. Set the stack name to **`brisa`**.
3. Set the repository URL to `https://github.com/DanielBoring/HomeLab` and choose the Git reference containing these files, normally `refs/heads/main` after merging.
4. Set the Compose path to **`brisa/compose.yaml`**.
5. Supply the values from [.env.example](.env.example) as Portainer stack variables, or use the matching defaults embedded in Compose.
6. Deploy the stack and inspect its container status and logs.

The defaults expose the dashboard at **http://10.0.5.10:9595**. Portainer stack variables belong to that deployment; a CLI run does not automatically inherit them. Keep using the same stack/project name when managing it from the command line. If an initial Web-editor stack already exists, use that same stack when changing its management source through the supported Portainer workflow.

## CLI validation and deployment

From the repository root on a Linux Docker host:

```bash
cp brisa/.env.example brisa/.env

docker compose --env-file brisa/.env \
  -p brisa -f brisa/compose.yaml config --quiet

docker compose --env-file brisa/.env \
  -p brisa -f brisa/compose.yaml up -d
```

The repository ignores the private `.env` file. Windows can validate this configuration, but runtime deployment targets the prepared TrueNAS Linux host and its hardware interfaces.

## First-run checks

```bash
sudo docker ps --filter name=brisa \
  --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}'

sudo docker logs --tail 80 brisa

curl -fsS http://10.0.5.10:9595/api/config | python3 -m json.tool
```

Leave fan assignments empty during discovery. Confirm the six intended HDD sensors, the CPU sensor, and the IT8613 channels in **Sensors & Fans**. Identify drives using their persistent IDs. The verified output for this machine is `pwm2`; the single tachometer on its Y-splitter cannot independently report both fan motors.

The health check proves API responsiveness. It does not establish successful PWM writes, loop progress, complete sensor coverage, or adequate cooling. The upstream application leaves motherboard PWM outputs at their last setting after an abrupt exit. Verify graceful release, crash/restart behavior, missing sensors, and measured fan response before relying on unattended control. A container restart policy alone does not address a stalled control loop.

A reboot at an appropriate time must verify the host loader, sensor rediscovery, and application startup. Keep the initial fan assignments empty for this test so the firmware curve remains the baseline.

## Recovery, backup, and updates

Preserve `/mnt/SSD/Containers/brisa` for the loader, configuration, and history. Stop Brisa before taking a simple file copy of its SQLite database, or use an SQLite-consistent backup method. Confirm actual control mode and RPM after stopping the application; graceful release on this IT8613 still needs physical verification.

The saved external module is kernel-specific. After a TrueNAS kernel change, check for native support or build and validate a matching module. The loader reports a missing matching artifact. Registry image updates and host-driver updates have separate lifecycles. Review changes and back up application state before changing the literal image pin.

## Community credits

- [frankcrawford/it87](https://github.com/frankcrawford/it87) provides the community IT8613E-capable driver. Tested source commit is `bc06d3488439e5fcd725c1bdcfcac994d6d95cac`.
- [brunoorsolon/brisa](https://github.com/brunoorsolon/brisa) provides the controller and dashboard used by this stack.
- [tarasverq/ugreen-fan](https://github.com/tarasverq/ugreen-fan) supplied a reference for building the driver against TrueNAS kernel headers inside Docker and demonstrates related temperature-policy and recovery approaches.

This directory packages those components for the verified HL8/BD790i X3D hardware and the HomeLab Portainer workflow. Driver support and existing dashboard features belong to their upstream projects.
