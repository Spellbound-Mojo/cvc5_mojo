"""Compile and execute the exact documentation programs on both import routes.

Every program in docs/examples.json is built from source (`-I src`) and
against the precompiled package, using the installed apn_mojo dependency,
at O0 and O3 with `--Werror`. Programs run
from the repository root or an isolated consumer directory, as declared in
the manifest. Paired Python programs share the expected output and run in
the oracle environment. A JSON report is written to the output directory.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import tempfile
import threading
import time

from docs_contract import ROOT, data
from bindgen import config

_active = set()
_lock = threading.RLock()
_cancelled = threading.Event()

def stop(process):
    """Stop a command started with start_new_session, including its process group.

    Even if the leader exits after SIGTERM, a descendant can ignore it. Always
    finish the group before returning. Processes that detach into new sessions
    require their own supervisor; these verification commands must not detach.
    """
    try:
        os.killpg(process.pid, signal.SIGTERM)
        process.wait(timeout=2)
    except subprocess.TimeoutExpired:
        pass
    except ProcessLookupError:
        pass
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    process.wait(timeout=5)


def run(cmd, timeout, *, env=None, cwd=ROOT):
    start = time.monotonic()
    if _cancelled.is_set():
        raise KeyboardInterrupt
    with _lock:
        proc = subprocess.Popen(cmd, cwd=cwd, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                text=True, start_new_session=True)
        _active.add(proc)
    try:
        try:
            if _cancelled.is_set():
                raise KeyboardInterrupt
            stdout, stderr = proc.communicate(timeout=timeout)
            if _cancelled.is_set():
                raise KeyboardInterrupt
            code = proc.returncode
        except subprocess.TimeoutExpired:
            stop(proc)
            stdout, stderr = proc.communicate()
            code, stderr = None, 'timeout\n' + stderr[-3992:]
    finally:
        stop(proc)
        with _lock:
            _active.discard(proc)
    return dict(returncode=code, stdout=stdout, stderr=stderr[-4000:],
                seconds=round(time.monotonic() - start, 1))


def cancel(signum, frame):
    """Cancel worker commands through the same process-group cleanup helper."""
    _cancelled.set()
    with _lock:
        processes = list(_active)
    for process in processes:
        stop(process)


def precompile(folder, timeout):
    """Precompile the package into `folder`/package, with --Werror; return
    that directory, for `mojo -I`, and the compilation record."""
    package = folder / 'package'
    package.mkdir(exist_ok=True)
    built = run(['mojo', 'precompile', '--Werror', 'src/cvc5_mojo', '-o', str(package / 'cvc5_mojo.mojoc')],
                timeout)
    assert built['returncode'] == 0, 'Package compilation failed:\n' + built['stderr']
    return package, built


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, help='A fresh report directory')
    parser.add_argument('--only', help='Run only programs whose path contains this text')
    parser.add_argument('--compile-timeout', type=int, default=300, help='Seconds per compilation')
    parser.add_argument('--jobs', type=int, default=2, help='Concurrent compilations')
    parser.add_argument('--oracle-only', action='store_true', help='Run paired Python examples in the oracle environment')
    parser.add_argument('--run-timeout', type=int, default=30, help='Hard timeout in seconds per example process group')
    args = parser.parse_args()
    folder = Path(args.output).resolve()
    folder.mkdir(parents=True, exist_ok=False)
    declared = data('examples.json')['examples']
    selected = {p: s for p, s in declared.items() if (not args.only or args.only in p)
                and (not args.oracle_only or 'python' in s)}
    assert selected, 'No matching documentation programs'

    if args.oracle_only:
        import cvc5
        import sys
        assert cvc5.__version__ == config.pinned()['version'], 'Use the pinned oracle environment'
        records = []
        for path, spec in selected.items():
            executed = run([sys.executable, str(ROOT / spec['python'])], args.run_timeout)
            passed = executed['returncode'] == 0 and executed['stdout'] == spec['stdout']
            print('PASS' if passed else 'FAIL', spec['python'], flush=True)
            records.append(dict(source=path, python=spec['python'], passed=passed, run=executed))
        passed = all(record['passed'] for record in records)
        (folder / 'report.json').write_text(json.dumps(dict(passed=passed, records=records), indent=2))
        return not passed

    package, built = precompile(folder, args.compile_timeout)

    tasks = [(path, route, level) for path in selected for route in ('source', 'package') for level in (0, 3)]

    def execute(task):
        path, route, level = task
        name = path.replace('/', '_').removesuffix('.mojo') + f'-{route}-O{level}'
        binary = folder / 'bin' / name
        binary.parent.mkdir(exist_ok=True)
        include = str(ROOT / 'src') if route == 'source' else str(package)
        # A consumer runs with neither the checkout cwd nor its library fallback.
        # Copy its adjacent modules as well, using the same source as the docs.
        with tempfile.TemporaryDirectory(prefix='cvc5-mojo-example-') as temporary:
            isolated = selected[path].get('working_directory') == 'isolated'
            cwd, source, env = ROOT, ROOT / path, None
            if isolated:
                cwd = Path(temporary) / 'app'
                shutil.copytree(source.parent, cwd)
                source = cwd / source.name
                library = config.BINARY_DIR / 'lib' / config.library_filename('libcvc5')
                env = dict(os.environ, CVC5_MOJO_LIBRARY=str(library))
                assert not cwd.is_relative_to(ROOT)
                assert not (cwd / 'third_party/cvc5/lib' / library.name).exists()
            compiled = run(['mojo', 'build', '--Werror', f'-O{level}', '-I', include, str(source), '-o', str(binary)],
                           args.compile_timeout, cwd=cwd, env=env)
            executed = run([str(binary)], args.run_timeout, cwd=cwd, env=env) if compiled['returncode'] == 0 else None
        passed = bool(executed) and executed['returncode'] == 0 and executed['stdout'] == selected[path]['stdout']
        print('PASS' if passed else 'FAIL', name, flush=True)
        return dict(source=path, route=route, optimization=level, isolated=isolated,
                    passed=passed, compile=compiled, run=executed)

    with ThreadPoolExecutor(max_workers=args.jobs) as executor:
        records = list(executor.map(execute, tasks))
    passed = all(r['passed'] for r in records)
    (folder / 'report.json').write_text(json.dumps(dict(passed=passed, package=built, records=records), indent=2))
    print('DOCUMENTATION EXAMPLES PASS' if passed else 'FAILED', flush=True)
    return not passed


if __name__ == '__main__':
    signal.signal(signal.SIGINT, cancel)
    signal.signal(signal.SIGTERM, cancel)
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        raise SystemExit(130)
