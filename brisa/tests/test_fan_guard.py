"""Linux tests use temporary hwmon files and a synthetic Brisa-like child."""

import json
import os
import signal
import sqlite3
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import fan_guard as guard


class Fixture(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='brisa-guard-test-')
        self.root = Path(self.temporary.name)
        self.data = self.root / 'data'
        self.hwmon = self.root / 'hwmon'
        self.data.mkdir()
        self.hwmon.mkdir()
        self.controller = self.hwmon / 'hwmon14'
        self.controller.mkdir()
        for name, value in {'name': 'it8613', 'pwm2': '150', 'pwm2_enable': '2', 'fan2_input': '1264'}.items():
            (self.controller / name).write_text(value + '\n')
        self.baseline = {
            'controller': 'it8613', 'channel': 2, 'pwm': 150,
            'pwm_enable': 2, 'kernel': os.uname().release,
        }
        self.baseline_path = self.data / 'firmware-pwm2-baseline.json'
        self.baseline_path.write_text(json.dumps(self.baseline))
        self.addCleanup(self.temporary.cleanup)

    def set_output(self, pwm, mode):
        (self.controller / 'pwm2').write_text(str(pwm))
        (self.controller / 'pwm2_enable').write_text(str(mode))


class BaselineTests(Fixture):
    def test_rejects_wrong_kernel_channel_mode_and_boolean_pwm(self):
        for key, value in [('kernel', 'other-kernel'), ('channel', 3), ('pwm_enable', 1), ('pwm', True)]:
            with self.subTest(key=key):
                bad = {**self.baseline, key: value}
                self.baseline_path.write_text(json.dumps(bad))
                with self.assertRaises(guard.GuardError):
                    guard.load_baseline(self.data)

    def test_rejects_ambiguous_controller(self):
        extra = self.hwmon / 'hwmon99'
        extra.mkdir()
        (extra / 'name').write_text('it8613')
        with self.assertRaises(guard.GuardError):
            guard.find_controller(self.hwmon)

    def test_full_restoration_after_mode_only_release(self):
        self.set_output(186, 2)
        self.assertTrue(guard.restore(self.controller, self.baseline))
        self.assertEqual(guard.readings(self.controller), {'pwm': 150, 'pwm_enable': 2, 'rpm': 1264})
        self.assertFalse(guard.restore(self.controller, self.baseline))

    def test_pwm_write_failure_still_requests_automatic_mode(self):
        self.set_output(186, 1)
        original = Path.write_text
        writes = []

        def write(path, text, *args, **kwargs):
            writes.append((path.name, text.strip()))
            if path.name == 'pwm2':
                raise OSError('simulated PWM write failure')
            return original(path, text, *args, **kwargs)

        with patch.object(Path, 'write_text', write):
            with self.assertRaises(OSError):
                guard.restore(self.controller, self.baseline)
        self.assertEqual(writes, [('pwm2_enable', '1'), ('pwm2', '150'), ('pwm2_enable', '2')])
        self.assertEqual((self.controller / 'pwm2_enable').read_text(), '2\n')

    def test_control_record_uses_selected_fan_only(self):
        with sqlite3.connect(self.data / 'history.db') as database:
            database.execute('CREATE TABLE fan_readings(ts INTEGER, fan_id TEXT)')
            database.execute('INSERT INTO fan_readings VALUES(?, ?)', (100, guard.FAN_ID))
            database.execute('INSERT INTO fan_readings VALUES(?, ?)', (101, 'other-fan'))
        self.assertEqual(guard.latest_control_record(self.data), (1, 100))

    def test_watchdog_requires_progress_and_ignores_wall_clock_direction(self):
        monitor = guard.ProgressWatchdog(0)
        self.assertFalse(monitor.stalled(True, (1, 100), 0, 5))
        self.assertTrue(monitor.stalled(True, (1, 100), 6, 5))
        self.assertFalse(monitor.stalled(True, (2, 90), 7, 5))
        self.assertFalse(monitor.stalled(False, None, 100, 5))
        self.assertFalse(monitor.stalled(True, None, 101, 5))


CHILD = '''
import json,signal,sqlite3,sys,time
from pathlib import Path
data,controller=map(Path,sys.argv[1:3])
signal.signal(signal.SIGTERM,lambda *_:sys.exit(0))
with sqlite3.connect(data/'history.db') as db:
    db.execute('CREATE TABLE IF NOT EXISTS fan_readings(ts INTEGER,fan_id TEXT)')
(controller/'pwm2_enable').write_text('1')
(controller/'pwm2').write_text('186')
while True:
    with sqlite3.connect(data/'history.db') as db:
        db.execute('INSERT INTO fan_readings VALUES(?,?)',(int(time.time()),'hwmon-pwm-it87.2608/pwm2'))
    time.sleep(.1)
'''


class LifecycleTests(Fixture):
    def setUp(self):
        super().setUp()
        (self.data / 'config.json').write_text(json.dumps({
            'settings': {'interval_seconds': .1},
            'fan_configs': [{'fan_id': guard.FAN_ID, 'backend': 'hwmon-pwm'}],
        }))
        self.child_path = self.root / 'synthetic_brisa.py'
        self.child_path.write_text(CHILD)
        self.processes = []
        self.child_ids = set()
        self.logs = []
        self.addCleanup(self.cleanup_processes)

    def cleanup_processes(self):
        for process in self.processes:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=3)
        for pid in self.child_ids:
            command = Path(f'/proc/{pid}/cmdline')
            try:
                if str(self.child_path).encode() in command.read_bytes():
                    os.killpg(pid, signal.SIGKILL)
            except (FileNotFoundError, ProcessLookupError):
                pass
        for log in self.logs:
            log.close()

    def start(self, mode):
        log = (self.root / f'{mode}-{len(self.processes)}.log').open('w+')
        self.logs.append(log)
        command = [
            sys.executable, str(ROOT / 'fan_guard.py'), mode,
            '--data-dir', str(self.data), '--hwmon-root', str(self.hwmon),
            '--poll', '.05', '--stall-timeout', '.8', '--shutdown-grace', '.3',
        ]
        if mode == 'run':
            command.extend(['--app', sys.executable, str(self.child_path), str(self.data), str(self.controller)])
        process = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT)
        self.processes.append(process)
        return process

    def wait_for(self, predicate, timeout=6):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            try:
                if predicate():
                    return
            except (OSError, ValueError, KeyError):
                pass
            time.sleep(.03)
        for file in self.root.glob('*.log'):
            print(file.read_text())
        self.fail('Timed out waiting for the expected state.')

    def wait_active(self):
        def active():
            state = json.loads((self.data / 'brisa-supervisor-status.json').read_text())
            self.child_ids.add(state['child_pid'])
            return state['state'] == 'running' and guard.readings(self.controller)['pwm_enable'] == 1
        self.wait_for(active)

    def child_pid(self):
        return json.loads((self.data / 'brisa-supervisor-status.json').read_text())['child_pid']

    def assert_restored(self):
        self.assertEqual(guard.readings(self.controller)['pwm'], 150)
        self.assertEqual(guard.readings(self.controller)['pwm_enable'], 2)

    def test_normal_stop_restores_full_baseline(self):
        process = self.start('run')
        self.wait_active()
        process.terminate()
        self.assertEqual(process.wait(timeout=5), 0)
        self.assert_restored()

    def test_child_crash_restores_before_supervisor_exit(self):
        process = self.start('run')
        self.wait_active()
        os.kill(self.child_pid(), signal.SIGKILL)
        self.assertEqual(process.wait(timeout=5), 1)
        self.assert_restored()

    def test_stopped_child_triggers_watchdog_and_restoration(self):
        process = self.start('run')
        self.wait_active()
        self.wait_for(lambda: guard.latest_control_record(self.data) is not None)
        os.kill(self.child_pid(), signal.SIGSTOP)
        self.assertEqual(process.wait(timeout=5), 1)
        self.assert_restored()
        self.assertIn('control-loop-stalled', next(self.root.glob('run-*.log')).read_text())

    def test_guard_waits_for_inherited_lock_then_recovers_whole_container_loss(self):
        companion = self.start('watch')
        supervisor = self.start('run')
        self.wait_active()
        child = self.child_pid()
        supervisor.kill()
        supervisor.wait(timeout=3)
        time.sleep(.2)
        # The child is still alive: the companion must not fight its PWM output.
        self.assertEqual(guard.readings(self.controller)['pwm_enable'], 1)
        os.killpg(child, signal.SIGKILL)
        self.wait_for(lambda: guard.readings(self.controller)['pwm_enable'] == 2)
        self.assert_restored()
        self.assertIsNone(companion.poll())

    def test_guard_leaves_firmware_duty_changes_after_release_alone(self):
        companion = self.start('watch')
        self.wait_for(lambda: (self.data / 'fan-control-owner.json').exists())
        # Simulate firmware legitimately increasing its automatic output.
        self.set_output(220, 2)
        time.sleep(.25)
        self.assertEqual(guard.readings(self.controller)['pwm'], 220)
        self.assertIsNone(companion.poll())

    def test_boot_waits_for_controller_before_starting_application(self):
        offline = self.hwmon / '_offline'
        self.controller.rename(offline)
        process = self.start('run')
        time.sleep(.2)
        self.assertIsNone(process.poll())
        self.assertEqual(json.loads((self.data / 'brisa-supervisor-status.json').read_text())['state'], 'waiting-for-hardware')
        offline.rename(self.controller)
        self.wait_active()
        process.terminate()
        self.assertEqual(process.wait(timeout=5), 0)
        self.assert_restored()

    def test_missing_baseline_prevents_application_start(self):
        saved = self.data / 'baseline-saved.json'
        self.baseline_path.rename(saved)
        process = self.start('run')
        time.sleep(.2)
        self.assertIsNone(process.poll())
        state = json.loads((self.data / 'brisa-supervisor-status.json').read_text())
        self.assertEqual(state['state'], 'waiting-for-hardware')
        self.assertNotIn('child_pid', state)
        self.assert_restored()
        saved.rename(self.baseline_path)
        self.wait_active()
        process.terminate()
        self.assertEqual(process.wait(timeout=5), 0)
        self.assert_restored()


if __name__ == '__main__':
    unittest.main()
