"""Public null objects can be formatted without invoking invalid native handles."""

from std.testing import assert_equal, assert_true
from cvc5_mojo import Command, Datatype, DatatypeConstructor, DatatypeConstructorDecl, DatatypeDecl, DatatypeSelector, Grammar, Kind, Op, Proof, ProofRule, Result, Sort, SynthResult, Term, TermManager, UnknownExplanation


def keys_and_ordering() raises:
    var tm = TermManager()
    var term = tm.mkInteger(42)
    var copy = term
    var terms = Dict[Term, Int]()
    terms[Term()] = 1
    terms[term] = 2
    terms[copy] = 3
    assert_equal(len(terms), 2)
    assert_equal(terms[Term()], 1)
    assert_equal(terms[tm.mkInteger(42)], 3)
    assert_true(Term() != term)
    assert_equal(hash(Term()), hash(Term()))
    assert_equal(hash(term), hash(copy))
    var other = tm.mkInteger(43)
    assert_true((term < other) != (other < term))
    assert_true(term <= copy and term >= copy and not term < copy)

    var sorts = Dict[Sort, Int]()
    sorts[Sort()] = 1
    sorts[tm.getIntegerSort()] = 2
    sorts[tm.getIntegerSort()] = 3
    assert_equal(len(sorts), 2)
    assert_equal(sorts[Sort()], 1)
    assert_equal(sorts[tm.getIntegerSort()], 3)
    assert_true(Sort() != tm.getIntegerSort())
    assert_true(not Sort() != Sort())
    assert_true(tm.getIntegerSort() != Sort())
    assert_true(not tm.getIntegerSort() != tm.getIntegerSort())
    assert_true(tm.getIntegerSort() != tm.getBooleanSort())
    assert_equal(hash(Sort()), hash(Sort()))
    assert_true(tm.getIntegerSort() <= tm.getIntegerSort())

    var ops = Dict[Op, Int]()
    ops[Op()] = 1
    ops[tm.mkOp(Kind.BITVECTOR_EXTRACT, 7, 0)] = 2
    ops[tm.mkOp(Kind.BITVECTOR_EXTRACT, 7, 0)] = 3
    assert_equal(len(ops), 2)
    assert_equal(ops[Op()], 1)
    assert_equal(ops[tm.mkOp(Kind.BITVECTOR_EXTRACT, 7, 0)], 3)
    assert_true(Op() != tm.mkOp(Kind.BITVECTOR_EXTRACT, 7, 0))
    assert_equal(hash(Op()), hash(Op()))


def main() raises:
    # Oracle-derived strings are checked by the generator; these examples
    # additionally exercise all public null Writable types at run time.
    assert_equal(String(Term()), "null")
    assert_equal(String(Sort()), "null")
    assert_equal(String(Result()), "none")
    assert_equal(String(SynthResult()), "(NONE)")
    assert_equal(String(Op()), "NULL_TERM")
    assert_equal(String(Command()), "null")
    assert_equal(String(Grammar()), "")
    assert_equal(String(Datatype()), "Datatype(null)")
    assert_equal(String(DatatypeConstructor()), "DatatypeConstructor(null)")
    assert_equal(String(DatatypeConstructorDecl()), "DatatypeConstructorDecl(null)")
    assert_equal(String(DatatypeDecl()), "DatatypeDecl(null)")
    assert_equal(String(DatatypeSelector()), "DatatypeSelector(null)")
    assert_true(Term() == Term())
    assert_true(Result() == Result())
    var result = Result()
    var copy = result
    assert_true(copy.isNull())
    assert_true(not copy.isSat() and not copy.isUnsat() and not copy.isUnknown())
    assert_equal(copy.getUnknownExplanation(), UnknownExplanation.UNKNOWN_REASON)
    var synth = SynthResult()
    var synth_copy = synth
    assert_true(synth_copy.isNull())
    assert_true(not synth_copy.hasSolution() and not synth_copy.hasNoSolution() and not synth_copy.isUnknown())
    var proof = Proof()
    var proof_copy = proof
    assert_equal(proof_copy.getRule(), ProofRule.UNKNOWN)
    assert_true(proof_copy.getResult().isNull())
    assert_equal(len(proof_copy.getChildren()), 0)
    assert_equal(len(proof_copy.getArguments()), 0)
    var rejected = False
    try:
        _ = proof_copy.getRewriteRule()
    except e:
        rejected = "undefined on a null object" in String(e)
    assert_true(rejected)
    keys_and_ordering()
    print("null formatting test passed")
