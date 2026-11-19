#!/usr/bin/env python3
"""Embed the canonical guard script as a portable inline Compose config."""

import argparse
from pathlib import Path

root = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--check', action='store_true')
args = parser.parse_args()
marker = '# Generated from fan_guard.py by scripts/render-guard-config.py.\n'
path = root / 'compose.yaml'
original = path.read_text(encoding='utf-8')
prefix = original.split(marker, 1)[0].rstrip() + '\n\n'
source = (root / 'fan_guard.py').read_text(encoding='utf-8').replace('$', '$$')
rendered = prefix + marker + 'configs:\n  brisa-fan-guard:\n    content: |\n'
rendered += ''.join('      ' + line if line.strip() else line for line in source.splitlines(True))
if args.check:
    if original != rendered:
        raise SystemExit('Compose guard content is stale. Run scripts/render-guard-config.py.')
    print('Compose guard content matches fan_guard.py.')
else:
    path.write_text(rendered, encoding='utf-8', newline='\n')
