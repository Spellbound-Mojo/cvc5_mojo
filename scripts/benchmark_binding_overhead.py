"""Measure binding costs with cached libraries, isolated runs, and checked outputs.

Timing and native-call tracing use separate binaries/processes. No performance
threshold is a correctness gate. Never fetch dependencies or benchmark solving.
"""
import argparse
from collections import Counter
import hashlib
import json
import math
import os
from pathlib import Path
import random
import re
import statistics

from run_soak_tests import ROOT, build_workload, provenance
from bindgen import config
from run_matched_controls import libraries, per_operation, equivalent_calls, reference_pairs
from run_contract_tests import build_native
from verify_docs_examples import run

MODES = ('scalar', 'copy', 'integer-int', 'integer-literal', 'integer-text',
         'term-2', 'term-8', 'term-list-8', 'values-8', 'format', 'decimal-copy', 'format-once', 'integer-wide-literal',
         'children-8', 'assertions-32', 'option-names', 'integer-apn', 'integer-get', 'integer-get-wide',
         'real-apn', 'real-pair', 'real-get', 'real-get-wide', 'bv-apn', 'integer-apn-wide')
LAYERS = ('c-bare', 'c-checked', 'raw', 'public')
ALLOCATION_FIELDS = ('malloc', 'calloc', 'realloc', 'free_nonnull', 'aligned_alloc', 'requested_bytes')
DECIMAL = str(2**256 - 1)
EXPECTED = (8, 8, 1, 1, 1, 2, 8, 8, 16, sum(DECIMAL.encode()), sum(DECIMAL.encode()), sum(DECIMAL.encode()), 1, 16, 64, 1,
            1, 1, 1, 1, 1, 1, 1, 1, 1)
PROTOCOL = 'isolated-workloads-v1'


def loop_inventory(result, language):
    """Check named timing specializations in the pinned toolchain's nm output.

    This verifies compiled entry-point coverage, not instructions or timing
    quality. Equivalent C bodies may have the same address. Mojo decimal-copy
    deliberately shares one helper-level control between raw and public.
    """
    if language not in ('c', 'mojo'):
        raise ValueError('unknown fixture language')
    if result['returncode'] != 0:
        raise ValueError('could not inspect compiled timing loops')
    expected = {(layer, mode) for mode in range(len(MODES))
                for layer in (('c',) if language == 'c' else ('public', 'raw'))
                if not (layer == 'raw' and MODES[mode] == 'decimal-copy')}
    entries = {}
    prefix = 'execute_' if language == 'c' else 'overhead::execute'
    for line in result['stdout'].splitlines():
        if prefix not in line:
            continue
        parsed = re.fullmatch(r'([0-9a-fA-F]+)\s+([0-9a-fA-F]+)\s+([tT])\s+(.+)', line)
        if not parsed or int(parsed[2], 16) == 0:
            raise ValueError('malformed timing symbol: ' + line)
        address, size, _, symbol = parsed.groups()
        if language == 'c':
            specialization = re.fullmatch(r'execute_(\d+)', symbol)
            key = ('c', int(specialization[1])) if specialization else None
        else:
            specialization = re.fullmatch(r'overhead::execute\[.+\]\(.+\),raw=(true|false),mode=(\d+)', symbol)
            key = (('raw' if specialization[1] == 'true' else 'public'), int(specialization[2])) if specialization else None
        if key not in expected or key in entries:
            raise ValueError('unexpected or duplicate timing specialization: ' + symbol)
        entries[key] = dict(layer=key[0], mode=MODES[key[1]], symbol=symbol,
                            address=address, size_bytes=int(size, 16))
    if entries.keys() != expected:
        raise ValueError('missing timing specializations: ' + repr(sorted(expected - entries.keys())))
    return [entries[key] for key in sorted(entries)]


def inspect_loops(binary, language):
    command = ['nm', '-S', '--defined-only', str(binary)]
    inspected = dict(command=command, **run(command, 30))
    record = dict(binary_sha256=hashlib.sha256(binary.read_bytes()).hexdigest(), inspection=inspected)
    try:
        record.update(entries=loop_inventory(inspected, language), passed=True)
    except ValueError as error:
        record.update(passed=False, error=str(error))
    path = binary.with_name(binary.name + '-loops.json')
    path.write_text(json.dumps(record, indent=2) + '\n')
    if not record['passed']:
        raise SystemExit('Invalid compiled loop inventory: ' + str(path) + '\n' + record['error'])
    return record


def measurement(result, mode, count, warmup, *, expected=None):
    """Crashes, malformed output, missing completion and wrong checksums fail."""
    if result['returncode'] != 0:
        return None
    lines = result['stdout'].splitlines()
    if len(lines) != 2 or lines[1] != 'overhead passed' or not result['stdout'].endswith('\n'):
        return None
    try:
        actual, iterations, elapsed, checksum, warmed = map(int, lines[0].split())
    except ValueError:
        return None
    if expected is None:
        expected = 1 if mode == -1 else EXPECTED[mode]
    if (actual != mode or iterations != count or elapsed <= 0 or checksum != count * expected
            or warmed != warmup * expected):
        return None
    return dict(count=count, elapsed_ns=elapsed, ns_per_operation=elapsed / count,
                checksum=checksum, warmup_checksum=warmed)


def distribution(values):
    center = statistics.median(values)
    return dict(median=center, min=min(values), max=max(values),
                median_absolute_deviation=statistics.median(abs(v - center) for v in values))


def paired_interval(values):
    """Descriptive bootstrap interval for the median of paired run deltas."""
    rng = random.Random(73)
    bootstrap = sorted(statistics.median(rng.choices(values, k=len(values))) for _ in range(2000))
    return dict(distribution(values), bootstrap_95=[bootstrap[49], bootstrap[1949]])


def summarize(records, modes, repetitions):
    summaries = {}
    for mode in modes:
        rows = [r for r in records if r['mode'] == mode]
        layers = ('c-loader', 'raw') if mode == 'cold' else LAYERS
        by_key = {(r['repetition'], r['layer']): r for r in rows}
        valid = (len(rows) == repetitions * len(layers) and len(by_key) == len(rows)
                 and all((i, layer) in by_key for i in range(repetitions) for layer in layers)
                 and all(r['passed'] for r in rows))
        if not valid:
            summaries[mode] = dict(passed=False)
            continue
        values = {layer: [by_key[i, layer]['metrics']['ns_per_operation'] for i in range(repetitions)]
                  for layer in layers}
        base = 'c-loader' if mode == 'cold' else 'c-checked'
        differences = {layer: paired_interval([a - b for a, b in zip(values[layer], values[base])])
                       for layer in layers if layer != base}
        summaries[mode] = dict(passed=True, ns_per_operation={k: distribution(v) for k, v in values.items()},
                               paired_delta_ns_vs_checked=differences,
                               median_paired_ratio_vs_checked={k: statistics.median(a / b for a, b in zip(v, values[base]))
                                                              for k, v in values.items() if k != base})
    return summaries


def compare_baselines(before, after):
    """Describe changes beyond within-run noise; never infer a portable speed gate.

    Each interval is already computed from paired wrapper/checked-C timings by
    summarize(). Nonoverlap flags a candidate for a controlled rerun; it does
    not account for drift between runs or multiple workload comparisons.
    """
    reasons = []
    for field in ('protocol', 'machine', 'cpu'):
        if before.get(field) != after.get(field) or field not in before:
            reasons.append(field + ' differs or is missing')
    for field in ('route', 'assertions', 'warmup', 'operations', 'target_ms'):
        if (field not in before.get('settings', {})
                or field not in after.get('settings', {})
                or before['settings'][field] != after['settings'][field]):
            reasons.append('settings.' + field + ' differs or is missing')
    def compilers(report):
        return (report.get('versions', {}).get('mojo', {}).get('stdout'),
                report.get('c_compiler', {}).get('stdout'))
    if not all(compilers(before)) or compilers(before) != compilers(after):
        reasons.append('compiler versions differ or are missing')
    for report in (before, after):
        if not report.get('passed') or report.get('settings', {}).get('repetitions', 0) < 7:
            reasons.append('need passing reports with at least seven repetitions')
    def dependency_hashes(report):
        return {p: h for p, h in report.get('source_and_dependency_hashes', {}).items()
                if p == 'pixi.lock' or p.startswith('third_party/') or p.startswith('tests/binding/overhead')}
    if not dependency_hashes(before) or dependency_hashes(before) != dependency_hashes(after):
        reasons.append('dependency or timing fixture hashes differ or are missing')
    if reasons:
        return dict(comparable=False, reasons=sorted(set(reasons)))
    changes = {}
    for mode in before['summary'].keys() & after['summary'].keys():
        first = before['summary'][mode]['paired_delta_ns_vs_checked']
        second = after['summary'][mode]['paired_delta_ns_vs_checked']
        for layer in first.keys() & second.keys():
            old, new = first[layer]['bootstrap_95'], second[layer]['bootstrap_95']
            status = 'higher' if new[0] > old[1] else 'lower' if new[1] < old[0] else 'overlap'
            changes[mode + '/' + layer] = dict(status=status, before_ns=old, after_ns=new,
                                              median_change_ns=second[layer]['median'] - first[layer]['median'])
    return dict(comparable=bool(changes), changes=changes,
                interpretation='Descriptive paired-overhead intervals; confirm candidates on the same idle host.')


def build_c(folder, source, name, flags=()):
    binary, built = build_native(name, 3, folder, source=source, output_name=name, flags=flags,
                                 link_flags=['-ldl'] if source.endswith('loading.c') else None)
    (folder / (name + '-build.json')).write_text(json.dumps(built, indent=2) + '\n')
    if built['returncode']:
        raise SystemExit(built['stderr'])
    return binary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True)
    parser.add_argument('--route', choices=('source', 'package'), default='package')
    parser.add_argument('--assertions', action='store_true')
    parser.add_argument('--modes', default=','.join((*MODES, 'cold')))
    parser.add_argument('--repetitions', type=int, default=9)
    parser.add_argument('--target-ms', type=int, default=150, help='Calibrate shared counts using checked C')
    parser.add_argument('--operations', type=int, default=0, help='Override calibration, useful for semantic checks')
    parser.add_argument('--warmup', type=int, default=10000)
    parser.add_argument('--order-seed', type=int, default=17)
    parser.add_argument('--cpu', type=int, help='Default: first CPU in the allowed affinity set')
    parser.add_argument('--skip-traces', action='store_true', help='Timing replication after validating call counts')
    parser.add_argument('--skip-allocations', action='store_true', help='Skip the Linux/glibc diagnostic interposer')
    parser.add_argument('--baseline', help='Compare against a saved compatible report; descriptive only, no hard timing gate')
    args = parser.parse_args()
    modes = args.modes.split(',')
    if (min(args.repetitions, args.target_ms) < 1 or min(args.operations, args.warmup) < 0
            or not modes or len(set(modes)) != len(modes) or set(modes) - {*MODES, 'cold'}):
        parser.error('invalid modes or measurement settings')
    cpus = sorted(os.sched_getaffinity(0))
    cpu = cpus[0] if args.cpu is None else args.cpu
    if cpu not in cpus:
        parser.error('CPU is outside the allowed affinity set')
    folder = Path(args.output).resolve()
    folder.mkdir(parents=True, exist_ok=False)
    sources = [ROOT / p for p in ('tests/binding/overhead.c', 'tests/binding/overhead_loading.c',
                                  'tests/binding/support.h', 'tests/binding/overhead_allocations.c',
                                  'scripts/benchmark_binding_overhead.py',
                                  'scripts/run_matched_controls.py', 'scripts/verify_docs_examples.py',
                                  'scripts/run_contract_tests.py',
                                  'bindgen/config.py', 'api/cvc5-api.json', 'pixi.lock')]
    sources += list(config.INCLUDE_DIR.rglob('*.h'))
    binary, hashes = build_workload(folder, args.route, 'tests/binding/overhead.mojo',
                                    assertions=args.assertions, extra_inputs=sources)
    binaries = {'raw': binary, 'public': binary,
                'c-checked': build_c(folder, 'tests/binding/overhead.c', 'checked'),
                'c-bare': build_c(folder, 'tests/binding/overhead.c', 'bare', ['-DBARE']),
                'c-loader': build_c(folder, 'tests/binding/overhead_loading.c', 'loader')}
    inventories = {'timing-mojo': inspect_loops(binary, 'mojo'),
                   'timing-c-checked': inspect_loops(binaries['c-checked'], 'c'),
                   'timing-c-bare': inspect_loops(binaries['c-bare'], 'c')}
    # Extract exactly the current loader's lookups; no handwritten API inventory.
    symbols = re.findall(r'self\._lib(cvc5parser|cvc5)\.get_function[^\n]*?\("(cvc5_[^"]+)"\)', config.RAW_FILE.read_text())
    if not symbols or len({name for _, name in symbols}) != len(symbols):
        raise SystemExit('missing or duplicate dynamic symbol manifest')
    manifest = folder / 'symbols.txt'
    manifest.write_text(''.join(f'{int(lib == "cvc5parser")} {name}\n' for lib, name in symbols))
    metadata = provenance(binary, hashes)
    metadata.update(cpu=cpu, c_compiler=run([config.c_compiler(), '--version'], 20),
                    native_symbol_count=len(symbols),
                    binaries={k: hashlib.sha256(v.read_bytes()).hexdigest() for k, v in binaries.items()})
    env = os.environ.copy()
    env['CVC5_MOJO_LIBRARY'] = str(config.BINARY_DIR / 'lib/libcvc5.so')

    def execute(mode, layer, count, warmup, label, repetition=-1, target=None, trace=None, probe=None):
        stem = folder / label
        number = -1 if mode == 'cold' else MODES.index(mode)
        if layer == 'c-loader':
            command = [str(binaries[layer]), env['CVC5_MOJO_LIBRARY'],
                       str(config.BINARY_DIR / 'lib/libcvc5parser.so'), str(manifest),
                       config.pinned()['version'], str(stem)]
        elif layer.startswith('c-'):
            command = [str(target or binaries[layer]), str(number), str(count), str(warmup), str(stem)]
        else:
            command = [str(target or binary), layer, 'cold' if number == -1 else str(number),
                       str(count), str(warmup), str(stem)]
        command = ['taskset', '-c', str(cpu), *command]
        overrides = {'CVC5_BINDING_TRACE': str(trace)} if trace else {}
        if probe:
            overrides['LD_PRELOAD'] = str(probe)
        execution = run(command, 120, env={**env, **overrides})
        observed = execution.copy()
        allocations = None
        if probe:
            lines = observed['stdout'].splitlines(keepends=True)
            if len(lines) == 3 and lines[2].startswith('allocations ') and lines[2].endswith('\n'):
                fields = lines[2].split()[1:]
                if len(fields) == len(ALLOCATION_FIELDS) and all(s.isdigit() for s in fields):
                    allocations = dict(zip(ALLOCATION_FIELDS, map(int, fields)))
                    observed['stdout'] = ''.join(lines[:2])
        metrics = measurement(observed, number, count, warmup)
        loaded = libraries(Path(str(stem) + '.maps'))
        row = dict(mode=mode, layer=layer, repetition=repetition, metrics=metrics,
                   passed=metrics is not None and loaded['matched'] and (not probe or allocations is not None),
                   allocations=allocations, libraries=loaded,
                   command=command, run=execution)
        stem.with_suffix('.json').write_text(json.dumps(row, indent=2) + '\n')
        if not row['passed']:
            raise SystemExit('Invalid benchmark observation: ' + str(stem) + '\n' + execution['stderr'])
        return row

    counts = {}
    for mode in modes:
        if mode == 'cold':
            counts[mode] = 1
        elif args.operations:
            counts[mode] = args.operations
        else:
            calibration = execute(mode, 'c-checked', 32768, args.warmup, 'calibrate-' + mode)
            rate = calibration['metrics']['ns_per_operation']
            counts[mode] = min(100_000_000, max(32768, math.ceil(args.target_ms * 1e6 / rate)))
    records = []
    rng = random.Random(args.order_seed)
    for repetition in range(args.repetitions):
        order = modes.copy()
        rng.shuffle(order)
        for mode in order:
            layers = ['c-loader', 'raw'] if mode == 'cold' else list(LAYERS)
            rng.shuffle(layers)
            for layer in layers:
                row = execute(mode, layer, counts[mode], 0 if mode == 'cold' else args.warmup,
                              f'run-{repetition}-{mode}-{layer}', repetition)
                records.append(row)
                print(f'{repetition} {mode} {layer}: {row["metrics"]["ns_per_operation"]:.1f} ns/op', flush=True)
        (folder / 'timings.json').write_text(json.dumps(records, indent=2) + '\n')

    traces = {}
    if not args.skip_traces and any(mode != 'cold' for mode in modes):
        build_folder = folder / 'trace-build'
        build_folder.mkdir()
        trace_path = build_folder / 'calls.txt'
        trace_binary, _ = build_workload(build_folder, args.route, 'tests/binding/overhead.mojo',
                                        assertions=args.assertions,
                                        defines=[f'CVC5_MOJO_TRACE={trace_path}'], extra_inputs=sources)
        c_trace = build_c(build_folder, 'tests/binding/overhead.c', 'checked', ['-DTRACE_PROBE'])
        inventories.update({'trace-mojo': inspect_loops(trace_binary, 'mojo'),
                            'trace-c-checked': inspect_loops(c_trace, 'c')})
        pairs = reference_pairs(json.loads(config.SNAPSHOT_FILE.read_text()))
        for mode in modes:
            if mode == 'cold':
                continue
            calls = {}
            for layer in ('c-checked', 'raw', 'public'):
                counters = []
                for count in (1, 33):
                    trace_path.unlink(missing_ok=True)
                    label = f'trace-{mode}-{layer}-{count}'
                    execute(mode, layer, count, 0, label,
                            target=trace_binary if layer in ('raw', 'public') else c_trace, trace=trace_path)
                    if not trace_path.is_file():
                        raise SystemExit('missing native trace: ' + label)
                    counters.append(Counter(trace_path.read_text().splitlines()))
                    trace_path.rename(folder / (label + '.calls'))
                calls[layer] = per_operation(*counters)
            traces[mode] = dict(calls=calls, passed=calls['c-checked'] == calls['raw']
                               and equivalent_calls(calls['c-checked'], calls['public'], pairs))
    allocations = {}
    if not args.skip_allocations and any(mode != 'cold' for mode in modes):
        build_folder = folder / 'allocation-build'
        build_folder.mkdir()
        probe = build_folder / 'allocations.so'
        command = [config.c_compiler(), '-shared', '-fPIC', '-std=gnu11', '-O2', '-fno-builtin',
                   '-Wall', '-Wextra', '-Werror', 'tests/binding/overhead_allocations.c', '-o', str(probe)]
        built = dict(command=command, **run(command, 120))
        (build_folder / 'probe-build.json').write_text(json.dumps(built, indent=2) + '\n')
        if built['returncode']:
            raise SystemExit(built['stderr'])
        c_probe = build_c(build_folder, 'tests/binding/overhead.c', 'checked', ['-DALLOCATION_PROBE', '-ldl'])
        mojo_probe, _ = build_workload(build_folder, args.route, 'tests/binding/overhead.mojo',
                                      assertions=args.assertions,
                                      defines=[f'CVC5_OVERHEAD_PROBE={probe}'], extra_inputs=sources)
        inventories.update({'allocation-mojo': inspect_loops(mojo_probe, 'mojo'),
                            'allocation-c-checked': inspect_loops(c_probe, 'c')})
        for mode in modes:
            if mode == 'cold':
                continue
            allocations[mode] = {}
            for layer in ('c-checked', 'raw', 'public'):
                counters = []
                for count in (1000, 2000):
                    row = execute(mode, layer, count, 10000, f'alloc-{mode}-{layer}-{count}',
                                  target=c_probe if layer == 'c-checked' else mojo_probe, probe=probe)
                    counters.append(Counter(row['allocations']))
                allocations[mode][layer] = per_operation(*counters, difference=1000)
    summary = summarize(records, modes, args.repetitions)
    passed = all(r['passed'] for r in summary.values()) and all(r['passed'] for r in traces.values())
    report = dict(passed=passed, protocol=PROTOCOL, compiled_loops=inventories,
                  settings=vars(args), **metadata, counts=counts, records=records,
                  native_calls_per_operation=traces, interposed_allocations_per_operation=allocations,
                  summary=summary)
    if args.baseline:
        report['baseline_comparison'] = compare_baselines(json.loads(Path(args.baseline).read_text()), report)
    (folder / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
    print('BINDING OVERHEAD BASELINE PASS' if passed else 'BINDING OVERHEAD BASELINE FAILED', flush=True)
    return int(not passed)


if __name__ == '__main__':
    raise SystemExit(main())
