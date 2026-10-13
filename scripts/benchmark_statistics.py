"""Measure statistics snapshots with cached dependencies and preserved baseline binaries.

Reuse the binding benchmark's validation and paired statistics. Native call
tracing is separate from timing. This measures public Mojo snapshots, not
solver throughput or total heap allocation.
"""
import argparse
from collections import Counter
import hashlib
import json
import math
import os
from pathlib import Path
import random

from benchmark_binding_overhead import distribution, measurement, paired_interval
from run_matched_controls import libraries, per_operation
from run_soak_tests import ROOT, build_workload, provenance
from verify_docs_examples import run
from bindgen import config

MODES = ('visible', 'internal', 'defaulted', 'all', 'iterate')
SOURCE = 'tests/binding/statistics_overhead.mojo'


def observation(result, mode, count, warmup):
    lines = result['stdout'].splitlines(keepends=True)
    if len(lines) != 3 or not lines[2].startswith('expected ') or not lines[2].endswith('\n'):
        return None
    try:
        expected = int(lines[2].split()[1])
    except (ValueError, IndexError):
        return None
    if lines[2] != f'expected {expected}\n' or expected <= 0:
        return None
    metrics = measurement(dict(result, stdout=''.join(lines[:2])), mode, count, warmup, expected=expected)
    return dict(metrics, entries=expected) if metrics else None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, help='A fresh directory')
    parser.add_argument('--route', choices=('source', 'package'), default='package')
    parser.add_argument('--baseline', type=Path, help='Previously saved report.json; re-time its binary in paired runs')
    parser.add_argument('--repetitions', type=int, default=9)
    parser.add_argument('--operations', type=int, default=0, help='Zero calibrates each mode to target-ms')
    parser.add_argument('--target-ms', type=int, default=150)
    parser.add_argument('--warmup', type=int, default=100)
    parser.add_argument('--cpu', type=int)
    parser.add_argument('--skip-traces', action='store_true')
    args = parser.parse_args()
    if min(args.repetitions, args.target_ms) < 1 or min(args.operations, args.warmup) < 0:
        parser.error('invalid measurement settings')
    cpu = min(os.sched_getaffinity(0)) if args.cpu is None else args.cpu
    if cpu not in os.sched_getaffinity(0):
        parser.error('CPU is outside the allowed affinity set')
    folder = Path(args.output).resolve()
    folder.mkdir(parents=True, exist_ok=False)
    extra = [ROOT / 'scripts/benchmark_statistics.py', ROOT / 'scripts/benchmark_binding_overhead.py']
    binary, hashes = build_workload(folder, args.route, SOURCE, assertions=False, extra_inputs=extra)
    inputs = provenance(binary, hashes)
    binaries = dict(current=binary)
    baseline = json.loads(args.baseline.read_text()) if args.baseline else None
    if baseline:
        assert baseline['passed'] and baseline['settings']['route'] == args.route
        old = Path(baseline['binary'])
        assert hashlib.sha256(old.read_bytes()).hexdigest() == baseline['binary_sha256']
        # Fixture and dependencies must be identical; only the library may differ.
        for name, digest in hashes.items():
            if not name.startswith('src/'):
                assert baseline['source_and_dependency_hashes'][name] == digest, name
        binaries['baseline'] = old
    env = dict(os.environ, CVC5_MOJO_LIBRARY=str(config.BINARY_DIR / 'lib/libcvc5.so'))

    def execute(mode, revision, count, warmup, label, target=None):
        stem = folder / label
        command = ['taskset', '-c', str(cpu), str(target or binaries[revision]),
                   str(mode), str(count), str(warmup), str(stem)]
        result = run(command, 120, env=env)
        metrics = observation(result, mode, count, warmup)
        loaded = libraries(Path(str(stem) + '.maps'))
        row = dict(mode=MODES[mode], revision=revision, command=command, run=result,
                   metrics=metrics, libraries=loaded, passed=metrics is not None and loaded['matched'])
        stem.with_suffix('.json').write_text(json.dumps(row, indent=2) + '\n')
        assert row['passed'], row
        return row

    counts = {}
    for mode, name in enumerate(MODES):
        if args.operations:
            counts[name] = args.operations
        elif baseline:
            counts[name] = baseline['counts'][name]
        else:
            row = execute(mode, 'current', 32, args.warmup, 'calibrate-' + name)
            counts[name] = max(16, min(1_000_000, math.ceil(args.target_ms * 1e6 / row['metrics']['ns_per_operation'])))
    records, rng = [], random.Random(127)
    for repetition in range(args.repetitions):
        modes = list(range(len(MODES))); rng.shuffle(modes)
        for mode in modes:
            revisions = list(binaries); rng.shuffle(revisions)
            for revision in revisions:
                row = execute(mode, revision, counts[MODES[mode]], args.warmup,
                              f'timing-{repetition}-{MODES[mode]}-{revision}')
                records.append(dict(row, repetition=repetition))
        print('timing repetition', repetition, 'passed', flush=True)
    summary = {}
    for name in MODES:
        rows = [r for r in records if r['mode'] == name]
        assert len({r['metrics']['entries'] for r in rows}) == 1, name
        values = {rev: {r['repetition']: r['metrics']['ns_per_operation'] for r in rows if r['revision'] == rev}
                  for rev in binaries}
        summary[name] = dict(entries=rows[0]['metrics']['entries'],
                             ns_per_operation={rev: distribution(list(v.values())) for rev, v in values.items()})
        if baseline:
            a, b = values['baseline'], values['current']
            summary[name].update(saved_ns=paired_interval([a[i] - b[i] for i in a]),
                                 reduction_percent=paired_interval([100 * (1 - b[i] / a[i]) for i in a]))
    calls = {}
    if not args.skip_traces:
        trace_folder = folder / 'instrumented'; trace_folder.mkdir()
        trace = trace_folder / 'calls.txt'
        traced, _ = build_workload(trace_folder, args.route, SOURCE, assertions=False,
                                   defines=[f'CVC5_MOJO_TRACE={trace}'], extra_inputs=extra)
        for mode, name in enumerate(MODES):
            observed = []
            for n in (1, 3):
                trace.unlink(missing_ok=True)
                execute(mode, 'current', n, 0, f'trace-{name}-{n}', target=traced)
                observed.append(Counter(trace.read_text().splitlines()))
                trace.rename(folder / f'trace-{name}-{n}.calls')
            calls[name] = per_operation(*observed, difference=2)
            assert calls[name]['cvc5_stats_iter_next'] == calls[name]['cvc5_stat_release'] == summary[name]['entries']
        if baseline and baseline['native_calls_per_operation']:
            assert calls == baseline['native_calls_per_operation'], 'native call counts changed'
    report = dict(passed=True, settings=dict(route=args.route, cpu=cpu, repetitions=args.repetitions,
                                            warmup=args.warmup, order_seed=127),
                  baseline=str(args.baseline) if args.baseline else None, binary=str(binary),
                  **inputs, counts=counts, records=records, summary=summary, native_calls_per_operation=calls)
    (folder / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
