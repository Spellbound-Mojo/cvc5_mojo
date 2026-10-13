"""Run core or extended binding verification without fetching dependencies.

Each gate delegates to its existing runner. Output must be fresh; reports are
checkpointed after every gate, and failures never disappear behind later passes.
"""
import argparse
import json
from pathlib import Path
import sys
import tomllib

from verify_docs_examples import run
from run_soak_tests import fingerprint
from bindgen import config


def gates(tier, folder, jobs):
    python = sys.executable
    # Reuse the manifest's standalone build/run command, without invoking its
    # Pixi fetch dependency. Running this fixture through Mojo's JIT would mask
    # growth by reusing memory released by the compiler.
    leak_command = tomllib.loads((config.ROOT / 'pixi.toml').read_text())['tasks']['leaks']['cmd']

    def script(name, *args):
        return [python, 'scripts/' + name + '.py', *map(str, args)]

    def output(name):
        return str(folder / name)

    core = [
        ('snapshot', [python, '-m', 'bindgen.snapshot', '--check']),
        *[(name, [python, '-m', 'bindgen.' + name]) for name in ('enums', 'gen_raw', 'gen_api', 'translate')],
        *[(name + '-unit', [python, '-m', 'unittest', 'discover', '-s', 'tests/' + name, '-v'])
          for name in ('bindgen', 'binding', 'soak')],
        ('contracts', script('run_contract_tests', '--optimization', '0,3', '--jobs', jobs, '--output', output('contracts'))),
        ('runtime', script('check_runtime_loading', '--optimization', '0,3', '--jobs', jobs, '--output', output('runtime'))),
        *[(name, ['mojo', 'run', '-I', 'src', f'tests/smoke/test_{name}.mojo'])
          for name in ('raw', 'api', 'smoke', 'lifetimes', 'threads')],
        ('leaks', ['bash', '-c', leak_command]),
        ('upstream', script('run_cvc5_tests', '--jobs', jobs, '--output', output('upstream'))),
        ('docs-examples', script('verify_docs_examples', '--jobs', jobs, '--output', output('docs-examples'))),
        ('docs', [str(config.ROOT / '.pixi/envs/docs/bin/python'), 'scripts/check_docs.py']),
    ]
    extended = [
        ('sanitizers', script('check_sanitizers', '--jobs', jobs, '--output', output('sanitizers'))),
        ('conversion-stress', script('run_contract_tests', '--only', 'return_conversion', '--conversion-iterations', 1000,
                                     '--jobs', jobs, '--output', output('conversion-stress'))),
        ('ownership-stress', script('run_contract_tests', '--only', 'ownership', '--ownership-iterations', 5000,
                                    '--jobs', jobs, '--output', output('ownership-stress'))),
        ('sequences-long', script('run_contract_tests', '--only', 'sequences', '--sequence-seeds', '0,1,42,73,127,1024',
                                 '--sequence-steps', 2048, '--jobs', jobs, '--output', output('sequences-long'))),
        ('threads-long', script('check_runtime_loading', '--rounds', 500, '--repetitions', 10,
                               '--jobs', jobs, '--output', output('threads-long'))),
        ('matched-live', script('run_matched_controls', '--modes',
                               'results,proofs,grammar-empty,grammar-rules,commands,datatype-declarations,datatypes,synthesis-copy',
                               '--operations', '200000,1000000', '--repetitions', 2, '--output', output('matched-live'))),
        ('matched-statistics', script('run_matched_controls', '--modes', 'statistics,statistics-iter',
                                     '--operations', '20000,100000', '--repetitions', 2,
                                     '--output', output('matched-statistics'))),
        ('matched-round', script('run_matched_controls', '--modes',
                                'datatype-declarations,datatypes,statistics,statistics-iter,synthesis,synthesis-copy',
                                '--lifetime', 'round', '--operations', '100,1000', '--warmup', 40,
                                '--repetitions', 2, '--output', output('matched-round'))),
        ('overhead', script('benchmark_binding_overhead', '--repetitions', 9, '--output', output('overhead'))),
    ]
    return core if tier == 'core' else extended if tier == 'extended' else core + extended


def generated_hashes():
    """Require regeneration and translated call accounting to preserve outputs."""
    return fingerprint(p for root in ('api', 'src', 'tests/cvc5') for p in (config.ROOT / root).rglob('*')
                       if p.is_file() and p.suffix in ('.mojo', '.json'))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--tier', choices=('core', 'extended', 'all'), default='core')
    parser.add_argument('--output', required=True)
    parser.add_argument('--jobs', type=int, default=2)
    parser.add_argument('--only', help='Comma-separated exact gate names, retaining their canonical order')
    parser.add_argument('--list', action='store_true', help='Show commands without executing them')
    args = parser.parse_args()
    if args.jobs < 1:
        parser.error('jobs must be positive')
    folder = Path(args.output).resolve()
    commands = gates(args.tier, folder, args.jobs)
    if args.only:
        selected = set(args.only.split(','))
        unknown = selected - {name for name, _ in commands}
        if unknown:
            parser.error('unknown gates: ' + ', '.join(sorted(unknown)))
        commands = [(name, cmd) for name, cmd in commands if name in selected]
    if args.list:
        print(json.dumps(commands, indent=2))
        return 0
    if folder.exists() and any(folder.iterdir()):
        parser.error('output directory must be empty to prevent stale results')
    folder.mkdir(parents=True, exist_ok=True)
    paths = [p for root in ('src', 'bindgen', 'scripts', 'tests') for p in (config.ROOT / root).rglob('*')
             if p.is_file() and p.suffix in ('.py', '.mojo', '.c', '.h', '.toml', '.json')]
    paths += [config.SNAPSHOT_FILE, config.ROOT / 'pixi.lock', config.APN_PACKAGE_DIR / 'apn_mojo.mojoc']
    paths += list((config.BINARY_DIR / 'lib').glob('libcvc5*.so'))
    generated = generated_hashes()
    report = dict(tier=args.tier, selected=[name for name, _ in commands], completed=False, passed=False,
                  generated_before=generated,
                  source_and_dependency_hashes=fingerprint(paths), records=[])
    path = folder / 'report.json'
    path.write_text(json.dumps(report, indent=2) + '\n')
    for name, command in commands:
        print('RUN', name, flush=True)
        try:
            result = dict(name=name, command=command, **run(command, 14400))
        except OSError as error:
            result = dict(name=name, command=command, returncode=None, stdout='', stderr=str(error))
        result['passed'] = result['returncode'] == 0
        (folder / (name + '.json')).write_text(json.dumps(result, indent=2) + '\n')
        report['records'].append(result)
        path.write_text(json.dumps(report, indent=2) + '\n')
        print('PASS' if result['passed'] else 'FAIL', name, flush=True)
        if not result['passed']:
            print(result['stderr'], flush=True)
            return 1
    after = generated_hashes()
    drift = sorted(p for p in generated.keys() | after.keys() if generated.get(p) != after.get(p))
    report.update(completed=True, passed=not drift, generated_drift=drift)
    path.write_text(json.dumps(report, indent=2) + '\n')
    if drift:
        print('FAIL generated output drift:', ', '.join(drift), flush=True)
    return int(bool(drift))


if __name__ == '__main__':
    raise SystemExit(main())
