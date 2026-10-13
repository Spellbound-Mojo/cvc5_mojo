"""CAS-style service workloads with correctness checks and bounded input vocabularies.

Run through scripts/run_soak_tests.py, which builds with assertions, monitors
the process, and evaluates the samples. A request includes all work in step().
"""

from std.sys import argv
from std.testing import assert_equal, assert_true
from std.time import perf_counter_ns
from cvc5_mojo import InputLanguage, InputParser, Kind, Solver, Term, TermManager, UnknownExplanation
from memory_support import resident_kb, peak_resident_kb


trait Workload(Movable):
    def step(self, index: Int) raises:
        ...


def configure(solver: Solver, logic: String) raises:
    solver.setLogic(logic)
    solver.setOption("incremental", "true")
    solver.setOption("produce-models", "true")
    solver.setOption("tlimit-per", "1000")


struct Incremental(Workload):
    var finite_vocabulary: Bool
    var tm: TermManager
    var solver: Solver
    var x: Term
    var y: Term

    def __init__(out self, finite_vocabulary: Bool = True, tm: Optional[TermManager] = None) raises:
        self.finite_vocabulary = finite_vocabulary
        self.tm = tm.value() if tm else TermManager()
        self.solver = Solver(self.tm)
        configure(self.solver, "QF_LIA")
        self.solver.setOption("produce-unsat-cores", "true")
        self.solver.setOption("produce-proofs", "true")
        self.x = self.tm.mkConst(self.tm.getIntegerSort(), "x")
        self.y = self.tm.mkConst(self.tm.getIntegerSort(), "y")

    def step(self, index: Int) raises:
        var n = index % 127 if self.finite_vocabulary else index
        var x_value = self.tm.mkInteger(n)
        var y_value = self.tm.mkInteger(2 * n + 1)
        self.solver.push()
        self.solver.assertFormula(self.x.eqTerm(x_value))
        self.solver.assertFormula(self.y.eqTerm(y_value))
        assert_true(self.solver.checkSat().isSat())
        var values = self.solver.getValue([self.x, self.y])
        assert_equal(String(values[0].getIntegerValue()), String(n))
        assert_equal(String(values[1].getIntegerValue()), String(2 * n + 1))
        self.solver.push()
        self.solver.assertFormula(self.x.eqTerm(x_value).notTerm())
        assert_true(self.solver.checkSat().isUnsat())
        assert_true(len(self.solver.getUnsatCore()) > 0)
        var proofs = self.solver.getProof()
        assert_true(len(proofs) > 0)
        _ = proofs[0].getChildren()
        self.solver.pop()
        assert_true(self.solver.checkSat().isSat())
        self.solver.pop()
        assert_equal(len(self.solver.getAssertions()), 0)
        # Values remain usable across solver state changes.
        assert_equal(String(values[0].getIntegerValue()), String(n))


struct Algebra(Workload):
    var tm: TermManager
    var solver: Solver
    var x: Term
    var y: Term

    def __init__(out self) raises:
        self.tm = TermManager()
        self.solver = Solver(self.tm)
        configure(self.solver, "QF_NRA")
        self.x = self.tm.mkConst(self.tm.getRealSort(), "x")
        self.y = self.tm.mkConst(self.tm.getRealSort(), "y")

    def step(self, index: Int) raises:
        var k = self.tm.mkReal(String(index % 31 + 1, "/3"))
        var sum = self.tm.mkTerm(Kind.ADD, self.x, self.y)
        var lhs = self.tm.mkTerm(Kind.MULT, k, sum)
        var rhs = self.tm.mkTerm(Kind.ADD, self.tm.mkTerm(Kind.MULT, k, self.x), self.tm.mkTerm(Kind.MULT, k, self.y))
        self.solver.push()
        self.solver.assertFormula(lhs.eqTerm(rhs).notTerm())
        assert_true(self.solver.checkSat().isUnsat(), "distributivity must be valid")
        self.solver.pop()
        # Reject a tempting but invalid rewrite, with a known counterexample.
        var square = self.tm.mkTerm(Kind.MULT, sum, sum)
        var wrong = self.tm.mkTerm(Kind.ADD, self.tm.mkTerm(Kind.MULT, self.x, self.x), self.tm.mkTerm(Kind.MULT, self.y, self.y))
        self.solver.push()
        self.solver.assertFormula(self.x.eqTerm(k))
        self.solver.assertFormula(self.y.eqTerm(k))
        self.solver.assertFormula(square.eqTerm(wrong).notTerm())
        assert_true(self.solver.checkSat().isSat(), "the missing cross term must have a counterexample")
        assert_equal(self.solver.getValue(self.x).getRealValue(), k.getRealValue())
        assert_true(self.solver.getValue(square) != self.solver.getValue(wrong))
        self.solver.pop()


def invoke(parser: InputParser, solver: Solver, text: String) raises:
    parser.setStringInput(InputLanguage.SMT_LIB_2_6, text, "soak")
    var symbols = parser.getSymbolManager()
    while True:
        var command = parser.nextCommand()
        if command.isNull():
            break
        _ = command.invoke(solver, symbols)


struct Parsing(Workload):
    var tm: TermManager
    var solver: Solver
    var parser: InputParser
    var x: Term
    var text: Term

    def __init__(out self) raises:
        self.tm = TermManager()
        self.solver = Solver(self.tm)
        configure(self.solver, "ALL")
        self.parser = InputParser(self.solver)
        invoke(self.parser, self.solver, "(declare-const x Int)(declare-const text String)")
        var terms = self.parser.getSymbolManager().getDeclaredTerms()
        self.x = terms[0]
        self.text = terms[1]

    def step(self, index: Int) raises:
        var n = index % 127
        var value = String("é😀", chr(0), "\\u0041-", n)
        var input = String("(push 1)(assert (= x ", n, "))(assert (= text ", self.tm.mkString(value), "))")
        invoke(self.parser, self.solver, input)
        assert_true(self.solver.checkSat().isSat())
        assert_equal(String(self.solver.getValue(self.x).getIntegerValue()), String(n))
        assert_equal(self.solver.getValue(self.text).getStringValue(), value)
        invoke(self.parser, self.solver, "(assert false)")
        assert_true(self.solver.checkSat().isUnsat())
        invoke(self.parser, self.solver, "(pop 1)")
        if index % 32 == 0:
            var rejected = False
            try:
                invoke(self.parser, self.solver, "(assert (= x ))")
            except:
                rejected = True
            assert_true(rejected, "malformed input must be rejected")
            invoke(self.parser, self.solver, "(push 1)(assert true)(pop 1)")
        assert_equal(len(self.solver.getAssertions()), 0)


struct BoundedJobs(Workload):
    var tm: TermManager
    var shared_tm: Bool

    def __init__(out self, shared_tm: Bool = False) raises:
        self.tm = TermManager()
        self.shared_tm = shared_tm

    def step(self, index: Int) raises:
        # One request has several checks, then releases the entire owner graph.
        var job = Incremental(False, self.tm) if self.shared_tm else Incremental(False)
        for offset in range(8):
            job.step(index + offset)
        var algebra = Algebra()
        algebra.step(index)


def synthesize(tm: TermManager, index: Int) raises:
    var solver = Solver(tm)
    solver.setOption("sygus", "true")
    solver.setOption("incremental", "false")
    solver.setOption("tlimit-per", "1000")
    solver.setLogic("LIA")
    var integer = tm.getIntegerSort()
    var x = tm.mkVar(integer, "x")
    var start = tm.mkVar(integer, "Start")
    var k = tm.mkInteger(index % 7 + 1)
    var grammar = solver.mkGrammar([x], [start])
    grammar.addRules(start, [x, k, tm.mkTerm(Kind.ADD, x, k), tm.mkTerm(Kind.SUB, x, k)])
    var f = solver.synthFun("f", [x], integer, grammar)
    var v = solver.declareSygusVar("v", integer)
    var offset = tm.mkInteger(index % 7 + 1 + (1 if index % 4 == 0 else 0))
    solver.addSygusConstraint(tm.mkTerm(Kind.APPLY_UF, f, v).eqTerm(tm.mkTerm(Kind.ADD, v, offset)))
    var result = solver.checkSynth()
    if index % 4 == 0:
        assert_true(result.hasNoSolution())
    else:
        assert_true(result.hasSolution())
        # Check the synthesized function in an independent SMT solver.
        var solution = solver.getSynthSolution(f)
        var checker = Solver(tm)
        configure(checker, "QF_LIA")
        var input = tm.mkConst(integer, "input")
        checker.assertFormula(tm.mkTerm(Kind.APPLY_UF, solution, input).eqTerm(tm.mkTerm(Kind.ADD, input, k)).notTerm())
        assert_true(checker.checkSat().isUnsat(), "synthesized function violates its specification")


struct Synthesis(Workload):
    var tm: TermManager
    var bounded: Bool

    def __init__(out self, bounded: Bool) raises:
        self.tm = TermManager()
        self.bounded = bounded

    def step(self, index: Int) raises:
        var tm = TermManager() if self.bounded else self.tm
        synthesize(tm, index)


struct ResourceLimits(Workload):
    var tm: TermManager
    var solver: Solver
    var hard: Term

    def __init__(out self) raises:
        self.tm = TermManager()
        self.solver = Solver(self.tm)
        configure(self.solver, "QF_NIA")
        self.solver.setOption("rlimit-per", "10")
        var x = self.tm.mkConst(self.tm.getIntegerSort(), "x")
        self.hard = self.tm.mkTerm(Kind.MULT, x, x).eqTerm(self.tm.mkInteger(2))

    def step(self, index: Int) raises:
        _ = index
        self.solver.assertFormula(self.hard)
        var result = self.solver.checkSat()
        assert_true(result.isUnknown())
        assert_equal(result.getUnknownExplanation(), UnknownExplanation.RESOURCEOUT)
        self.solver.resetAssertions()
        self.solver.assertFormula(self.tm.mkFalse())
        assert_true(self.solver.checkSat().isUnsat(), "solver must recover after resource exhaustion")
        self.solver.resetAssertions()


struct Metrics(Movable):
    var started: Int
    var count: Int
    var total_ns: Int
    var max_ns: Int
    var bins: List[Int]

    def __init__(out self):
        self.started = Int(perf_counter_ns())
        self.count = 0
        self.total_ns = 0
        self.max_ns = 0
        self.bins = List[Int](length=64, fill=0)

    def observe(mut self, ns: Int):
        self.count += 1
        self.total_ns += ns
        self.max_ns = max(self.max_ns, ns)
        var bucket = 0
        var value = max(ns, 1)
        while value > 1:
            value >>= 1
            bucket += 1
        self.bins[bucket] += 1

    def sample(self, path: String) raises:
        var elapsed = Int(perf_counter_ns()) - self.started
        var rss = resident_kb()
        with open(path, "a") as output:
            output.write(String(elapsed, "\t", self.count, "\t", rss, "\t", self.total_ns, "\t", self.max_ns, "\t", self.bins, "\t", peak_resident_kb(), "\n"))


def initialize_samples(path: String) raises:
    with open(path, "w") as output:
        output.write("elapsed_ns\trequests\trss_kib\twork_ns\tmax_request_ns\thistogram\tpeak_rss_kib\n")


def soak[T: Workload](work: T, seconds: Int, warmup: Int, seed: Int, path: String) raises:
    var index = seed
    var start = Int(perf_counter_ns())
    while Int(perf_counter_ns()) - start < warmup * 1000000000:
        work.step(index)
        index += 1
    var metrics = Metrics()
    metrics.sample(path)
    var next_sample = metrics.started + 1000000000
    while Int(perf_counter_ns()) - metrics.started < seconds * 1000000000:
        var before = Int(perf_counter_ns())
        work.step(index)
        metrics.observe(Int(perf_counter_ns()) - before)
        index += 1
        if Int(perf_counter_ns()) >= next_sample:
            metrics.sample(path)
            next_sample = Int(perf_counter_ns()) + 1000000000
    metrics.sample(path)
    print("completed", metrics.count, "requests")


def main() raises:
    var args = argv()
    if len(args) != 6:
        raise Error("expected: mode seconds warmup seed samples.tsv")
    var mode = args[1]
    var seconds = Int(args[2])
    var warmup = Int(args[3])
    var seed = Int(args[4])
    var path = args[5]
    if seconds < 1 or warmup < 0 or seed < 0:
        raise Error("invalid soak duration, warmup, or seed")
    initialize_samples(path)
    if mode == "incremental":
        soak(Incremental(), seconds, warmup, seed, path)
    elif mode == "term-churn":
        soak(Incremental(False), seconds, warmup, seed, path)
    elif mode == "algebra":
        soak(Algebra(), seconds, warmup, seed, path)
    elif mode == "parser":
        soak(Parsing(), seconds, warmup, seed, path)
    elif mode == "bounded-jobs":
        soak(BoundedJobs(), seconds, warmup, seed, path)
    elif mode == "solver-batches":
        soak(BoundedJobs(True), seconds, warmup, seed, path)
    elif mode == "synthesis-bounded":
        soak(Synthesis(True), seconds, warmup, seed, path)
    elif mode == "synthesis-shared-tm":
        soak(Synthesis(False), seconds, warmup, seed, path)
    elif mode == "resource-limits":
        soak(ResourceLimits(), seconds, warmup, seed, path)
    else:
        raise Error("unknown workload: " + mode)
