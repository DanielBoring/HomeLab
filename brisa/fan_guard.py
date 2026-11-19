#!/usr/bin/env python3
"""Supervise stock Brisa and restore the saved IT8613 channel-2 baseline."""

import argparse
import contextlib
import fcntl
import json
import os
import signal
import sqlite3
import subprocess
import sys
import threading
import time
import uuid
from pathlib import Path

FAN_ID = 'hwmon-pwm-it87.2608/pwm2'
DEFAULT_APP = ['uvicorn', 'app.main:app', '--host', '0.0.0.0', '--port', '9595']


class GuardError(RuntimeError):
    pass


def log(event, **fields):
    print(json.dumps({'event': event, **fields}), flush=True)


def status(path, state, **fields):
    temporary = path.with_name(f'{path.name}.{os.getpid()}.tmp')
    temporary.write_text(json.dumps({
        'state': state, 'updated_at': time.time(), 'pid': os.getpid(), **fields,
    }) + '\n')
    os.replace(temporary, path)


def load_baseline(data, kernel=None):
    baseline = json.loads((data / 'firmware-pwm2-baseline.json').read_text())
    if (
        baseline.get('controller') != 'it8613'
        or baseline.get('channel') != 2
        or baseline.get('pwm_enable') != 2
        or baseline.get('kernel') != (kernel or os.uname().release)
        or type(baseline.get('pwm')) is not int
        or not 0 <= baseline['pwm'] <= 255
    ):
        raise GuardError('Baseline does not match the controller, kernel, or automatic mode.')
    return baseline


def find_controller(root):
    controllers = [
        path for path in root.glob('hwmon*')
        if (path / 'name').is_file()
        and (path / 'name').read_text().strip() == 'it8613'
    ]
    if len(controllers) != 1:
        raise GuardError(f'Expected one IT8613 controller; found {len(controllers)}.')
    controller = controllers[0]
    if not all((controller / name).is_file() for name in ('pwm2', 'pwm2_enable', 'fan2_input')):
        raise GuardError('Expected channel-2 controls are unavailable.')
    return controller


def readings(controller):
    return {
        'pwm': int((controller / 'pwm2').read_text()),
        'pwm_enable': int((controller / 'pwm2_enable').read_text()),
        'rpm': int((controller / 'fan2_input').read_text()),
    }


def restore(controller, baseline):
    before = readings(controller)
    if before['pwm'] == baseline['pwm'] and before['pwm_enable'] == 2:
        return False
    try:
        (controller / 'pwm2_enable').write_text('1\n')
        (controller / 'pwm2').write_text(f"{baseline['pwm']}\n")
        if int((controller / 'pwm2').read_text()) != baseline['pwm']:
            raise GuardError('Saved PWM write did not read back in manual mode.')
    finally:
        (controller / 'pwm2_enable').write_text('2\n')
    after = readings(controller)
    # Firmware may legitimately change live duty after automatic mode resumes.
    if after['pwm_enable'] != 2:
        raise GuardError(f'Baseline restoration readback failed: {after}')
    log('baseline-restored', saved_pwm=baseline['pwm'], before=before, after=after)
    return True


def take_lock(data):
    descriptor = os.open(data / 'fan-control.lock', os.O_RDWR | os.O_CREAT, 0o600)
    try:
        fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        os.close(descriptor)
        return None
    except BaseException:
        os.close(descriptor)
        raise
    return descriptor


def release_lock(descriptor):
    # Closing, rather than explicitly unlocking, preserves a child's inherited lock.
    os.close(descriptor)


def target_settings(data):
    config = json.loads((data / 'config.json').read_text())
    active = any(
        item.get('fan_id') == FAN_ID and item.get('backend') == 'hwmon-pwm'
        for item in config.get('fan_configs', [])
    )
    interval = float(config.get('settings', {}).get('interval_seconds', 60))
    if not interval > 0 or not interval < 86400:
        raise GuardError('Invalid Brisa polling interval.')
    return active, interval


def latest_control_record(data):
    uri = (data / 'history.db').resolve().as_uri() + '?mode=ro'
    with contextlib.closing(sqlite3.connect(uri, uri=True, timeout=1)) as connection:
        return connection.execute(
            'SELECT rowid, ts FROM fan_readings WHERE fan_id = ? ORDER BY rowid DESC LIMIT 1',
            (FAN_ID,),
        ).fetchone()


class ProgressWatchdog:
    def __init__(self, now):
        self.last_record = None
        self.last_progress = now

    def stalled(self, active, record, now, timeout):
        if not active:
            self.last_record = None
            self.last_progress = now
            return False
        if record is not None and record != self.last_record:
            self.last_record = record
            self.last_progress = now
        return now - self.last_progress > timeout


def terminate_child(child, grace):
    if child.poll() is not None:
        return
    try:
        os.killpg(child.pid, signal.SIGTERM)
        # A stopped process must resume to handle its pending termination signal.
        os.killpg(child.pid, signal.SIGCONT)
    except ProcessLookupError:
        pass
    try:
        child.wait(timeout=grace)
    except subprocess.TimeoutExpired:
        os.killpg(child.pid, signal.SIGKILL)
        child.wait(timeout=5)


def supervise(args, stop):
    state_file = args.data_dir / 'brisa-supervisor-status.json'
    descriptor = None
    baseline = None
    controller = None
    child = None
    result = 0
    previous_error = None
    generation = None
    try:
        while not stop.is_set():
            try:
                baseline = load_baseline(args.data_dir)
                controller = find_controller(args.hwmon_root)
                descriptor = take_lock(args.data_dir)
                if descriptor is not None:
                    break
                status(state_file, 'waiting-for-lock')
            except (OSError, ValueError, GuardError) as error:
                detail = str(error)
                status(state_file, 'waiting-for-hardware', detail=detail)
                if detail != previous_error:
                    log('startup-wait', detail=detail)
                    previous_error = detail
            stop.wait(args.poll)
        if stop.is_set():
            return 0

        # Always establish the authoritative baseline before a new Brisa process.
        generation = uuid.uuid4().hex
        status(args.data_dir / 'fan-control-owner.json', 'owned', generation=generation)
        restore(controller, baseline)
        child = subprocess.Popen(
            args.app or DEFAULT_APP,
            pass_fds=(descriptor,),
            start_new_session=True,
        )
        log('brisa-started', child_pid=child.pid)
        watchdog = ProgressWatchdog(time.monotonic())
        while child.poll() is None and not stop.is_set():
            detail = None
            try:
                active, interval = target_settings(args.data_dir)
                record = latest_control_record(args.data_dir) if active else None
            except (OSError, ValueError, GuardError, sqlite3.Error) as error:
                active, interval, record = True, 10, None
                detail = str(error)
            timeout = max(args.stall_timeout, interval * 3)
            if watchdog.stalled(active, record, time.monotonic(), timeout):
                status(state_file, 'loop-stalled', child_pid=child.pid, detail=detail)
                log('control-loop-stalled', timeout=timeout, detail=detail)
                result = 1
                break
            status(
                state_file, 'running', child_pid=child.pid,
                active=active, last_record=record, detail=detail,
            )
            stop.wait(args.poll)
        if not stop.is_set() and child.poll() is not None:
            log('brisa-exited', returncode=child.returncode)
            result = 1
    except (OSError, ValueError, GuardError, subprocess.SubprocessError) as error:
        log('supervisor-error', detail=str(error))
        result = 1
    finally:
        try:
            if child is not None:
                terminate_child(child, args.shutdown_grace)
            if descriptor is not None and baseline is not None and controller is not None:
                restore(controller, baseline)
                status(args.data_dir / 'fan-control-owner.json', 'released', generation=generation)
            status(state_file, 'stopped', result=result)
        finally:
            if descriptor is not None:
                release_lock(descriptor)
    return result


def watch(args, stop):
    state_file = args.data_dir / 'brisa-guard-status.json'
    previous_state = None
    while not stop.is_set():
        descriptor = None
        try:
            baseline = load_baseline(args.data_dir)
            descriptor = take_lock(args.data_dir)
            if descriptor is None:
                current = 'brisa-owned'
            else:
                controller = find_controller(args.hwmon_root)
                owner_file = args.data_dir / 'fan-control-owner.json'
                owner = json.loads(owner_file.read_text()) if owner_file.exists() else {}
                # A released lease permits firmware to vary duty freely. A dead
                # owner's unreleased lease needs one complete restoration.
                if owner.get('state') != 'released' or readings(controller)['pwm_enable'] != 2:
                    restore(controller, baseline)
                    status(owner_file, 'released', generation=owner.get('generation'))
                current = 'firmware'
            status(state_file, current)
            if current != previous_state:
                log('guard-state', state=current)
                previous_state = current
        except (OSError, ValueError, GuardError) as error:
            detail = str(error)
            status(state_file, 'waiting-for-hardware', detail=detail)
            if detail != previous_state:
                log('guard-wait', detail=detail)
                previous_state = detail
        finally:
            if descriptor is not None:
                release_lock(descriptor)
        stop.wait(args.poll)
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=('run', 'watch'))
    parser.add_argument('--data-dir', type=Path, default=Path('/data'))
    parser.add_argument('--hwmon-root', type=Path, default=Path('/sys/class/hwmon'))
    parser.add_argument('--poll', type=float, default=2)
    parser.add_argument('--stall-timeout', type=float, default=60)
    parser.add_argument('--shutdown-grace', type=float, default=12)
    parser.add_argument('--app', nargs=argparse.REMAINDER)
    args = parser.parse_args()
    if not all(value > 0 for value in (args.poll, args.stall_timeout, args.shutdown_grace)):
        parser.error('Polling, stall, and shutdown intervals must be positive.')
    if not args.data_dir.is_dir():
        parser.error('The shared data directory must already exist.')
    stop = threading.Event()
    signal.signal(signal.SIGTERM, lambda *_: stop.set())
    signal.signal(signal.SIGINT, lambda *_: stop.set())
    return supervise(args, stop) if args.mode == 'run' else watch(args, stop)


if __name__ == '__main__':
    sys.exit(main())
