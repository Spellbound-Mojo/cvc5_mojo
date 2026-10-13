"""Run isolated CAS-style workloads using already installed, pinned dependencies.

No fetch task is invoked. Memory is assessed after warmup; latency histograms
measure a complete workload request, including validation, not individual FFI
calls. Parallel runs measure service contention, not single-core benchmarks.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
import csv
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import statistics
import subprocess
import time

from docs_contract import ROOT
from verify_docs_examples import precompile, run, stop
from bindgen import config

WORKLOADS = ('incremental', 'term-churn', 'algebra', 'parser', 'bounded-jobs', 'solver-batches',
             'synthesis-bounded', 'resource-limits')
CONTROL = 'synthesis-shared-tm'


def samples(path):
    """Parse only complete checkpoints; a killed process can leave a partial line."""
    if not path.exists():
        return []
    lines = path.read_text().splitlines(keepends=True)
    rows = []
    for row in csv.DictReader([line for line in lines if line.endswith('\n')], delimiter='\t'):
        rows.append({k: json.loads(v) if k == 'histogram' else int(v) for k, v in row.items()})
    return rows


def slope(rows):
    """Least-squares RSS slope in KiB/second."""
    xs = [r['elapsed_ns'] / 1e9 for r in rows]
    ys = [r['rss_kib'] for r in rows]
    mx, my = statistics.mean(xs), statistics.mean(ys)
    denominator = sum((x - mx) ** 2 for x in xs)
    return sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / denominator if denominator else 0.0


def percentile_upper_ns(histogram, fraction):
    target = math.ceil(sum(histogram) * fraction)
    count = 0
    for bucket, n in enumerate(histogram):
        count += n
        if count >= target and target:
            return (1 << (bucket + 1)) - 1
    return None


def analyze(rows, peak_budget_kib, drift_budget_kib, slope_budget_kib_s):
    if len(rows) < 2 or rows[-1]['requests'] <= 0:
        return dict(assessed=False, reason='no completed measurement window')
    first, last = rows[0], rows[-1]
    quarter = max(1, len(rows) // 4)
    tail = rows[len(rows) // 2:]
    drift = statistics.median(r['rss_kib'] for r in rows[-quarter:]) - statistics.median(r['rss_kib'] for r in rows[:quarter])
    peak = max(r['rss_kib'] for r in rows) - first['rss_kib']
    growth = slope(tail)
    # Short probes establish correctness only, not a memory plateau.
    assessed = last['elapsed_ns'] >= 60e9 and len(rows) >= 10
    violations = []
    if assessed:
        if peak > peak_budget_kib:
            violations.append('peak growth')
        if drift > drift_budget_kib:
            violations.append('first-to-last-quarter drift')
        if growth > slope_budget_kib_s:
            violations.append('second-half slope')
    return dict(assessed=assessed, memory_passed=not violations if assessed else None, violations=violations,
                seconds=last['elapsed_ns'] / 1e9, requests=last['requests'],
                requests_per_second=last['requests'] / (last['elapsed_ns'] / 1e9),
                baseline_rss_kib=first['rss_kib'], final_rss_kib=last['rss_kib'],
                peak_growth_kib=peak, quarter_drift_kib=drift, tail_slope_kib_s=growth,
                mean_request_us=last['work_ns'] / last['requests'] / 1000,
                max_request_us=last['max_request_ns'] / 1000,
                percentile_upper_us={str(p): percentile_upper_ns(last['histogram'], p / 100) / 1000
                                     for p in (50, 95, 99)})


def process_rss_kib(pid):
    try:
        for line in Path(f'/proc/{pid}/status').read_text().splitlines():
            if line.startswith('VmRSS:'):
                return int(line.split()[1])
    except (FileNotFoundError, ProcessLookupError):
        pass
    return 0


def fingerprint(paths):
    # Pixi environments may live outside the checkout. Preserve dependency
    # identity in reports without requiring a repository-relative prefix.
    return {str(p.relative_to(ROOT) if p.is_relative_to(ROOT) else p):
            hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(paths)}


def build_workload(folder, route, source='tests/soak/workloads.mojo', *,
                   optimization=3, assertions=True, defines=(), extra_inputs=()):
    """Build a checked workload against cached dependencies; never fetch."""
    required = [config.APN_PACKAGE_DIR / 'apn_mojo.mojoc', config.BINARY_DIR / 'lib/libcvc5.so',
                config.BINARY_DIR / 'lib/libcvc5parser.so']
    for path in required:
        if not path.is_file():
            raise SystemExit(f'cached dependency missing: {path}; provision it before running')
    inputs = list((ROOT / 'src').rglob('*.mojo')) + list((ROOT / 'tests/soak').glob('*.mojo'))
    inputs += list((ROOT / 'scripts').glob('*soak*.py')) + list((ROOT / 'scripts').glob('*batch*.py'))
    inputs += [ROOT / source, ROOT / 'tests/smoke/memory_support.mojo', *required, *extra_inputs]
    input_hashes = fingerprint(inputs)
    package_record = None
    include = 'src'
    if route == 'package':
        include, package_record = precompile(folder, 300)
    binary = folder / Path(source).stem
    flags = ['-D', 'ASSERT=all'] if assertions else []
    for define in defines:
        flags += ['-D', define]
    command = ['mojo', 'build', '--Werror', f'-O{optimization}', *flags, '-I', str(include),
               '-I', 'tests/smoke', source, '-o', str(binary)]
    compiled = run(command, 600)
    (folder / 'build.json').write_text(json.dumps(dict(command=command, compile=compiled, package=package_record), indent=2) + '\n')
    if compiled['returncode'] != 0:
        raise SystemExit(compiled['stderr'])
    return binary, input_hashes


def monitor(command, folder, name, timeout, memory_cap_mib, *, env_overrides=None):
    """Run one isolated worker with shared RSS and wall-clock watchdogs."""
    env = os.environ.copy()
    env['CVC5_MOJO_LIBRARY'] = str(config.BINARY_DIR / 'lib/libcvc5.so')
    env.update(env_overrides or {})
    start = time.monotonic()
    reason = None
    peak_rss = 0
    with (folder / f'{name}.stdout').open('w') as out, (folder / f'{name}.stderr').open('w') as err:
        process = subprocess.Popen(command, cwd=ROOT, env=env, stdout=out, stderr=err, start_new_session=True)
        try:
            while process.poll() is None:
                peak_rss = max(peak_rss, process_rss_kib(process.pid))
                if peak_rss > memory_cap_mib * 1024:
                    reason = 'memory cap'
                    break
                if time.monotonic() - start > timeout:
                    reason = 'watchdog timeout'
                    break
                time.sleep(0.2)
        finally:
            if process.poll() is None:
                stop(process)
    return dict(stop_reason=reason, returncode=process.returncode, wall_seconds=time.monotonic() - start,
                watchdog_peak_rss_kib=peak_rss, stderr=(folder / f'{name}.stderr').read_text()[-4000:])


def provenance(binary, input_hashes):
    quota = Path('/sys/fs/cgroup/cpu.max')
    cpu_info = Path('/proc/cpuinfo')
    model = next((line.partition(':')[2].strip() for line in cpu_info.read_text().splitlines()
                  if line.startswith('model name')), None) if cpu_info.exists() else None
    return dict(versions=dict(cvc5=config.pinned(), apn=config.apn_installed(), mojo=run(['mojo', '--version'], 20)),
                machine=dict(platform=platform.platform(), cpu_model=model, cpu_count=os.cpu_count(),
                             available_cpus=len(os.sched_getaffinity(0)),
                             cpu_quota=quota.read_text().strip() if quota.exists() else None),
                source_and_dependency_hashes=input_hashes,
                binary_sha256=hashlib.sha256(binary.read_bytes()).hexdigest())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, help='A fresh report directory')
    parser.add_argument('--seconds', type=int, default=180, help='Measured seconds per required workload')
    parser.add_argument('--warmup', type=int, default=15)
    parser.add_argument('--jobs', type=int, default=1, help='Concurrent isolated workers')
    parser.add_argument('--seeds', default='1', help='Comma-separated nonnegative starting offsets')
    parser.add_argument('--only', choices=(*WORKLOADS, CONTROL))
    parser.add_argument('--control-seconds', type=int, default=30, help='Shorter diagnostic control duration')
    parser.add_argument('--route', choices=('source', 'package'), default='package')
    parser.add_argument('--memory-cap-mib', type=int, default=512, help='Absolute process RSS watchdog')
    parser.add_argument('--peak-budget-mib', type=int, default=32)
    parser.add_argument('--drift-budget-mib', type=int, default=8)
    parser.add_argument('--slope-budget-kib-s', type=float, default=64)
    args = parser.parse_args()
    seeds = [int(s) for s in args.seeds.split(',')]
    if (min(args.seconds, args.control_seconds, args.jobs, args.memory_cap_mib) < 1
            or args.warmup < 0 or not seeds or min(seeds) < 0 or len(set(seeds)) != len(seeds)
            or min(args.peak_budget_mib, args.drift_budget_mib, args.slope_budget_kib_s) < 0):
        parser.error('invalid duration, seed, concurrency, or budget')
    folder = Path(args.output).resolve()
    folder.mkdir(parents=True, exist_ok=False)
    binary, input_hashes = build_workload(folder, args.route)

    def execute(task):
        mode, seed = task
        control = mode == CONTROL
        seconds = args.control_seconds if control else args.seconds
        name = f'{mode}-{seed}'
        path = folder / f'{name}.tsv'
        print(f'RUN {name}: {seconds}s after {args.warmup}s warmup', flush=True)
        execution = monitor([str(binary), mode, str(seconds), str(args.warmup), str(seed), str(path)],
                            folder, name, seconds + args.warmup + 20, args.memory_cap_mib)
        reason = execution['stop_reason']
        data = samples(path)
        metrics = analyze(data, args.peak_budget_mib * 1024, args.drift_budget_mib * 1024, args.slope_budget_kib_s)
        complete = (reason is None and execution['returncode'] == 0 and metrics.get('seconds', 0) >= seconds
                    and len(data) >= 2)
        passed = complete and metrics.get('memory_passed') is not False
        # The control diagnoses upstream growth; a crash/assertion/timeout is
        # still a failure. A deliberate RSS stop is recorded as incomplete.
        acceptable_control = control and (complete or reason == 'memory cap')
        record = dict(name=name, mode=mode, seed=seed, diagnostic=control, passed=passed,
                      gate_passed=acceptable_control if control else passed, complete=complete,
                      **execution, metrics=metrics, samples=path.name)
        (folder / f'{name}.json').write_text(json.dumps(record, indent=2) + '\n')
        status = 'CONTROL' if acceptable_control else 'PASS' if passed else 'FAIL'
        print(f'{status} {name}: {metrics.get("requests", 0)} requests; '
              f'RSS drift {metrics.get("quarter_drift_kib", 0):.0f} KiB; '
              f'tail slope {metrics.get("tail_slope_kib_s", 0):.1f} KiB/s; {reason or "completed"}', flush=True)
        if not record['gate_passed']:
            print(record['stderr'], flush=True)
        return record

    selected = [args.only] if args.only else [*WORKLOADS, CONTROL]
    tasks = [(mode, seed) for seed in seeds for mode in selected]
    with ThreadPoolExecutor(max_workers=args.jobs) as executor:
        records = list(executor.map(execute, tasks))
    result = dict(passed=all(r['gate_passed'] for r in records), settings=vars(args),
                  **provenance(binary, input_hashes), records=records)
    (folder / 'report.json').write_text(json.dumps(result, indent=2) + '\n')
    print('SOAK PASS' if result['passed'] else 'SOAK FAILED', flush=True)
    return int(not result['passed'])


if __name__ == '__main__':
    raise SystemExit(main())
