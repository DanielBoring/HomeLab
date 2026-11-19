# Automatic firmware restoration and failure validation

## Why this change exists

The stock Brisa 1.0.2 shutdown test on this IT8613E returned channel 2 from manual mode to automatic mode, but retained raw PWM 186. Restoring the complete saved baseline required PWM 150 and mode 2. The observed RPMs were 1,412 while Brisa controlled the fans, 1,448 after mode-only release, and 1,264 after full restoration.

The saved baseline is `/mnt/SSD/Containers/brisa/firmware-pwm2-baseline.json`. It identifies controller `it8613`, channel 2, PWM 150, mode 2, and kernel `6.12.105-production+truenas`. This change uses that durable baseline rather than recapturing a possibly manual state after a crash.

## The two processes

The stack continues using the exact official Brisa image. [fan_guard.py](../fan_guard.py) is mounted as an inline Compose config. The application service runs it in `run` mode, and companion service `brisa-fan-guard` runs it in `watch` mode.

The supervisor waits for a valid matching baseline and the host IT8613 interfaces, establishes the baseline, then starts the original Uvicorn application. On normal termination or child-process failure, it waits for the application to exit and restores both saved values. The application and supervisor share an inherited Linux file lock for their entire lifetime.

The companion attempts that same lock every two seconds. While Brisa owns it, the companion cannot write PWM settings. When the whole Brisa container is killed and all holders disappear, the companion acquires the lock and restores the baseline. If Docker restarts Brisa first, its supervisor establishes the baseline before launching a new application process. Neither process uses the Docker socket.

An ownership record distinguishes a released controller from an interrupted owner. After restoring and returning automatic mode, the companion leaves firmware free to vary its live PWM output; it does not repeatedly force PWM 150. Restoration verifies the saved PWM while still in manual mode, then verifies automatic mode. A later firmware-driven duty change is valid.

The supervisor monitors actual fan-history progress in `/data/history.db` for the verified front-fan ID. If the configured channel has no new successful history record for at least 60 seconds, or three configured polling intervals if longer, it terminates the app and restores the baseline. Docker's existing restart policy then handles the supervisor's nonzero exit. The monitor uses monotonic elapsed time and changing database records, so a wall-clock correction alone does not establish a stall.

The baseline and history must remain available in the shared data directory. A missing controller or an invalid/mismatched baseline prevents the application from starting; logs and guard health indicate the waiting state. A kernel upgrade therefore requires a matching driver and a freshly validated baseline.

## Source and generated Compose config

`fan_guard.py` is authoritative. The Compose file contains its generated inline copy so deployment does not depend on relative host bind mounts into Portainer's Git checkout. The repository already uses inline Compose configs for Loki. Regenerate and check with:

```bash
python3 brisa/scripts/render-guard-config.py
python3 brisa/scripts/render-guard-config.py --check
docker compose --env-file brisa/.env.example -p brisa \
  -f brisa/compose.yaml config --quiet
python3 -B -m unittest discover -s brisa/tests -v
```

Run lifecycle tests on Linux. They use a temporary fake hwmon tree, temporary SQLite history, and a synthetic application process. Thirteen cases passed in WSL, including restoration after mode-only release, a failed PWM write still requesting automatic mode, baseline/controller validation, normal shutdown, child crash, stalled child, inherited-lock exclusion, whole-container-like process loss, permitting subsequent firmware duty changes, boot-time controller delay, and missing baseline. These are software tests; they do not substitute for the NAS checks below.

## Deploy and verify readiness

For the first deployment of this protection, stop the existing stock Brisa container before publishing/redeploying the change. The old command does not participate in the new ownership lock. Then commit/push the reviewed changes and redeploy the existing Portainer Git stack from `brisa/compose.yaml`. The stack now contains containers `brisa` and `brisa-fan-guard`. The existing Post Init task and host module location stay in use.

```bash
sudo docker stop -t 30 brisa
```

Run on TrueNAS:

```bash
sudo docker ps --filter label=com.docker.compose.project=brisa \
  --format 'table {{.Names}}\t{{.Status}}'
sudo docker logs --tail 30 brisa
sudo docker logs --tail 30 brisa-fan-guard
sudo cat /mnt/SSD/Containers/brisa/brisa-supervisor-status.json
sudo cat /mnt/SSD/Containers/brisa/brisa-guard-status.json
```

Expect a running Brisa child, a healthy companion in `brisa-owned` state, and the already-saved HDD curve. Verify actual mode/PWM/RPM as well as API readiness.

Use this read-only snapshot block before and after each test:

```bash
sudo bash <<'EOF'
set -euo pipefail
for sensor in /sys/class/hwmon/hwmon*; do
    [ -f "$sensor/name" ] || continue
    [ "$(cat "$sensor/name")" = it8613 ] || continue
    printf 'Controller: %s\n' "$sensor"
    for attribute in pwm2 pwm2_enable fan2_input; do
        printf '%s = ' "$attribute"
        cat "$sensor/$attribute"
    done
done
EOF
```

## 1. Normal stop

```bash
sudo docker stop -t 30 brisa
sleep 5
```

Run the snapshot block. Expect automatic mode 2 without manually writing either attribute. In the same conditions as the previous test, raw PWM should initially be 150 and RPM should settle near 1,264. Firmware is free to adjust duty once automatic mode resumes. The companion should remain running. Check the Brisa log for `baseline-restored`, including `saved_pwm: 150` and successful automatic-mode readback.

Restart for the following checks:

```bash
sudo docker start brisa
```

## 2. Application-process crash

Once the supervisor status is fresh and the curve is active, kill only its application child:

```bash
sudo docker exec brisa python -c 'import json,os,signal; s=json.load(open("/data/brisa-supervisor-status.json")); os.kill(s["child_pid"],signal.SIGKILL)'
```

The supervisor should record the child failure, restore the baseline, and exit nonzero. Docker should restart the application container. Logs should show restoration followed by a fresh `brisa-started` event. On recovery, the configured HDD curve resumes; manual mode 1 is then expected.

## 3. Whole-container kill

For this test, temporarily disable Brisa's restart policy so the companion's restoration can be observed before the application returns:

```bash
sudo docker update --restart=no brisa
sudo docker kill --signal=KILL brisa
sleep 5
```

Run the snapshot block. Expect mode 2 and, at the previous test conditions, PWM 150, with the companion in `firmware` state. Check its `baseline-restored` event; subsequent automatic duty changes are valid. This tests the path that cannot run the application's or supervisor's cleanup code.

Restore the production policy and resume:

```bash
sudo docker update --restart=unless-stopped brisa
sudo docker start brisa
```

Restore the restart policy even if a test result differs, then investigate the actual mode and guard logs. The temporary policy change is not a Compose-file change.

## 4. Stalled application loop

With the app active, suspend only its child process:

```bash
sudo docker exec brisa python -c 'import json,os,signal; s=json.load(open("/data/brisa-supervisor-status.json")); os.kill(s["child_pid"],signal.SIGSTOP)'
```

Allow roughly 60–80 seconds with the configured ten-second polling interval. The supervisor should log `control-loop-stalled`, terminate/resume the stopped child so it can exit, restore the baseline, and exit nonzero. Docker should restart Brisa and the curve should resume. Check logs and fresh history; a responsive HTTP endpoint alone does not prove loop progress.

## 5. Reboot

After the stop and failure checks pass, restart the TrueNAS system through its portal at a suitable time for the other workloads. The restart is an intentional NAS-wide interruption.

After reconnecting, verify:

```bash
uname -r
sudo midclt call initshutdownscript.query '[["id","=",2]]'
sudo docker ps --filter label=com.docker.compose.project=brisa \
  --format 'table {{.Names}}\t{{.Status}}'
sudo docker logs --tail 40 brisa
sudo docker logs --tail 30 brisa-fan-guard
```

Confirm automatic IT8613 detection without manual `insmod`, both containers running, fresh HDD temperatures and fan history, and curve-driven physical output. If Docker starts the app before the module is available, its supervisor should show a waiting state and then start the app after the Post Init loader exposes the controller.

## Recovery and boundaries

If an outcome differs, stop `brisa`, keep the companion running, inspect its logs, and read actual PWM/mode/RPM. The saved baseline and the original manual restoration procedure remain the recovery reference. Reverting to the stock command requires removing the supervisor command/config and companion service from Compose; revalidate shutdown behavior afterward.

The protection covers channel 2 with its saved baseline. Adding another controlled fan requires a separate validated baseline and corresponding guard support. The existing Brisa maximum sensor still uses remaining members if one HDD temperature disappears; this change does not enforce complete six-drive coverage. Both guard processes still depend on the host kernel. A frozen whole OS or simultaneously killing all guard processes can leave the last output until software or firmware recovers.

## Operational results

Local software checks passed. Deployment of this guard, its actual NAS stop/failure tests, and the reboot test are pending execution evidence.

## References

- [Docker Compose inline configs](https://docs.docker.com/reference/compose-file/configs/)
- [Docker stop signals and timeout](https://docs.docker.com/reference/cli/docker/container/stop/)
- [Docker restart-policy updates](https://docs.docker.com/reference/cli/docker/container/update/)
- [Tested community driver source](https://github.com/frankcrawford/it87/blob/bc06d3488439e5fcd725c1bdcfcac994d6d95cac/it87.c)
