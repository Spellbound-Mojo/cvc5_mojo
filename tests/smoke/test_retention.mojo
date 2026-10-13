"""Discarded handles must not accumulate in a solver that remains alive."""

from std.testing import assert_equal, assert_true
from cvc5_mojo import Grammar, Kind, Proof, Result, Solver, SynthResult, TermManager
from memory_support import resident_kb

comptime BUDGET_KB = 4096


def check_growth(label: String, before: Int) raises:
    var growth = resident_kb() - before
    print(label, "growth:", growth, "kB")
    assert_true(growth <= BUDGET_KB, label + " accumulates discarded handles")


def query_results(tm: TermManager) raises:
    var solver = Solver(tm)
    solver.setLogic("QF_UF")
    for _ in range(2000):
        assert_true(solver.checkSat().isSat())
    var before = resident_kb()
    for _ in range(200000):
        assert_true(solver.checkSat().isSat())
    check_growth("results", before)
    assert_true(solver.checkSat().isSat())  # keep the solver alive through measurement


def proofs(tm: TermManager) raises:
    var solver = Solver(tm)
    solver.setOption("produce-proofs", "true")
    solver.assertFormula(tm.mkFalse())
    assert_true(solver.checkSat().isUnsat())
    for _ in range(2000):
        _ = solver.getProof()[0].getChildren()
    var before = resident_kb()
    for _ in range(30000):
        _ = solver.getProof()[0].getChildren()
    check_growth("proofs", before)
    assert_true(solver.checkSat().isUnsat())


def grammars(tm: TermManager) raises:
    var solver = Solver(tm)
    solver.setOption("sygus", "true")
    var start = tm.mkVar(tm.getBooleanSort(), "Start")
    for _ in range(2000):
        _ = solver.mkGrammar([], [start])
    var before = resident_kb()
    for _ in range(30000):
        _ = solver.mkGrammar([], [start])
    check_growth("grammars", before)
    assert_true(solver.mkGrammar([], [start]).isNull() == False)


def synthesis_round() raises:
    var tm = TermManager()
    var solver = Solver(tm)
    solver.setOption("sygus", "true")
    _ = solver.synthFun("f", [], tm.getBooleanSort())
    solver.addSygusConstraint(tm.mkFalse())
    for _ in range(4):
        assert_true(solver.checkSynth().hasNoSolution())


def synthesis_results() raises:
    # cvc5's synthesis engine itself grows across repeated queries in both
    # Python and Mojo with a shared term manager. Bound both lifetimes here; the other
    # cases above specifically measure live-owner handle retention.
    for _ in range(20):
        synthesis_round()
    var before = resident_kb()
    for _ in range(200):
        synthesis_round()
    check_growth("synthesis solver and term-manager lifetimes", before)


def detached_proof() raises -> Proof:
    var tm = TermManager()
    var solver = Solver(tm)
    solver.setOption("produce-proofs", "true")
    solver.assertFormula(tm.mkFalse())
    assert_true(solver.checkSat().isUnsat())
    return solver.getProof()[0]


def detached_grammar() raises -> Grammar:
    var tm = TermManager()
    var solver = Solver(tm)
    solver.setOption("sygus", "true")
    var start = tm.mkVar(tm.getBooleanSort(), "Start")
    var grammar = solver.mkGrammar([], [start])
    grammar.addRule(start, tm.mkTrue())
    return grammar


def detached_synthesis() raises -> SynthResult:
    var tm = TermManager()
    var solver = Solver(tm)
    solver.setOption("sygus", "true")
    _ = solver.synthFun("f", [], tm.getBooleanSort())
    solver.addSygusConstraint(tm.mkFalse())
    return solver.checkSynth()


def main() raises:
    var tm = TermManager()
    query_results(tm)
    proofs(tm)
    grammars(tm)
    synthesis_results()
    var proof = detached_proof()
    var copy = proof
    assert_equal(copy.getResult(), proof.getResult())
    var child = proof.getChildren()[0]
    _ = child.getRule()
    var grammar = detached_grammar()
    var grammar_copy = grammar
    _ = grammar^
    assert_true(String(grammar_copy).byte_length() > 0)
    var synthesis = detached_synthesis()
    var synthesis_copy = synthesis
    _ = synthesis^
    assert_true(synthesis_copy.hasNoSolution())
    print("retention test passed")
