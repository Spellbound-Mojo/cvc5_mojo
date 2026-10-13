"""Compare solver lifetimes over identical, nonoverlapping integer requests."""

from std.sys import argv
from std.time import perf_counter_ns
from cvc5_mojo import TermManager
from workloads import Incremental, Metrics, initialize_samples


def batch(tm: TermManager, size: Int, seed: Int, mut metrics: Metrics,
          mut next_sample: Int, path: String, record: Bool) raises:
    # Charge construction to the first request. Wall throughput also includes
    # destruction on return, metric recording, and checkpoint I/O.
    var before = Int(perf_counter_ns())
    var work = Incremental(False, tm)
    for _ in range(size):
        work.step(seed + metrics.count)
        metrics.observe(Int(perf_counter_ns()) - before)
        if record and Int(perf_counter_ns()) >= next_sample:
            metrics.sample(path)
            next_sample = Int(perf_counter_ns()) + 1000000000
        before = Int(perf_counter_ns())


def main() raises:
    var args = argv()
    if len(args) != 7:
        raise Error("expected: batch_size requests seconds warmup_requests seed samples.tsv")
    var size = Int(args[1])
    var requests = Int(args[2])
    var seconds = Int(args[3])
    var warmup = Int(args[4])
    var seed = Int(args[5])
    var path = args[6]
    if size < 1 or requests < 1 or seconds < 0 or warmup < 0 or seed < 0:
        raise Error("invalid benchmark argument")
    var tm = TermManager()
    var warm_metrics = Metrics()
    var next_sample = 0
    while warm_metrics.count < warmup:
        batch(tm, min(size, warmup - warm_metrics.count), seed,
              warm_metrics, next_sample, path, False)
    initialize_samples(path)
    var metrics = Metrics()
    metrics.sample(path)
    next_sample = metrics.started + 1000000000
    while metrics.count < requests or Int(perf_counter_ns()) - metrics.started < seconds * 1000000000:
        var remaining = min(size, requests - metrics.count) if seconds == 0 else size
        batch(tm, remaining, seed, metrics, next_sample, path, True)
    metrics.sample(path)
    print("completed", metrics.count, "requests")
