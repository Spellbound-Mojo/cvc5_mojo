"""Ensure solver examples cannot leave child processes after a timeout or cancellation."""
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time
import unittest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'scripts'))
import verify_docs_examples as runner

TREE = '''import pathlib, subprocess, sys, time
child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'])
pathlib.Path(sys.argv[1]).write_text(str(child.pid))
time.sleep(60)
'''


class ProcessLifetime(unittest.TestCase):
    def assert_stopped(self, pid):
        path = Path(f'/proc/{pid}/stat')
        # An orphan may wait for the host to reap its zombie entry; it must
        # already have stopped executing. Inspect state, not only PID existence.
        for _ in range(50):
            if not path.exists():
                return
            try:
                if path.read_text().split(') ', 1)[1].split()[0] == 'Z':
                    return
            except (FileNotFoundError, ProcessLookupError):
                return
            time.sleep(0.02)
        self.fail(f'Example descendant still running: {pid}')

    def test_timeout_kills_descendant(self):
        with tempfile.TemporaryDirectory() as directory:
            marker = Path(directory) / 'child'
            record = runner.run([sys.executable, '-c', TREE, str(marker)], timeout=1)
            self.assertIsNone(record['returncode'])
            self.assertTrue(record['stderr'].startswith('timeout'))
            self.assert_stopped(int(marker.read_text()))

    def test_sigterm_stops_worker_process_groups(self):
        with tempfile.TemporaryDirectory() as directory:
            marker = Path(directory) / 'child'
            harness = '''import signal, sys
from concurrent.futures import ThreadPoolExecutor
sys.path.insert(0, sys.argv[1])
import verify_docs_examples as runner
signal.signal(signal.SIGTERM, runner.cancel)
try:
    with ThreadPoolExecutor(max_workers=1) as executor:
        executor.submit(runner.run, [sys.executable, '-c', sys.argv[2], sys.argv[3]], 5).result()
except KeyboardInterrupt:
    raise SystemExit(130)
'''
            proc = subprocess.Popen([sys.executable, '-c', harness, str(ROOT / 'scripts'), TREE, str(marker)],
                                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            try:
                deadline = time.monotonic() + 4
                while not marker.exists() and time.monotonic() < deadline:
                    time.sleep(0.02)
                self.assertTrue(marker.exists(), 'Worker did not start')
                proc.send_signal(signal.SIGTERM)
                _, stderr = proc.communicate(timeout=3)
                self.assertEqual(proc.returncode, 130, stderr)
                self.assert_stopped(int(marker.read_text()))
            finally:
                if proc.poll() is None:
                    proc.send_signal(signal.SIGTERM)
                    proc.communicate(timeout=7)


if __name__ == '__main__':
    unittest.main()
