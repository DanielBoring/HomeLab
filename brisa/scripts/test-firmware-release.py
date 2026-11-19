#!/usr/bin/env python3
"""Stop Brisa, record its release behavior, and restore the saved firmware baseline."""

import json
import os
import subprocess
import time
from pathlib import Path

baseline_path = Path('/mnt/SSD/Containers/brisa/firmware-pwm2-baseline.json')
baseline = json.loads(baseline_path.read_text())
if (
    baseline.get('controller') != 'it8613'
    or baseline.get('channel') != 2
    or baseline.get('pwm_enable') != 2
    or baseline.get('kernel') != os.uname().release
    or type(baseline.get('pwm')) is not int
    or not 0 <= baseline['pwm'] <= 255
):
    raise SystemExit('The baseline does not match this controller, kernel, or expected mode.')

controllers = [
    path for path in Path('/sys/class/hwmon').glob('hwmon*')
    if (path / 'name').is_file()
    and (path / 'name').read_text().strip() == 'it8613'
]
if len(controllers) != 1:
    raise SystemExit('Expected exactly one IT8613 controller.')
controller = controllers[0]

def readings():
    return {
        'pwm': int((controller / 'pwm2').read_text().strip()),
        'pwm_enable': int((controller / 'pwm2_enable').read_text().strip()),
        'rpm': int((controller / 'fan2_input').read_text().strip()),
    }

before = readings()
if before['pwm_enable'] != 1:
    raise SystemExit('Expected Brisa to own channel 2 in manual mode 1 before this test.')
print('Before stopping Brisa:', json.dumps(before), flush=True)
subprocess.run(['docker', 'stop', '-t', '30', 'brisa'], check=True, timeout=45)
state = subprocess.check_output(
    ['docker', 'inspect', '--format', '{{.State.Running}} {{.State.ExitCode}}', 'brisa'],
    text=True,
).split()
if len(state) != 2 or state[0] != 'false':
    raise SystemExit('Brisa is still running; firmware restoration was not attempted.')
print('Container exit code:', state[1], flush=True)

try:
    time.sleep(5)
    print('After Brisa release:', json.dumps(readings()), flush=True)
finally:
    try:
        (controller / 'pwm2_enable').write_text('1\n')
        (controller / 'pwm2').write_text(f"{baseline['pwm']}\n")
        if int((controller / 'pwm2').read_text()) != baseline['pwm']:
            raise SystemExit('Saved PWM did not read back while in manual mode.')
    finally:
        (controller / 'pwm2_enable').write_text('2\n')

time.sleep(5)
restored = readings()
print('After baseline restoration:', json.dumps(restored), flush=True)
if restored['pwm_enable'] != 2:
    raise SystemExit('Automatic mode was not restored. Inspect controller state.')
print('Firmware may adjust the live PWM after automatic control resumes.', flush=True)
print('Baseline restored. Brisa remains stopped for review.', flush=True)
