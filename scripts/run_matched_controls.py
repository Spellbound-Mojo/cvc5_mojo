"""Compare fixed-input ownership through direct C, raw Mojo, and public Mojo.

Uses cached dependencies only. Operation-count memory checks cover live-owner
exports and complete graph cleanup. Short traces check equivalent native
operations and reference balance. Timings are diagnostic, not an overhead
benchmark or a service-lifetime policy.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import random

from run_soak_tests import ROOT, build_workload, monitor, provenance, samples
from verify_docs_examples import run
from bindgen import config, gen_raw, report as coverage

MODES = ('results', 'proofs', 'grammars')
ALL_MODES = (*MODES, 'grammar-empty', 'grammar-rules', 'grammar-reuse', 'grammar-write', 'commands',
             'datatype-declarations', 'datatypes', 'statistics', 'statistics-iter', 'synthesis', 'synthesis-copy')
LAYERS = ('c', 'raw', 'public')


def analyze(rows, operations):
    measured = [r for r in rows if r['phase'] == 1]
    valid = (bool(rows) and rows[0]['phase'] == 0 and rows[0]['operations'] == 0 and bool(measured)
             and all(r['rss_kib'] > 0 for r in rows)
             and all(a['operations'] < b['operations'] and a['elapsed_ns'] <= b['elapsed_ns']
                     for a, b in zip(measured, measured[1:])))
    complete = (valid and len(rows) == len(measured) + 2
                and len(measured) >= 1 and measured[-1]['operations'] == operations
                and rows[-1]['phase'] == 2 and rows[-1]['operations'] == operations)
    if not valid:
        return dict(complete=False)
    baseline = rows[0]['rss_kib']
    last = measured[-1]
    return dict(complete=complete, operations=last['operations'], requested_operations=operations, checksum=last['checksum'],
                seconds=last['elapsed_ns'] / 1e9, baseline_rss_kib=baseline,
                peak_growth_kib=max(r['rss_kib'] for r in [rows[0], *measured]) - baseline,
                final_growth_kib=last['rss_kib'] - baseline,
                after_cleanup_rss_kib=rows[-1]['rss_kib'] if rows[-1]['phase'] == 2 else None)


def libraries(path):
    paths = set()
    if path.exists():
        for line in path.read_text().splitlines():
            fields = line.split(maxsplit=5)
            if len(fields) == 6 and Path(fields[5]).name.startswith('libcvc5'):
                paths.add(Path(fields[5]).resolve())
    expected = (config.BINARY_DIR / 'lib/libcvc5.so').resolve()
    parser = (config.BINARY_DIR / 'lib/libcvc5parser.so').resolve()
    files = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(paths)}
    wanted = {hashlib.sha256(p.read_bytes()).hexdigest() for p in (expected, parser)}
    main_hash = hashlib.sha256(expected.read_bytes()).hexdigest()
    # Release archives may contain byte-identical .so and SONAME copies rather
    # than symlinks. Match bytes, and reject duplicate mappings or other builds.
    matched = (main_hash in files.values() and set(files.values()) <= wanted
               and len(files) == len(set(files.values())))
    return dict(matched=matched, files=files)


def compare(control, other, absolute_budget_kib, excess_budget_kib):
    if not control.get('complete') or not other.get('complete'):
        return dict(passed=False, reason='incomplete control or comparison')
    same = (control['operations'], control['checksum']) == (other['operations'], other['checksum'])
    excess = other['peak_growth_kib'] - control['peak_growth_kib']
    return dict(passed=same and control['peak_growth_kib'] <= absolute_budget_kib
                and other['peak_growth_kib'] <= absolute_budget_kib and excess <= excess_budget_kib,
                same_result=same, excess_growth_kib=excess)


def per_operation(small, large, difference=32):
    delta = {name: large[name] - small[name] for name in small.keys() | large.keys()}
    if any(value < 0 or value % difference for value in delta.values()):
        raise ValueError('trace counts do not scale with the fixed operation sequence')
    return {name: value // difference for name, value in sorted(delta.items()) if value}


def reference_pairs(snapshot):
    """Extract every handle's copy/release pair, including the private Stat."""
    pairs = []
    for ctype in snapshot['handles']:
        functions = {name for name, f in snapshot['c_functions'].items()
                     if f['params'] and gen_raw._split(f['params'][0]['type'])[:2] == (ctype, 0)}
        copy = [n for n in functions if n.endswith('_copy')]
        release = [n for n in functions if n.endswith('_release')]
        if len(copy) != 1 or len(release) != 1:
            raise ValueError('ambiguous reference lifecycle: ' + ctype)
        pairs.append((copy[0], release[0]))
    return pairs


def balanced(control, other, pairs=None):
    # Allow additional balanced copies introduced by public value semantics.
    # The direct-C fixture defines the exports for an equivalent operation.
    if pairs is None:
        pairs = reference_pairs(json.loads(config.SNAPSHOT_FILE.read_text()))
    return all(other.get(release, 0) - other.get(copy, 0)
               == control.get(release, 0) - control.get(copy, 0) for copy, release in pairs)


def equivalent_calls(control, other, pairs):
    """Permit balanced value copies and report formatting amplification.

    All other native calls, including exports and owner construction/deletion,
    must match. Formatter counts stay visible in the report; the known two-pass
    String conversion is a diagnostic, not an ownership mismatch.
    """
    copies = {name for pair in pairs for name in pair}
    def core(counts):
        return {n: v for n, v in counts.items() if n not in copies and not n.endswith('_to_string')}
    return balanced(control, other, pairs) and core(control) == core(other)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True)
    parser.add_argument('--operations', default='200000,1000000')
    parser.add_argument('--modes', default=','.join(MODES), help='Comma-separated controls: ' + ','.join(ALL_MODES))
    parser.add_argument('--repetitions', type=int, default=2)
    parser.add_argument('--warmup', type=int, default=2000)
    parser.add_argument('--route', choices=('source', 'package'), default='package')
    parser.add_argument('--optimization', type=int, choices=(0, 3), default=3)
    parser.add_argument('--release', action='store_true', help='Do not enable ASSERT=all')
    parser.add_argument('--lifetime', choices=('live', 'round'), default='live',
                        help='Keep one graph alive, or create/exercise/release a graph each iteration')
    parser.add_argument('--absolute-budget-kib', type=int, default=4096)
    parser.add_argument('--excess-budget-kib', type=int, default=1024)
    parser.add_argument('--timeout', type=int, default=180)
    args = parser.parse_args()
    counts = [int(n) for n in args.operations.split(',')]
    modes = args.modes.split(',')
    if (not counts or min(counts) < 1 or len(set(counts)) != len(counts) or args.repetitions < 1
            or min(args.warmup, args.absolute_budget_kib, args.excess_budget_kib) < 0 or args.timeout < 1
            or not modes or len(set(modes)) != len(modes) or any(m not in ALL_MODES for m in modes)):
        parser.error('invalid operation count, repetition, warmup, or budget')
    folder = Path(args.output).resolve()
    folder.mkdir(parents=True, exist_ok=False)
    sources = [p for p in (ROOT / 'tests/binding').glob('*') if p.is_file()]
    sources += [Path(__file__).resolve(), ROOT / 'scripts/verify_docs_examples.py',
                ROOT / 'bindgen/config.py', config.SNAPSHOT_FILE, ROOT / 'pixi.lock']
    sources += list(config.INCLUDE_DIR.rglob('*.h'))
    binary, hashes = build_workload(folder, args.route, 'tests/binding/controls.mojo',
                                    optimization=args.optimization, assertions=not args.release, extra_inputs=sources)
    c_binary = folder / 'controls-c'
    lib = config.BINARY_DIR / 'lib'
    command = [config.c_compiler(), '-std=gnu11', f'-O{args.optimization}', '-Wall', '-Wextra', '-Werror',
               '-I', str(config.INCLUDE_DIR), 'tests/binding/controls.c', '-L', str(lib),
               '-Wl,-rpath,' + str(lib), '-lcvc5parser', '-lcvc5', '-o', str(c_binary)]
    compiled = run(command, 120)
    (folder / 'c-build.json').write_text(json.dumps(dict(command=command, compile=compiled,
                                                      compiler=run([config.c_compiler(), '--version'], 20)), indent=2) + '\n')
    if compiled['returncode'] != 0:
        raise SystemExit(compiled['stderr'])
    metadata = provenance(binary, hashes)
    metadata['c_binary_sha256'] = hashlib.sha256(c_binary.read_bytes()).hexdigest()
    snap = json.loads(config.SNAPSHOT_FILE.read_text())
    pairs = reference_pairs(snap)
    (folder / 'api-coverage.json').write_text(json.dumps(coverage.summarize(snap), default=sorted, indent=2) + '\n')

    def execute(layer, mode, count, warmup, name, *, target=binary, retained=False, trace=None):
        path = folder / f'{name}.tsv'
        lifetime = 'live' if retained else args.lifetime
        command = ([str(c_binary), mode, str(count), str(warmup), str(path), str(int(retained)), lifetime]
                   if layer == 'c' else [str(target), layer, mode, str(count), str(warmup), str(path), lifetime])
        execution = monitor(command, folder, name, args.timeout, 512,
                            env_overrides={'CVC5_BINDING_TRACE': str(trace)} if trace else None)
        metrics = analyze(samples(path), count)
        loaded = libraries(Path(str(path) + '.maps'))
        complete = (execution['returncode'] == 0 and execution['stop_reason'] is None
                    and metrics['complete'] and loaded['matched'])
        record = dict(name=name, layer=layer, mode=mode, complete=complete, metrics=metrics,
                      libraries=loaded, command=command, **execution)
        (folder / f'{name}.json').write_text(json.dumps(record, indent=2) + '\n')
        if not complete:
            print(f'FAIL {name}: {execution["stop_reason"] or execution["stderr"] or "incomplete checkpoints or library mismatch"}', flush=True)
        return record

    records = []
    rng = random.Random(17)
    for repetition in range(args.repetitions):
        tasks = [(mode, count) for mode in modes for count in counts]
        rng.shuffle(tasks)
        for mode, count in tasks:
            order = list(LAYERS)
            rng.shuffle(order)
            group = {}
            for layer in order:
                name = f'{mode}-{layer}-{count}-{repetition}'
                print('RUN', name, flush=True)
                group[layer] = execute(layer, mode, count, args.warmup, name)
            control = group['c']['metrics']
            for layer, record in group.items():
                comparison = compare(control, record['metrics'], args.absolute_budget_kib, args.excess_budget_kib)
                record['comparison'] = comparison
                record['passed'] = all(r['complete'] for r in group.values()) and comparison['passed']
                records.append(record)
                (folder / f'{record["name"]}.json').write_text(json.dumps(record, indent=2) + '\n')
                print(f'{"PASS" if record["passed"] else "FAIL"} {record["name"]}: '
                      f'growth {record["metrics"].get("peak_growth_kib")} KiB; '
                      f'excess over C {comparison.get("excess_growth_kib")} KiB', flush=True)
            (folder / 'report.json').write_text(json.dumps(dict(settings=vars(args), **metadata, records=records,
                                                               complete=False), indent=2) + '\n')

    # A known extra reference must exceed the same memory budget. This is
    # reachable retention until solver deletion, not an unreachable leak.
    print('RUN retained-reference sensitivity control', flush=True)
    sensitivity = execute('c', 'results', 200000, 2000, 'retained-reference', retained=True)
    sensitivity['detected'] = (sensitivity['complete']
                               and sensitivity['metrics']['peak_growth_kib'] > args.absolute_budget_kib)

    trace_folder = folder / 'trace-build'
    trace_folder.mkdir()
    trace_path = trace_folder / 'calls.txt'
    trace_binary, _ = build_workload(trace_folder, args.route, 'tests/binding/controls.mojo',
                                    optimization=args.optimization, assertions=not args.release,
                                    defines=[f'CVC5_MOJO_TRACE={trace_path}'], extra_inputs=sources)
    traces = {}
    for mode in modes:
        traces[mode] = {}
        for layer in LAYERS:
            counters = []
            for count in (1, 33):
                trace_path.unlink(missing_ok=True)
                name = f'trace-{mode}-{layer}-{count}'
                record = execute(layer, mode, count, 0, name, target=trace_binary, trace=trace_path)
                if not record['complete'] or not trace_path.exists():
                    raise SystemExit('trace control failed: ' + name)
                counters.append(Counter(trace_path.read_text().splitlines()))
                trace_path.rename(folder / f'{name}.calls')
            traces[mode][layer] = per_operation(*counters)
        c, raw, public = (traces[mode][layer] for layer in LAYERS)
        traces[mode]['passed'] = c == raw and equivalent_calls(c, public, pairs)
    passed = all(r['passed'] for r in records) and sensitivity['detected'] and all(t['passed'] for t in traces.values())
    result = dict(passed=passed, complete=True, settings=vars(args), **metadata,
                  records=records, sensitivity=sensitivity, native_calls_per_operation=traces)
    (folder / 'report.json').write_text(json.dumps(result, indent=2) + '\n')
    print('MATCHED CONTROLS PASS' if passed else 'MATCHED CONTROLS FAILED', flush=True)
    return int(not passed)


if __name__ == '__main__':
    raise SystemExit(main())
