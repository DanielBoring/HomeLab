#!/usr/bin/env python3
"""Save channel 2's firmware baseline before assigning it to Brisa."""

import json
import os
from pathlib import Path

controllers = [
    path
    for path in Path('/sys/class/hwmon').glob('hwmon*')
    if (path / 'name').is_file()
    and (path / 'name').read_text().strip() == 'it8613'
]
if len(controllers) != 1:
    raise SystemExit('Expected exactly one IT8613 controller. Recheck discovery.')

controller = controllers[0]
mode = int((controller / 'pwm2_enable').read_text().strip())
pwm = int((controller / 'pwm2').read_text().strip())
if mode != 2:
    raise SystemExit(f'Expected firmware automatic mode 2; found {mode}.')
if not 0 <= pwm <= 255:
    raise SystemExit(f'Unexpected PWM value: {pwm}')

baseline = {
    'controller': 'it8613',
    'channel': 2,
    'pwm': pwm,
    'pwm_enable': mode,
    'kernel': os.uname().release,
}
destination = Path('/mnt/SSD/Containers/brisa/firmware-pwm2-baseline.json')
try:
    descriptor = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
except FileExistsError:
    raise SystemExit(f'Baseline already exists at {destination}; inspect it before continuing.')

with os.fdopen(descriptor, 'w') as output:
    json.dump(baseline, output, indent=2)
    output.write('\n')

print(json.dumps(baseline, indent=2))
print(f'Saved baseline: {destination}')
