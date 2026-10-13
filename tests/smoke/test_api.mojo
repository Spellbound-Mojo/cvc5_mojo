"""Generated base API test: each marshaling rule and each class, with values checked.

The smoke and lifetime tests cover the core every program uses; this test
calls at least one generated method per rule of bindgen/gen_api.py and per
mirrored class.
"""

from std.testing import assert_equal, assert_false, assert_true

from apn_mojo import Integer, Rational
from cvc5_mojo import (
    InputLanguage,
    InputParser,
    Kind,
    OptionCategory,
    ProofComponent,
    ProofFormat,
    Result,
    SkolemId,
    Solver,
    Op,
    Proof,
    Sort,
    Stat,
    SynthResult,
    SymbolManager,
    Term,
    TermManager,
)


def borrowed_term_manager() raises -> TermManager:
    """A term manager returned by a solver, whose original values are gone."""
    var tm = TermManager()
    var solver = Solver(tm)
    return solver.getTermManager()


def orphan_proposition() raises -> Term:
    """A Boolean term whose TermManager value is gone; cvc5 keeps the manager."""
    var tm = TermManager()
    return tm.mkConst(tm.getBooleanSort(), "orphan")


def statistics() raises:
    """Statistics, with the values the official Python bindings give for this problem."""
    var tm = TermManager()
    var solver = Solver(tm)
    solver.setLogic("QF_LIA")
    var x = tm.mkConst(tm.getIntegerSort(), "x")
    solver.assertFormula(tm.mkTerm(Kind.GT, x, tm.mkInteger(0)))
    _ = solver.checkSat()
    var stats = solver.getStatistics()

    # get(): by default neither internal nor unchanged statistics.
    var visible = stats.get()
    assert_equal(len(visible), 1)
    assert_false(visible["global::totalTime"].default)
    assert_false(visible["global::totalTime"].internal)
    assert_true(visible["global::totalTime"].value[String].endswith("ms"))
    # 49 on Linux, of which 18 are timers. A timer counts as changed only
    # after it measures a nonzero duration, which a fast clock sometimes
    # misses (macOS on Apple Silicon), so compare the other 31.
    var untimed = 0
    for entry in stats.get(True, False).items():
        if not (entry.value.value.isa[String]() and entry.value.value[String].endswith("ms")):
            untimed += 1
    assert_equal(untimed, 31)
    assert_equal(len(stats.get(False, True)), 47)
    assert_equal(len(stats.get(True, True)), 505)

    # Iteration: every statistic, as (name, Stat) pairs.
    var listed = 0
    var found = False
    for name, stat in stats:
        listed += 1
        if name == "LearnedRewrite::lrewCount":
            found = stat.default and stat.internal and len(stat.value[Dict[String, UInt64]]) == 0
    assert_equal(listed, 505)
    assert_true(found)

    # Indexing, and each kind of value: integer, float, string, histogram.
    var count = stats["DefaultModel::ee::constantTermsCount"]
    assert_true(count.default and count.internal)
    assert_equal(count.value[Int], 0)
    var average = stats["theory::arith::status::avgUnknownsInARow"]
    assert_true(not average.default and average.internal)
    assert_equal(average.value[Float64], 0.0)
    assert_equal(stats["Normalize::pass_time"].value[String], "0ms")
    var steps = stats["resource::steps::resource"].value[Dict[String, UInt64]].copy()
    assert_equal(len(steps), 7)
    assert_equal(steps["CnfStep"], 2)
    assert_equal(steps["DecisionStep"], 1)
    assert_equal(steps["PreprocessStep"], 7)
    assert_equal(steps["RewriteStep"], 40)
    assert_equal(steps["SatConflictStep"], 3)
    assert_equal(steps["TheoryCheckStep"], 2)
    assert_equal(steps["TheoryFullCheckStep"], 1)
    var message = String()
    try:
        _ = stats["no such statistic"]
    except e:
        message = String(e)
    assert_equal(message, 'cvc5: no statistic with name "no such statistic" exists.')

    # Printing: as Python prints the statistic's dict.
    assert_equal(String(count), "{'default': True, 'internal': True, 'value': 0}")
    assert_equal(String(average), "{'default': False, 'internal': True, 'value': 0.0}")
    assert_equal(String(stats["Normalize::pass_time"]), "{'default': True, 'internal': True, 'value': '0ms'}")
    assert_equal(
        String(stats["resource::steps::resource"]),
        "{'default': False, 'internal': True, 'value': {'CnfStep': 2, 'DecisionStep': 1, 'PreprocessStep': 7, "
        "'RewriteStep': 40, 'SatConflictStep': 3, 'TheoryCheckStep': 2, 'TheoryFullCheckStep': 1}}",
    )
    # Strings are quoted and escaped as Python's repr does.
    var names = Dict[String, UInt64]()
    names["it's"] = 1
    names["tab\t\u00a0"] = 2
    assert_equal(
        String(Stat(False, False, Stat.Value(names^))),
        "{'default': False, 'internal': False, 'value': {\"it's\": 1, 'tab\\t\\xa0': 2}}",
    )


def even(n: Int) raises -> Result:
    """Whether `n` is even, by mutually recursive functions (defineFunsRec).

    The official Python bindings give `unknown (INCOMPLETE)` for 4 and
    `unsat` for 3.
    """
    var tm = TermManager()
    var integer = tm.getIntegerSort()
    var domain = List[Sort]()
    domain.append(integer)
    var predicate = tm.mkFunctionSort(domain, tm.getBooleanSort())
    var even_ = tm.mkConst(predicate, "even")
    var odd = tm.mkConst(predicate, "odd")
    var a = tm.mkVar(integer, "a")
    var b = tm.mkVar(integer, "b")
    var zero = tm.mkInteger(0)
    var one = tm.mkInteger(1)
    var funs = List[Term]()
    funs.append(even_)
    funs.append(odd)
    var bound_vars = List[List[Term]]()
    bound_vars.append([a])
    bound_vars.append([b])
    var bodies = List[Term]()
    bodies.append(tm.mkTerm(Kind.ITE, tm.mkTerm(Kind.EQUAL, a, zero), tm.mkTrue(),
                            tm.mkTerm(Kind.APPLY_UF, odd, tm.mkTerm(Kind.SUB, a, one))))
    bodies.append(tm.mkTerm(Kind.ITE, tm.mkTerm(Kind.EQUAL, b, zero), tm.mkFalse(),
                            tm.mkTerm(Kind.APPLY_UF, even_, tm.mkTerm(Kind.SUB, b, one))))
    var solver = Solver(tm)
    solver.setLogic("UFLIA")
    # The C API cannot see the inner lists' count, so the bindings check it.
    var message = String()
    try:
        solver.defineFunsRec(funs, List[List[Term]](), bodies)
    except e:
        message = String(e)
    assert_equal(message, "cvc5_mojo: `bound_vars` and `funs` must have the same length")
    solver.defineFunsRec(funs, bound_vars, bodies)
    solver.assertFormula(tm.mkTerm(Kind.APPLY_UF, even_, tm.mkInteger(n)))
    return solver.checkSat()


def options() raises:
    """Option information and enums, printed as the official Python bindings print them."""
    assert_equal(String(Kind.ADD), "Kind.ADD")
    assert_equal(repr(OptionCategory.EXPERT), "<OptionCategory.EXPERT: 1>")
    var arity = Dict[Kind, Int]()  # enums hash, as Python's do
    arity[Kind.NOT] = 1
    assert_equal(arity[Kind.NOT], 1)
    assert_equal(String(Kind(9999)), "Kind(9999)")
    var tm = TermManager()
    var solver = Solver(tm)
    solver.setOption("verbosity", "2")
    var verbosity = solver.getOptionInfo("verbosity")
    assert_true(verbosity.setByUser and verbosity.category == OptionCategory.COMMON)
    assert_equal(verbosity.current.value()[Int], 2)
    assert_false(verbosity.minimum)
    assert_equal(
        String(verbosity),
        "{'name': 'verbosity', 'aliases': [], 'setByUser': True, 'category': <OptionCategory.COMMON: 2>, "
        "'type': <class 'int'>, 'current': 2, 'default': 0, 'minimum': None, 'maximum': None}",
    )
    # A uint64 option whose maximum does not fit in Int.
    var size = solver.getOptionInfo("bv-abstraction-size")
    assert_equal(size.maximum.value()[UInt64], UInt64.MAX)
    assert_equal(
        String(solver.getOptionInfo("deep-restart-factor")),
        "{'name': 'deep-restart-factor', 'aliases': [], 'setByUser': False, 'category': <OptionCategory.EXPERT: 1>, "
        "'type': <class 'float'>, 'current': 3.0, 'default': 3.0, 'minimum': 0.0, 'maximum': 1000.0}",
    )
    var mode = solver.getOptionInfo("arith-prop")
    assert_equal(mode.type.value(), "mode")
    assert_equal(mode.modes, ["bi", "both", "none", "unate"])
    assert_equal(
        String(mode),
        "{'name': 'arith-prop', 'aliases': [], 'setByUser': False, 'category': <OptionCategory.EXPERT: 1>, "
        "'type': 'mode', 'current': 'both', 'default': 'both', 'modes': ['bi', 'both', 'none', 'unate']}",
    )
    assert_equal(
        String(solver.getOptionInfo("err")),
        "{'name': 'err', 'aliases': ['diagnostic-output-channel'], 'setByUser': False, "
        "'category': <OptionCategory.EXPERT: 1>, 'type': None}",
    )
    var message = String()
    try:
        _ = solver.getOptionInfo("no-such-option")
    except e:
        message = String(e)
    assert_equal(message, "cvc5: Error in option parsing: Unrecognized option key or setting: no-such-option")


def numbers() raises:
    """Python's big integers and fractions as apn_mojo's `Integer` and `Rational`,
    with the results the official Python bindings give."""
    var tm = TermManager()
    # Values beyond 64 bits from cvc5's own Python tests.
    assert_true(tm.mkInteger("-18446744073709551616").getIntegerValue() == -18446744073709551616)
    assert_true(tm.mkInteger("18446744073709551616").getIntegerValue() == Integer(2) ** 64)
    # Literals stay exact, where Mojo would truncate them to an Int (Python
    # raises OverflowError for mkInteger(2**70)); an Int takes the int64 path.
    assert_true(tm.mkInteger(2**70).getIntegerValue() == 2**70)
    var small = -5
    assert_true(tm.mkInteger(small).getIntegerValue() == -5)
    # Fractions print as Python's do.
    assert_true(tm.mkReal("12.7").getRealValue() == Rational(127, 10))
    assert_equal(String(tm.mkReal("12.7").getRealValue()), "127/10")
    assert_equal(String(tm.mkReal("-17").getRealValue()), "-17")
    var big = tm.mkReal(2**70, 3)
    assert_equal(String(big), "(/ 1180591620717411303424 3)")
    assert_equal(String(big.getRealValue()), "1180591620717411303424/3")
    assert_equal(String(tm.mkReal(Rational(1, 2))), "(/ 1 2)")
    assert_equal(String(tm.mkReal(5)), "5.0")
    assert_equal(String(tm.mkReal(2**70)), "1180591620717411303424.0")
    # Python's mkReal formats a numerator and a denominator alike.
    assert_equal(String(tm.mkReal("1", "2")), "(/ 1 2)")
    assert_equal(String(tm.mkReal(-1, "2")), "(/ (- 1) 2)")
    assert_equal(String(tm.mkReal("-1", 2)), "(/ (- 1) 2)")
    # A float is its shortest text, as Python's `str(0.3)`: exactly 3/10.
    assert_equal(String(tm.mkReal(0.3)), "(/ 3 10)")
    var tenth = -0.1
    assert_equal(String(tm.mkReal(tenth)), "(/ (- 1) 10)")
    # Finite fields are often larger than 64 bits.
    var field = tm.mkFiniteFieldSort(2**127 - 1)
    assert_equal(String(field), "(_ FiniteField 170141183460469231731687303715884105727)")
    assert_true(field.getFiniteFieldSize() == 2**127 - 1)
    var element = tm.mkFiniteFieldElem(-1, field)
    assert_equal(String(element), "#f170141183460469231731687303715884105726m170141183460469231731687303715884105727")
    assert_true(element.getFiniteFieldValue() == -1)
    # Bit-vectors of any width from an integer, and Python's zero form.
    assert_equal(String(tm.mkBitVector(70, 2**69)), "#b1" + String("0") * 69)
    assert_equal(String(tm.mkBitVector(8)), "#b00000000")
    assert_equal(String(tm.mkBitVector(8, 5)), "#b00000101")


def null_objects() raises:
    """Python's `Sort()` and its siblings are null objects, as in the official bindings."""
    assert_true(Result().isNull() and SynthResult().isNull() and Sort().isNull())
    assert_true(Term().isNull() and Op().isNull())
    assert_true(Term() == Term())
    assert_equal(hash(Sort()), hash(Sort()))  # equal, so they hash alike
    var tm = TermManager()
    assert_false(Sort() == tm.getIntegerSort())
    # Methods raise on a null object, as Python's do (Python crashes on the last one).
    var raised = 0
    try:
        _ = tm.mkArraySort(Sort(), tm.getIntegerSort())
    except:
        raised += 1
    try:
        _ = tm.mkTerm(Kind.NOT, Term())
    except:
        raised += 1
    try:
        _ = Solver(tm).proofToString(Proof())
    except:
        raised += 1
    assert_equal(raised, 3)


def main() raises:
    var tm = TermManager()
    var integer = tm.getIntegerSort()

    # Optional[String] = None: NULL when not given.
    assert_false(tm.mkConst(integer).hasSymbol())
    assert_equal(tm.mkConst(integer, "z").getSymbol(), "z")
    # A parameter cvc5's implementation tests for NULL, which its header does not say.
    assert_equal(String(tm.mkUninterpretedSortConstructorSort(2)), "||")

    # Python's other argument forms: one domain sort, and record fields as pairs.
    assert_equal(String(tm.mkFunctionSort(integer, tm.getBooleanSort())), "(-> Int Bool)")
    var record = tm.mkRecordSort(("a", integer), ("b", tm.getBooleanSort()))
    assert_equal(String(record), "__cvc5_record_a_Int_b_Bool")

    # Variadic and List overloads.
    var p = tm.mkConst(tm.getBooleanSort(), "p")
    var q = tm.mkConst(tm.getBooleanSort(), "q")
    var conjuncts = List[Term]()
    conjuncts.append(p)  # copies are implicit, as Python shares objects
    conjuncts.append(q)
    assert_true(tm.mkTerm(Kind.AND, p, q) == tm.mkTerm(Kind.AND, conjuncts))
    assert_equal(tm.mkTupleSort(integer, integer).getTupleLength(), 2)

    # Term methods that build terms, with the results and the error the
    # official Python bindings give (cvc5 1.4.1, pixi environment `oracle`).
    var x = tm.mkConst(integer, "x")
    var y = tm.mkConst(integer, "y")
    assert_equal(String(p.notTerm()), "(not p)")
    assert_equal(String(p.andTerm(q)), "(and p q)")
    assert_equal(String(p.orTerm(q)), "(or p q)")
    assert_equal(String(p.xorTerm(q)), "(xor p q)")
    assert_equal(String(x.eqTerm(y)), "(= x y)")
    assert_equal(String(p.impTerm(q)), "(=> p q)")
    assert_equal(String(p.iteTerm(x, y)), "(ite p x y)")
    var message = String()
    try:
        _ = x.notTerm()
    except e:
        message = String(e)
    assert_equal(message, "cvc5: expecting a Boolean subexpression")
    # The term manager a term remembers outlives every TermManager value.
    assert_equal(String(orphan_proposition().notTerm()), "(not orphan)")

    # Int parameters are range-checked into the C type.
    assert_equal(tm.mkBitVectorSort(8).getBitVectorSize(), 8)
    var raised = False
    try:
        _ = tm.mkBitVectorSort(-1)
    except e:
        raised = String(e) == "cvc5_mojo: -1 is out of range for uint32_t"
    assert_true(raised)

    # Indexing, comparison, hashing; two lists of one length.
    var total = tm.mkTerm(Kind.ADD, x, y)
    assert_equal(total.getNumChildren(), 2)
    assert_true(total[0] == x)
    assert_true(x < y or y < x)
    assert_equal(hash(x), hash(x.copy()))
    var olds = List[Term]()
    olds.append(x.copy())  # explicit copies still work
    var news = List[Term]()
    news.append(y)
    assert_equal(String(total.substitute(olds, news)), "(+ y y)")

    # Tuples: several results through out-parameters.
    var u = tm.mkUninterpretedSort("U")
    var constraint = tm.mkCardinalityConstraint(u, 3).getCardinalityConstraint()
    assert_true(constraint[0] == u)
    assert_equal(constraint[1], 3)
    var half = tm.mkFloatingPoint(5, 11, tm.mkBitVector(16, UInt64(0x3C00))).getFloatingPointValue()
    assert_equal(half[0], 5)
    assert_equal(half[1], 11)

    # A 32-bit string result, decoded.
    assert_equal(tm.mkString("caf\\u{e9}", True).getStringValue(), "café")

    # Operators with integer indices.
    var extract = tm.mkOp(Kind.BITVECTOR_EXTRACT, 7, 4)
    assert_equal(extract.getNumIndices(), 2)
    assert_true(extract[0].getIntegerValue() == 7)
    var nibble = tm.mkTerm(extract, tm.mkBitVector(8, UInt64(0xA5)))
    assert_equal(String(nibble), "((_ extract 7 4) #b10100101)")

    # Datatypes: declarations, the sort, indexing by position and by name.
    var decl = tm.mkDatatypeDecl("list")
    var cons = tm.mkDatatypeConstructorDecl("cons")
    cons.addSelector("head", integer)
    cons.addSelectorSelf("tail")
    decl.addConstructor(cons)
    decl.addConstructor(tm.mkDatatypeConstructorDecl("nil"))
    var datatype = tm.mkDatatypeSort(decl).getDatatype()
    assert_equal(datatype.getName(), "list")
    assert_equal(datatype[0].getName(), "cons")
    assert_equal(datatype["nil"].getName(), "nil")
    assert_equal(datatype[0]["head"].getName(), "head")
    assert_equal(datatype.getSelector("tail").getName(), "tail")

    # Iteration, in the order the official Python bindings give.
    var members = List[String]()
    for constructor in datatype:
        members.append(constructor.getName())
        for selector in constructor:
            members.append(selector.getName())
    assert_equal(members, ["cons", "head", "tail", "nil"])
    var domain = List[Sort]()
    domain.append(integer)
    var g = tm.mkConst(tm.mkFunctionSort(domain, integer), "g")
    var children = List[String]()
    for child in tm.mkTerm(Kind.APPLY_UF, g, x):
        children.append(String(child))
    assert_equal(children, ["g", "x"])
    var leaves = 0
    for _ in x:
        leaves += 1
    assert_equal(leaves, 0)

    # A solver: lists out, statistics, and an alias of a TermManager method.
    var solver = Solver(tm)
    solver.setLogic("QF_LIA")
    solver.assertFormula(tm.mkTerm(Kind.GT, x, tm.mkInteger(0)))
    assert_equal(len(solver.getAssertions()), 1)
    _ = solver.getStatistics()
    assert_equal(solver.getNumIndicesForSkolemId(SkolemId.PURIFY), tm.getNumIndicesForSkolemId(SkolemId.PURIFY))

    # A borrowed term manager keeps the solver that returned it alive.
    assert_equal(String(borrowed_term_manager().mkInteger(7)), "7")

    # Proofs: a list of solver-exported handles, each retaining its solver.
    var prover = Solver(tm)
    prover.setOption("produce-proofs", "true")
    prover.setLogic("QF_LIA")
    var impossible = tm.mkTerm(Kind.GT, x, x)
    prover.assertFormula(impossible)
    assert_true(prover.checkSat().isUnsat())
    var proofs = prover.getProof(ProofComponent.FULL)
    assert_true(len(proofs) >= 1)
    # The full proof closes its assumptions: it concludes the negated assertion.
    assert_true(proofs[0].getResult() == tm.mkTerm(Kind.NOT, impossible))

    # Dictionaries: a C++ map is a Dict, taken or returned. Names reach the
    # Alethe proof as in the official Python bindings.
    var names = Dict[Term, String]()
    names[impossible] = "contradiction"
    var alethe = prover.proofToString(proofs[0], ProofFormat.ALETHE, names)
    assert_true(alethe.startswith("(\n(assume contradiction (! (> x x) :named @p_1))\n"))
    assert_true("(assume @p1 (> x x))" in prover.proofToString(proofs[0]))
    var estimator = Solver(tm)
    estimator.setOption("produce-difficulty", "true")
    estimator.setLogic("QF_LIA")
    var positive = tm.mkTerm(Kind.GT, x, tm.mkInteger(0))
    var negative = tm.mkTerm(Kind.LT, x, tm.mkInteger(0))
    estimator.assertFormula(positive)
    estimator.assertFormula(negative)
    assert_true(estimator.checkSat().isUnsat())
    # Python's getDifficulty raises TypeError on a non-empty map in cvc5 1.4.1,
    # so these values come from the C API alone.
    var difficulty = estimator.getDifficulty()
    assert_equal(len(difficulty), 2)
    assert_equal(String(difficulty[positive]), "1")
    assert_equal(String(difficulty[negative]), "1")
    statistics()
    options()
    numbers()
    null_objects()
    assert_equal(String(even(4)), "unknown (INCOMPLETE)")
    assert_equal(String(even(3)), "unsat")

    # Synthesis.
    var synth = Solver(tm)
    synth.setOption("sygus", "true")
    synth.setLogic("LIA")
    var input = synth.declareSygusVar("input", integer)
    var bound = List[Term]()
    bound.append(tm.mkVar(integer, "v"))
    var f = synth.synthFun("f", bound, integer)
    var applied = tm.mkTerm(Kind.APPLY_UF, f, input)
    synth.addSygusConstraint(tm.mkTerm(Kind.EQUAL, applied, tm.mkTerm(Kind.ADD, input, tm.mkInteger(1))))
    assert_true(synth.checkSynth().hasSolution())
    assert_true(synth.getSynthSolution(f).getKind() == Kind.LAMBDA)

    # The parser: commands until a null one, and errors from `error_msg`.
    var reader = Solver(tm)
    var sm = SymbolManager(tm)
    var parser = InputParser(reader, sm)
    parser.setStringInput(
        InputLanguage.SMT_LIB_2_6, "(set-logic QF_LIA)(declare-const w Int)(assert (! (> w 0) :named positive))(check-sat)", "input"
    )
    var outputs = String()
    while True:
        var command = parser.nextCommand()
        if command.isNull():
            break
        outputs += command.invoke(reader, sm)
    assert_equal(outputs, "sat\n")
    var named = sm.getNamedTerms()
    assert_equal(len(named), 1)
    for entry in named.items():
        assert_equal(String(entry.key), "(> w 0)")
        assert_equal(entry.value, "positive")
    assert_true(parser.getSolver().getTermManager().mkTrue() == tm.mkTrue())
    var broken = InputParser(Solver(tm))  # a symbol manager of its own
    broken.setStringInput(InputLanguage.SMT_LIB_2_6, "(assert (> w", "broken")
    raised = False
    try:
        _ = broken.nextCommand()
    except e:
        raised = String(e).startswith("cvc5: ")
    assert_true(raised)
    print("api test passed")
