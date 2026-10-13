"""Independent Python-binding controls for synthesis and changing-term soaks.

Use the cached oracle environment. Repeating the same specification through
the official bindings distinguishes native term-manager growth from the Mojo
handle policy. The Python wheel and C release binary are different builds.
"""
import argparse
from importlib.metadata import version
import json
import os
from pathlib import Path
import sys
import time

import cvc5
from cvc5 import Kind

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'scripts'))
from run_soak_tests import analyze, process_rss_kib
from bindgen import config


def synthesis_request(tm, index):
    solver = cvc5.Solver(tm)
    solver.setOption('sygus', 'true')
    solver.setOption('incremental', 'false')
    solver.setOption('tlimit-per', '1000')
    solver.setLogic('LIA')
    integer = tm.getIntegerSort()
    x, start = tm.mkVar(integer, 'x'), tm.mkVar(integer, 'Start')
    k = tm.mkInteger(index % 7 + 1)
    grammar = solver.mkGrammar([x], [start])
    grammar.addRules(start, [x, k, tm.mkTerm(Kind.ADD, x, k), tm.mkTerm(Kind.SUB, x, k)])
    f = solver.synthFun('f', [x], integer, grammar)
    v = solver.declareSygusVar('v', integer)
    offset = tm.mkInteger(index % 7 + 1 + (1 if index % 4 == 0 else 0))
    solver.addSygusConstraint(tm.mkTerm(Kind.EQUAL, tm.mkTerm(Kind.APPLY_UF, f, v), tm.mkTerm(Kind.ADD, v, offset)))
    result = solver.checkSynth()
    if index % 4 == 0:
        assert result.hasNoSolution()
    else:
        assert result.hasSolution()
        solution = solver.getSynthSolution(f)
        checker = cvc5.Solver(tm)
        checker.setLogic('QF_LIA')
        checker.setOption('incremental', 'true')
        checker.setOption('produce-models', 'true')
        checker.setOption('tlimit-per', '1000')
        value = tm.mkConst(integer, 'input')
        checker.assertFormula(tm.mkTerm(Kind.NOT, tm.mkTerm(Kind.EQUAL,
                              tm.mkTerm(Kind.APPLY_UF, solution, value), tm.mkTerm(Kind.ADD, value, k))))
        assert checker.checkSat().isUnsat()


def incremental_request(tm=None, proofs=True, reset=False):
    """Keep an SMT owner graph alive while each request introduces new constants."""
    tm = tm if tm is not None else cvc5.TermManager()
    solver = cvc5.Solver(tm)
    solver.setLogic('QF_LIA')
    for key in ('incremental', 'produce-models', 'produce-unsat-cores'):
        solver.setOption(key, 'true')
    if proofs:
        solver.setOption('produce-proofs', 'true')
    solver.setOption('tlimit-per', '1000')
    x, y = tm.mkConst(tm.getIntegerSort(), 'x'), tm.mkConst(tm.getIntegerSort(), 'y')

    def step(n):
        xv, yv = tm.mkInteger(n), tm.mkInteger(2 * n + 1)
        solver.push()
        solver.assertFormula(x.eqTerm(xv))
        solver.assertFormula(y.eqTerm(yv))
        assert solver.checkSat().isSat()
        values = solver.getValue([x, y])
        assert values[0].getIntegerValue() == n
        assert values[1].getIntegerValue() == 2 * n + 1
        solver.push()
        solver.assertFormula(x.eqTerm(xv).notTerm())
        assert solver.checkSat().isUnsat()
        assert solver.getUnsatCore()
        if proofs:
            proof = solver.getProof()
            assert proof
            _ = proof[0].getChildren()
        solver.pop()
        assert solver.checkSat().isSat()
        solver.pop()
        assert not solver.getAssertions()
        assert values[0].getIntegerValue() == n
        if reset and n % 8 == 0:
            solver.resetAssertions()
    return step


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mode', choices=('bounded', 'shared', 'term-churn', 'term-churn-bounded',
                                           'term-churn-no-proofs', 'term-churn-reset', 'solver-batches'), required=True)
    parser.add_argument('--seconds', type=int, default=30)
    parser.add_argument('--warmup', type=int, default=5)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    if version('cvc5') != config.pinned()['version']:
        parser.error('the oracle wheel must match the pin')
    if args.seconds < 1 or args.warmup < 0:
        parser.error('invalid duration')
    shared = cvc5.TermManager() if args.mode in ('shared', 'solver-batches') else None
    if args.mode == 'term-churn':
        request = incremental_request()
    elif args.mode == 'term-churn-no-proofs':
        request = incremental_request(proofs=False)
    elif args.mode == 'term-churn-reset':
        request = incremental_request(reset=True)
    elif args.mode in ('term-churn-bounded', 'solver-batches'):
        def request(index):
            job = incremental_request(shared)
            for offset in range(8):
                job(index + offset)
    else:
        def request(index):
            synthesis_request(shared if shared is not None else cvc5.TermManager(), index)
    index = 1
    start = time.monotonic()
    while time.monotonic() - start < args.warmup:
        request(index)
        index += 1
    start = time.monotonic_ns()
    count, work_ns, max_ns = 0, 0, 0
    histogram = [0] * 64
    records = []

    def sample():
        rss = process_rss_kib(os.getpid())
        if rss > 512 * 1024:
            raise RuntimeError('oracle process exceeded the 512 MiB RSS cap')
        records.append(dict(elapsed_ns=time.monotonic_ns() - start, requests=count,
                            rss_kib=rss, work_ns=work_ns, max_request_ns=max_ns, histogram=histogram.copy()))

    sample()
    next_sample = start + 1_000_000_000
    while time.monotonic_ns() - start < args.seconds * 1_000_000_000:
        before = time.monotonic_ns()
        request(index)
        elapsed = time.monotonic_ns() - before
        count += 1
        work_ns += elapsed
        max_ns = max(max_ns, elapsed)
        histogram[elapsed.bit_length() - 1] += 1
        index += 1
        if time.monotonic_ns() >= next_sample:
            sample()
            next_sample = time.monotonic_ns() + 1_000_000_000
    sample()
    result = dict(mode=args.mode, cvc5_wheel=version('cvc5'), correctness_passed=True,
                  metrics=analyze(records, 32768, 8192, 64), samples=records)
    path = Path(args.output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, indent=2) + '\n')
    print(args.mode, json.dumps(result['metrics']), flush=True)


if __name__ == '__main__':
    main()
