"""Timed-out verification commands must not leave their process group running."""
import os
from pathlib import Path
import signal
import sys
import tempfile
import time
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'scripts'))
from verify_docs_examples import run


class ExecutionTests(unittest.TestCase):
    def test_timeout_stops_descendant_and_preserves_output(self):
        with tempfile.TemporaryDirectory() as folder:
            pidfile = Path(folder) / 'child.pid'
            child = ('import os,signal,time\n'
                     'signal.signal(signal.SIGTERM, signal.SIG_IGN)\n'
                     'print(os.getpid(), flush=True)\n'
                     'time.sleep(60)\n')
            parent = ('import pathlib,subprocess,sys,time\n'
                      f'p = subprocess.Popen([sys.executable, "-c", {child!r}], stdout=subprocess.PIPE, text=True)\n'
                      'pathlib.Path(sys.argv[1]).write_text(p.stdout.readline().strip())\n'
                      'print("before timeout", flush=True)\n'
                      'time.sleep(60)\n')
            pid = None
            try:
                result = run([sys.executable, '-c', parent, str(pidfile)], 1)
                pid = int(pidfile.read_text())
                # A killed orphan may remain a zombie until the container's
                # init reaps it. Neither a missing process nor a zombie runs.
                def active():
                    try:
                        return Path(f'/proc/{pid}/stat').read_text().split()[2] != 'Z'
                    except (FileNotFoundError, ProcessLookupError):
                        return False
                deadline = time.monotonic() + 2
                while active() and time.monotonic() < deadline:
                    time.sleep(0.01)
                self.assertFalse(active(), 'timed-out descendant is still running')
                self.assertIsNone(result['returncode'])
                self.assertIn('timeout', result['stderr'])
                self.assertEqual(result['stdout'], 'before timeout\n')
            finally:
                if pid is not None:
                    try:
                        os.kill(pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass

    def test_exit_status_and_streams_are_preserved(self):
        result = run([sys.executable, '-c',
                      'import sys; print("out"); print("err", file=sys.stderr); sys.exit(7)'], 10)
        self.assertEqual((result['returncode'], result['stdout'], result['stderr']), (7, 'out\n', 'err\n'))


if __name__ == '__main__':
    unittest.main()
