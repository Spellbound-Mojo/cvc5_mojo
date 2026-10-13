"""Measure solver recycling with cached dependencies and one worker at a time."""
import argparse
import json
from pathlib import Path
import random
import statistics

from run_soak_tests import ROOT, analyze, build_workload, monitor, provenance, samples


def summarize(records, expected_runs, memory_budget_mib, throughput_fraction):
    """Choose the smallest measured batch within the requested throughput band.

    Every expected repetition must pass. Short screens remain provisional;
    they cannot establish a memory plateau even when they fit the RSS budget.
    """
    groups = {}
    for record in records:
        groups.setdefault(record['batch_size'], []).append(record)
    summaries = []
    for size, rows in sorted(groups.items()):
        valid = len(rows) == expected_runs and all(r['passed'] for r in rows)
        rates = [r['metrics']['requests_per_second'] for r in rows if r['complete']]
        peak = max(r['peak_rss_kib'] for r in rows)
        summaries.append(dict(batch_size=size, runs=len(rows), eligible=valid and peak <= memory_budget_mib * 1024,
                              median_requests_per_second=statistics.median(rates) if rates else None,
                              min_requests_per_second=min(rates) if rates else None,
                              max_requests_per_second=max(rates) if rates else None,
                              peak_rss_mib=peak / 1024,
                              memory_assessed=valid and all(r['metrics'].get('assessed', False) for r in rows)))
    eligible = [r for r in summaries if r['eligible']]
    best = max((r['median_requests_per_second'] for r in eligible), default=None)
    candidates = [r for r in eligible if r['median_requests_per_second'] >= best * throughput_fraction]
    chosen = min(candidates, key=lambda r: r['batch_size']) if candidates else None
    return dict(batches=summaries, fastest_eligible_requests_per_second=best,
                recommended_batch_size=chosen['batch_size'] if chosen else None,
                recommendation_memory_assessed=chosen['memory_assessed'] if chosen else False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True)
    parser.add_argument('--sizes', default='1,8,32,128,512,2048,8192')
    parser.add_argument('--seeds', default='1,1048576', help='Each offset is a repetition over the same stream for every size')
    parser.add_argument('--requests', type=int, default=16384, help='Minimum measured requests; exact when --seconds=0')
    parser.add_argument('--seconds', type=int, default=0, help='Optional minimum duration; finish the last batch')
    parser.add_argument('--warmup-requests', type=int, default=512)
    parser.add_argument('--order-seed', type=int, default=17)
    parser.add_argument('--memory-budget-mib', type=int, default=128)
    parser.add_argument('--memory-cap-mib', type=int, default=512)
    parser.add_argument('--throughput-fraction', type=float, default=.95)
    parser.add_argument('--timeout', type=int, default=600, help='Total watchdog seconds per process including warmup')
    parser.add_argument('--route', choices=('source', 'package'), default='package')
    args = parser.parse_args()
    sizes = [int(n) for n in args.sizes.split(',')]
    seeds = [int(n) for n in args.seeds.split(',')]
    if (not sizes or min(sizes) < 1 or len(set(sizes)) != len(sizes)
            or not seeds or min(seeds) < 0 or len(set(seeds)) != len(seeds)
            or min(args.requests, args.memory_budget_mib, args.timeout) < 1
            or min(args.seconds, args.warmup_requests) < 0
            or args.memory_cap_mib < args.memory_budget_mib
            or not 0 < args.throughput_fraction <= 1):
        parser.error('invalid sizes, offsets, duration, or budget')
    folder = Path(args.output).resolve()
    folder.mkdir(parents=True, exist_ok=False)
    binary, hashes = build_workload(folder, args.route, 'tests/soak/batch_sizes.mojo')
    metadata = provenance(binary, hashes)
    records = []
    rng = random.Random(args.order_seed)
    for seed in seeds:
        order = sizes.copy()
        rng.shuffle(order)
        for size in order:
            name = f'batch-{size}-{seed}'
            path = folder / f'{name}.tsv'
            print(f'RUN {name}', flush=True)
            execution = monitor([str(binary), str(size), str(args.requests), str(args.seconds),
                                 str(args.warmup_requests), str(seed), str(path)],
                                folder, name, args.timeout, args.memory_cap_mib)
            data = samples(path)
            metrics = analyze(data, 32 * 1024, 8 * 1024, 64)
            complete = (execution['stop_reason'] is None and execution['returncode'] == 0
                        and metrics.get('seconds', 0) >= args.seconds and len(data) >= 2
                        and metrics.get('requests', 0) >= args.requests
                        and (args.seconds != 0 or metrics['requests'] == args.requests)
                        and sum(data[-1]['histogram']) == metrics['requests'])
            # Linux's lifetime high-water mark includes warmup and catches
            # intra-batch peaks that periodic RSS sampling can miss.
            peak = max([execution['watchdog_peak_rss_kib'], *(r['peak_rss_kib'] for r in data)])
            passed = complete and peak <= args.memory_budget_mib * 1024 and metrics.get('memory_passed') is not False
            record = dict(name=name, batch_size=size, seed=seed, complete=complete, passed=passed,
                          peak_rss_kib=peak, metrics=metrics, samples=path.name, **execution)
            records.append(record)
            (folder / f'{name}.json').write_text(json.dumps(record, indent=2) + '\n')
            print(f'{"PASS" if passed else "FAIL"} {name}: '
                  f'{metrics.get("requests_per_second", 0):.1f} requests/s; peak {peak / 1024:.2f} MiB', flush=True)
            if not complete:
                print(execution['stderr'], flush=True)
            report = dict(settings=vars(args), **metadata, records=records,
                          summary=summarize(records, len(seeds), args.memory_budget_mib, args.throughput_fraction))
            (folder / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
    return int(not all(r['passed'] for r in records))


if __name__ == '__main__':
    raise SystemExit(main())
