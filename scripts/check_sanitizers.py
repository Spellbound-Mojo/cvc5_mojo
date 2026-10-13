"""Check sanitizer sensitivity, then instrument binding contracts using cached dependencies.

ASan instruments Mojo at O1. Native cvc5 memory accesses remain uninstrumented;
LSan can observe its intercepted heap allocations, not reachable retained state.
"""
import argparse
import json
import os
from pathlib import Path
import re
import sys

from run_contract_tests import PROGRAMS, build_native
from bindgen import config
from run_soak_tests import fingerprint
from verify_docs_examples import run


def detected(result, diagnostic):
    """A crash, timeout, or unrelated error is never a successful sensitivity check."""
    return result['returncode'] == 1 and diagnostic in result['stderr'] and 'SUMMARY: AddressSanitizer:' in result['stderr']


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True)
    parser.add_argument('--jobs', type=int, default=2)
    parser.add_argument('--sensitivity-only', action='store_true')
    parser.add_argument('--only', default=','.join(name for name in PROGRAMS if name not in ('retention', 'formatting')),
                        help='Contract fixture substrings; default excludes RSS budgets and deliberate formatter aborts')
    args = parser.parse_args()
    folder = Path(args.output).resolve()
    folder.mkdir(parents=True, exist_ok=True)
    native, built = build_native('sanitizer_sensitivity', 1, folder, output_name='native-leak.so',
                                 flags=['-shared', '-fPIC', '-fno-builtin'], link_flags=[])
    binary = folder / 'sensitivity'
    command = ['mojo', 'build', '--Werror', '-O1', '-g1', '--sanitize', 'address',
               'tests/binding/sanitizer_sensitivity.mojo', '-o', str(binary)]
    compiled = dict(command=command, **run(command, 300))
    env = dict(os.environ, ASAN_OPTIONS='detect_leaks=1:halt_on_error=1')
    cases = {}
    if built['returncode'] == compiled['returncode'] == 0:
        for name, arguments, diagnostic in (
            ('clean', ['bounds', '0'], None),
            ('bounds', ['bounds', '32'], 'heap-buffer-overflow'),
            ('mojo-leak', ['leak'], 'Direct leak of 8 byte(s)'),
            ('checkpoint-leak', ['checkpoint'], 'Direct leak of 8 byte(s)'),
            ('native-leak', ['native', str(native)], 'Direct leak of 37 byte(s)'),
        ):
            command = [str(binary), *arguments]
            result = dict(command=command, **run(command, 60, env=env))
            passed = (result['returncode'] == 0 and result['stdout'] == '99\nsensitivity done\n'
                      and not result['stderr']) if diagnostic is None else detected(result, diagnostic)
            cases[name] = dict(passed=passed, run=result)
            print('PASS' if passed else 'FAIL', 'sanitizer sensitivity', name, flush=True)
    sensitive = len(cases) == 5 and all(r['passed'] for r in cases.values())
    shutdown = None
    if sensitive:
        loader, loader_build = build_native('sanitizer_loading', 1, folder,
                                            flags=['-g', '-fsanitize=address'], link_flags=['-ldl'])
        snap = json.loads(config.SNAPSHOT_FILE.read_text())
        libraries = sorted({config.library_filename(f['library']) for f in snap['c_functions'].values()})
        command = [str(loader), *(str(config.BINARY_DIR / 'lib' / lib) for lib in libraries)]
        result = dict(command=command, **run(command, 60, env=env)) if loader_build['returncode'] == 0 else None
        clean = result is not None and result['returncode'] == 0 and result['stdout'] == 'native libraries unloaded\n'
        # Record the exact unsuppressed native result. It is an open native
        # finding, not a clean leak test and not a Mojo binding failure.
        known = (result is not None and detected(result, 'LeakSanitizer: detected memory leaks')
                 and result['stdout'] == 'native libraries unloaded\n'
                 and re.search(r'SUMMARY: AddressSanitizer: 16 byte\(s\) leaked in 2 allocation\(s\)\.', result['stderr']) is not None)
        shutdown = dict(compile=loader_build, run=result, status='clean' if clean else 'known-native-leak' if known else 'unexpected-failure')
    contracts = None
    if sensitive and not args.sensitivity_only:
        # RSS budgets are for the production allocator, not sanitizer overhead.
        # Nonraising formatter aborts are separately classified by the O0/O3 gate.
        command = [sys.executable, 'scripts/run_contract_tests.py', '--sanitize', 'address', '--optimization', '1',
                   '--only', args.only,
                   '--output', str(folder / 'contracts'), '--jobs', str(args.jobs)]
        contracts = dict(command=command, **run(command, 7200, env=env))
    passed = (sensitive and shutdown['status'] != 'unexpected-failure'
              and (args.sensitivity_only or contracts is not None and contracts['returncode'] == 0))
    paths = [Path(__file__), config.ROOT / 'tests/binding/sanitizer_sensitivity.c',
             config.ROOT / 'tests/binding/sanitizer_sensitivity.mojo', config.ROOT / 'tests/binding/sanitizer_loading.c',
             config.SNAPSHOT_FILE, config.ROOT / 'pixi.lock']
    paths += list((config.BINARY_DIR / 'lib').glob('libcvc5*.so'))
    report = dict(passed=passed, sensitivity_only=args.sensitivity_only, selection=args.only,
                  environment={'ASAN_OPTIONS': env['ASAN_OPTIONS']},
                  native_build=built, mojo_build=compiled, cases=cases, contracts=contracts, native_shutdown=shutdown,
                  source_and_dependency_hashes=fingerprint(paths))
    (folder / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
    return int(not passed)


if __name__ == '__main__':
    raise SystemExit(main())
