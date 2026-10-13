"""Fixed-input ownership controls; pair with independent controls.c.

The driver either retains one graph or checks complete graph cleanup each
iteration. It does not change the public binding API.
"""
from std.os import abort
from std.sys import argv
from std.testing import assert_equal, assert_true
from std.time import perf_counter_ns
from cvc5_mojo import DatatypeDecl, Grammar, InputLanguage, InputParser, ProofComponent, Solver, Sort, Stat, SynthResult, Term, TermManager
from cvc5_mojo._c.ffi import CChars, c_bytes, is_null, null, to_string
from cvc5_mojo._c.raw import CApiPtr, Cvc5, Cvc5DatatypeDecl, Cvc5Grammar, Cvc5InputParser, Cvc5Sort, Cvc5Stat, Cvc5SymbolManager, Cvc5SynthResult, Cvc5Term, Cvc5TermManager, c_api
from memory_support import resident_kb, save_maps


trait Control(Movable, Deinitable):
    def __init__(out self, mode: String) raises:
        ...

    def step(self) raises -> Int:
        ...

    def alive(self) raises:
        ...


def declaration(tm: TermManager) raises -> DatatypeDecl:
    var decl = tm.mkDatatypeDecl("Box")
    var copied = decl
    var cons = tm.mkDatatypeConstructorDecl("box")
    var cons_copy = cons
    cons_copy.addSelector("value", tm.getBooleanSort())
    copied.addConstructor(cons_copy)
    assert_equal(decl.getName(), "Box")
    assert_equal(copied.getNumConstructors(), 1)
    return copied^


def stat_checksum(stat: Stat) raises -> Int:
    # Timers and other numeric values are nondeterministic; compare type,
    # flags, histogram keys and shape. The existing API tests check values.
    var value = stat.value.copy()
    var checksum = 16 * Int(stat.default) + 32 * Int(stat.internal)
    if value.isa[Int]():
        return checksum + 1
    if value.isa[Float64]():
        return checksum + 2
    if value.isa[String]():
        return checksum + 3
    ref histogram = value[Dict[String, UInt64]]
    checksum += 4 + 64 * len(histogram)
    for key in histogram.keys():
        assert_true(key.byte_length() > 0)
        checksum += key.byte_length()
    return checksum


def raw_declaration(api: CApiPtr, tm: Cvc5TermManager) raises -> Cvc5DatatypeDecl:
    var name = c_bytes("Box")
    var decl = api[].cvc5_mk_dt_decl(tm, name.unsafe_ptr(), False)
    var copied = api[].cvc5_dt_decl_copy(decl)
    var constructor_name = c_bytes("box")
    var cons = api[].cvc5_mk_dt_cons_decl(tm, constructor_name.unsafe_ptr())
    var cons_copy = api[].cvc5_dt_cons_decl_copy(cons)
    var field = c_bytes("value")
    var boolean = api[].cvc5_get_boolean_sort(tm)
    api[].cvc5_dt_cons_decl_add_selector(cons_copy, field.unsafe_ptr(), boolean)
    api[].cvc5_sort_release(boolean)
    api[].cvc5_dt_decl_add_constructor(copied, cons_copy)
    assert_equal(to_string(api[].cvc5_dt_decl_get_name(decl)), "Box")
    assert_equal(api[].cvc5_dt_decl_get_num_constructors(copied), 1)
    api[].cvc5_dt_cons_decl_release(cons_copy)
    api[].cvc5_dt_cons_decl_release(cons)
    api[].cvc5_dt_decl_release(decl)
    return copied


def raw_stat_checksum(api: CApiPtr, stat: Cvc5Stat) raises -> Int:
    var checksum = 16 * Int(api[].cvc5_stat_is_default(stat)) + 32 * Int(api[].cvc5_stat_is_internal(stat))
    if api[].cvc5_stat_is_int(stat):
        _ = api[].cvc5_stat_get_int(stat)
        return checksum + 1
    if api[].cvc5_stat_is_double(stat):
        _ = api[].cvc5_stat_get_double(stat)
        return checksum + 2
    if api[].cvc5_stat_is_string(stat):
        _ = to_string(api[].cvc5_stat_get_string(stat))
        return checksum + 3
    assert_true(api[].cvc5_stat_is_histogram(stat))
    var names = null[CChars]()
    var counts = null[UInt64]()
    var size = UInt(0)
    api[].cvc5_stat_get_histogram(stat, Pointer(to=names), Pointer(to=counts), Pointer(to=size))
    var histogram = Dict[String, UInt64]()
    for i in range(Int(size)):
        histogram[to_string(names[unsafe_offset=i])] = counts[unsafe_offset=i]
    checksum += 4 + 64 * len(histogram)
    for key in histogram.keys():
        assert_true(key.byte_length() > 0)
        checksum += key.byte_length()
    return checksum


struct PublicControl(Control):
    var mode: String
    var tm: TermManager
    var solver: Solver
    var start: Term
    var truth: Term
    var falsity: Term
    var reused: Optional[Grammar]
    var parser: Optional[InputParser]
    var datatype_sort: Optional[Sort]
    var synthesis: Optional[SynthResult]

    def __init__(out self, mode: String) raises:
        self.mode = mode
        self.tm = TermManager()
        self.solver = Solver(self.tm)
        self.start = self.tm.mkVar(self.tm.getBooleanSort(), "Γ")
        self.truth = self.tm.mkTrue()
        self.falsity = self.tm.mkFalse()
        self.reused = None
        self.parser = None
        self.datatype_sort = None
        self.synthesis = None
        if mode == "results":
            self.solver.setLogic("QF_UF")
        elif mode == "datatype-declarations":
            pass
        elif mode == "datatypes":
            self.datatype_sort = self.tm.mkDatatypeSort(declaration(self.tm))
        elif mode.startswith("statistics"):
            self.solver.setLogic("QF_UF")
            assert_true(self.solver.checkSat().isSat())
        elif mode.startswith("synthesis"):
            self.solver.setOption("sygus", "true")
            _ = self.solver.synthFun("f", [], self.tm.getBooleanSort())
            self.solver.addSygusConstraint(self.falsity)
            if mode == "synthesis-copy":
                self.synthesis = self.solver.checkSynth()
        elif mode == "commands":
            self.solver.setLogic("QF_UF")
            self.parser = InputParser(self.solver)
        elif mode == "proofs":
            self.solver.setOption("produce-proofs", "true")
            self.solver.assertFormula(self.falsity)
            assert_true(self.solver.checkSat().isUnsat())
        elif mode.startswith("grammar"):
            self.solver.setOption("sygus", "true")
            if mode == "grammar-reuse":
                var grammar = self.solver.mkGrammar([], [self.start])
                grammar.addRule(self.start, self.truth)
                self.reused = grammar^
        else:
            raise Error("unknown control")

    def step(self) raises -> Int:
        if self.mode == "datatype-declarations":
            _ = declaration(self.tm)
            return 1
        elif self.mode == "datatypes":
            var datatype = self.datatype_sort.value().getDatatype()
            var dt_copy = datatype
            assert_equal(datatype.getName(), "Box")
            var cons = dt_copy.getConstructor("box")
            var cons_copy = cons
            assert_equal(cons.getNumSelectors(), 1)
            var selector = cons_copy.getSelector("value")
            var sel_copy = selector
            assert_equal(selector.getName(), "value")
            assert_true(sel_copy.getCodomainSort().isBoolean())
            return 1
        elif self.mode.startswith("statistics"):
            var stats = self.tm.getStatistics() if self.mode == "statistics-iter" else self.solver.getStatistics()
            var copied = stats
            _ = stats^
            var checksum = 0
            if self.mode == "statistics-iter":
                var values = copied.get(True, True)
                assert_true(len(values) > 0)
                for entry in values.items():
                    checksum += entry.key.byte_length() + stat_checksum(entry.value)
            else:
                for name in ["DefaultModel::ee::constantTermsCount", "theory::arith::status::avgUnknownsInARow", "Normalize::pass_time", "resource::steps::resource"]:
                    checksum += stat_checksum(copied[name])
            return checksum
        elif self.mode.startswith("synthesis"):
            var result = self.synthesis.value() if self.synthesis else self.solver.checkSynth()
            var copied = result
            assert_true(result.hasNoSolution())
            assert_true(copied.hasNoSolution())
            return 2
        elif self.mode == "commands":
            ref parser = self.parser.value()
            parser.setStringInput(InputLanguage.SMT_LIB_2_6, "(assert true)", "ownership")
            var command = parser.nextCommand()
            var copied = command
            assert_equal(command.getCommandName(), "assert")
            assert_equal(copied.getCommandName(), "assert")
            return 2
        elif self.mode == "results":
            var result = self.solver.checkSat()
            var copied = result
            assert_true(result.isSat())
            assert_true(copied.isSat())
            return 2
        elif self.mode == "proofs":
            var roots = self.solver.getProof()
            assert_true(len(roots) > 0)
            var checksum = len(roots)
            for root in roots:
                var copied = root
                assert_true(copied == root)
                assert_true(copied.getResult().getSort().isBoolean())
                var children = copied.getChildren()
                assert_true(len(children) > 0)
                checksum += len(children)
                for child in children:
                    checksum += Int(child.getRule().value)
            return checksum
        else:
            var grammar = self.reused.value() if self.reused else self.solver.mkGrammar([], [self.start])
            if self.mode != "grammar-empty" and self.mode != "grammar-reuse":
                grammar.addRule(self.start, self.truth)
            var copied = grammar
            if self.mode == "grammar-empty" or self.mode == "grammar-rules":
                assert_true(not grammar.isNull() and not copied.isNull())
                return 1
            var original: String
            var shown: String
            if self.mode == "grammar-write":
                original = String()
                shown = String()
                grammar.write_to(original)
                copied.write_to(shown)
            else:
                original = String(grammar)
                shown = String(copied)
            assert_equal(shown, original)
            assert_true("Γ" in shown and "true" in shown)
            return shown.byte_length()

    def alive(self) raises:
        assert_true(self.solver.getVersion().byte_length() > 0)


struct RawControl(Control):
    var mode: String
    var api: CApiPtr
    var tm: Cvc5TermManager
    var solver: Cvc5
    var start: Cvc5Term
    var truth: Cvc5Term
    var falsity: Cvc5Term
    var reused: Optional[Cvc5Grammar]
    var parser: Optional[Cvc5InputParser]
    var datatype_sort: Optional[Cvc5Sort]
    var synthesis: Optional[Cvc5SynthResult]

    def __init__(out self, mode: String) raises:
        self.mode = mode
        self.api = c_api()
        self.tm = self.api[].cvc5_term_manager_new()
        self.solver = self.api[].cvc5_new(self.tm)
        var sort = self.api[].cvc5_get_boolean_sort(self.tm)
        var name = c_bytes("Γ")
        self.start = self.api[].cvc5_mk_var(self.tm, sort, name.unsafe_ptr())
        self.api[].cvc5_sort_release(sort)
        self.truth = self.api[].cvc5_mk_true(self.tm)
        self.falsity = self.api[].cvc5_mk_false(self.tm)
        self.reused = None
        self.parser = None
        self.datatype_sort = None
        self.synthesis = None
        if mode == "results":
            var logic = c_bytes("QF_UF")
            self.api[].cvc5_set_logic(self.solver, logic.unsafe_ptr())
        elif mode == "datatype-declarations":
            pass
        elif mode == "datatypes":
            var decl = raw_declaration(self.api, self.tm)
            self.datatype_sort = self.api[].cvc5_mk_dt_sort(self.tm, decl)
            self.api[].cvc5_dt_decl_release(decl)
        elif mode.startswith("statistics"):
            var logic = c_bytes("QF_UF")
            self.api[].cvc5_set_logic(self.solver, logic.unsafe_ptr())
            var result = self.api[].cvc5_check_sat(self.solver)
            assert_true(self.api[].cvc5_result_is_sat(result))
            self.api[].cvc5_result_release(result)
        elif mode.startswith("synthesis"):
            var option = c_bytes("sygus")
            var value = c_bytes("true")
            self.api[].cvc5_set_option(self.solver, option.unsafe_ptr(), value.unsafe_ptr())
            var name = c_bytes("f")
            var empty = List[Cvc5Term]()
            var boolean = self.api[].cvc5_get_boolean_sort(self.tm)
            var function = self.api[].cvc5_synth_fun(self.solver, name.unsafe_ptr(), 0, empty.unsafe_ptr(), boolean)
            self.api[].cvc5_sort_release(boolean)
            self.api[].cvc5_term_release(function)
            self.api[].cvc5_add_sygus_constraint(self.solver, self.falsity)
            if mode == "synthesis-copy":
                self.synthesis = self.api[].cvc5_check_synth(self.solver)
        elif mode == "commands":
            var logic = c_bytes("QF_UF")
            self.api[].cvc5_set_logic(self.solver, logic.unsafe_ptr())
            self.parser = self.api[].cvc5_parser_new(self.solver, Cvc5SymbolManager(null[NoneType]()))
        elif mode == "proofs":
            var option = c_bytes("produce-proofs")
            var value = c_bytes("true")
            self.api[].cvc5_set_option(self.solver, option.unsafe_ptr(), value.unsafe_ptr())
            self.api[].cvc5_assert_formula(self.solver, self.falsity)
            var result = self.api[].cvc5_check_sat(self.solver)
            assert_true(self.api[].cvc5_result_is_unsat(result))
            self.api[].cvc5_result_release(result)
        elif mode.startswith("grammar"):
            var option = c_bytes("sygus")
            var value = c_bytes("true")
            self.api[].cvc5_set_option(self.solver, option.unsafe_ptr(), value.unsafe_ptr())
            if mode == "grammar-reuse":
                var empty = List[Cvc5Term]()
                var starts = List[Cvc5Term]()
                starts.append(self.start)
                var grammar = self.api[].cvc5_mk_grammar(self.solver, 0, empty.unsafe_ptr(), 1, starts.unsafe_ptr())
                self.api[].cvc5_grammar_add_rule(grammar, self.start, self.truth)
                self.reused = grammar
        else:
            raise Error("unknown control")

    def __deinit__(deinit self):
        try:
            if self.synthesis:
                self.api[].cvc5_synth_result_release(self.synthesis.value())
            if self.datatype_sort:
                self.api[].cvc5_sort_release(self.datatype_sort.value())
            if self.parser:
                self.api[].cvc5_parser_delete(self.parser.value())
            if self.reused:
                self.api[].cvc5_grammar_release(self.reused.value())
            self.api[].cvc5_term_release(self.start)
            self.api[].cvc5_term_release(self.truth)
            self.api[].cvc5_term_release(self.falsity)
            self.api[].cvc5_delete(self.solver)
            self.api[].cvc5_term_manager_delete(self.tm)
        except e:
            abort(String(e))

    def step(self) raises -> Int:
        if self.mode == "datatype-declarations":
            self.api[].cvc5_dt_decl_release(raw_declaration(self.api, self.tm))
            return 1
        elif self.mode == "datatypes":
            var datatype = self.api[].cvc5_sort_get_datatype(self.datatype_sort.value())
            var dt_copy = self.api[].cvc5_dt_copy(datatype)
            assert_equal(to_string(self.api[].cvc5_dt_get_name(datatype)), "Box")
            var name = c_bytes("box")
            var cons = self.api[].cvc5_dt_get_constructor_by_name(dt_copy, name.unsafe_ptr())
            var cons_copy = self.api[].cvc5_dt_cons_copy(cons)
            assert_equal(self.api[].cvc5_dt_cons_get_num_selectors(cons), 1)
            var field = c_bytes("value")
            var selector = self.api[].cvc5_dt_cons_get_selector_by_name(cons_copy, field.unsafe_ptr())
            var sel_copy = self.api[].cvc5_dt_sel_copy(selector)
            assert_equal(to_string(self.api[].cvc5_dt_sel_get_name(selector)), "value")
            var sort = self.api[].cvc5_dt_sel_get_codomain_sort(sel_copy)
            assert_true(self.api[].cvc5_sort_is_boolean(sort))
            self.api[].cvc5_sort_release(sort)
            self.api[].cvc5_dt_sel_release(sel_copy)
            self.api[].cvc5_dt_sel_release(selector)
            self.api[].cvc5_dt_cons_release(cons_copy)
            self.api[].cvc5_dt_cons_release(cons)
            self.api[].cvc5_dt_release(dt_copy)
            self.api[].cvc5_dt_release(datatype)
            return 1
        elif self.mode.startswith("statistics"):
            var stats = self.api[].cvc5_term_manager_get_statistics(self.tm) if self.mode == "statistics-iter" else self.api[].cvc5_get_statistics(self.solver)
            var copied = self.api[].cvc5_stats_copy(stats)
            self.api[].cvc5_stats_release(stats)
            var checksum = 0
            if self.mode == "statistics-iter":
                self.api[].cvc5_stats_iter_init(copied, True, True)
                var count = 0
                while self.api[].cvc5_stats_iter_has_next(copied):
                    var name = null[Int8]()
                    var stat = self.api[].cvc5_stats_iter_next(copied, Pointer(to=name))
                    var key = to_string(name)
                    checksum += key.byte_length() + raw_stat_checksum(self.api, stat)
                    self.api[].cvc5_stat_release(stat)
                    count += 1
                assert_true(count > 0)
            else:
                for name in ["DefaultModel::ee::constantTermsCount", "theory::arith::status::avgUnknownsInARow", "Normalize::pass_time", "resource::steps::resource"]:
                    var key = c_bytes(name)
                    var stat = self.api[].cvc5_stats_get(copied, key.unsafe_ptr())
                    checksum += raw_stat_checksum(self.api, stat)
                    self.api[].cvc5_stat_release(stat)
            self.api[].cvc5_stats_release(copied)
            return checksum
        elif self.mode.startswith("synthesis"):
            var result = self.api[].cvc5_synth_result_copy(self.synthesis.value()) if self.synthesis else self.api[].cvc5_check_synth(self.solver)
            var copied = self.api[].cvc5_synth_result_copy(result)
            assert_true(self.api[].cvc5_synth_result_has_no_solution(result))
            assert_true(self.api[].cvc5_synth_result_has_no_solution(copied))
            self.api[].cvc5_synth_result_release(copied)
            self.api[].cvc5_synth_result_release(result)
            return 2
        elif self.mode == "commands":
            var parser = self.parser.value()
            var input = c_bytes("(assert true)")
            var name = c_bytes("ownership")
            self.api[].cvc5_parser_set_str_input(parser, InputLanguage.SMT_LIB_2_6, input.unsafe_ptr(), name.unsafe_ptr())
            var error = null[Int8]()
            var command = self.api[].cvc5_parser_next_command(parser, Pointer(to=error))
            assert_true(is_null(error))
            var copied = self.api[].cvc5_cmd_copy(command)
            assert_equal(to_string(self.api[].cvc5_cmd_get_name(command)), "assert")
            assert_equal(to_string(self.api[].cvc5_cmd_get_name(copied)), "assert")
            self.api[].cvc5_cmd_release(copied)
            self.api[].cvc5_cmd_release(command)
            return 2
        elif self.mode == "results":
            var result = self.api[].cvc5_check_sat(self.solver)
            var copied = self.api[].cvc5_result_copy(result)
            assert_true(self.api[].cvc5_result_is_sat(result))
            assert_true(self.api[].cvc5_result_is_sat(copied))
            self.api[].cvc5_result_release(copied)
            self.api[].cvc5_result_release(result)
            return 2
        elif self.mode == "proofs":
            var count = UInt(0)
            var roots = self.api[].cvc5_get_proof(self.solver, ProofComponent.FULL, Pointer(to=count))
            assert_true(count > 0)
            var checksum = Int(count)
            for i in range(Int(count)):
                var root = roots[unsafe_offset=i]
                var copied = self.api[].cvc5_proof_copy(root)
                assert_true(self.api[].cvc5_proof_is_equal(copied, root))
                var result = self.api[].cvc5_proof_get_result(copied)
                var sort = self.api[].cvc5_term_get_sort(result)
                assert_true(self.api[].cvc5_sort_is_boolean(sort))
                self.api[].cvc5_sort_release(sort)
                self.api[].cvc5_term_release(result)
                var child_count = UInt(0)
                var children = self.api[].cvc5_proof_get_children(copied, Pointer(to=child_count))
                assert_true(child_count > 0)
                checksum += Int(child_count)
                for j in range(Int(child_count)):
                    var child = children[unsafe_offset=j]
                    checksum += Int(self.api[].cvc5_proof_get_rule(child).value)
                    self.api[].cvc5_proof_release(child)
                self.api[].cvc5_proof_release(copied)
                self.api[].cvc5_proof_release(root)
            return checksum
        else:
            var empty = List[Cvc5Term]()
            var starts = List[Cvc5Term]()
            starts.append(self.start)
            var grammar = self.api[].cvc5_grammar_copy(self.reused.value()) if self.reused else self.api[].cvc5_mk_grammar(self.solver, 0, empty.unsafe_ptr(), 1, starts.unsafe_ptr())
            if self.mode != "grammar-empty" and self.mode != "grammar-reuse":
                self.api[].cvc5_grammar_add_rule(grammar, self.start, self.truth)
            var copied = self.api[].cvc5_grammar_copy(grammar)
            if self.mode == "grammar-empty" or self.mode == "grammar-rules":
                assert_true(not is_null(grammar.ptr) and not is_null(copied.ptr))
                self.api[].cvc5_grammar_release(copied)
                self.api[].cvc5_grammar_release(grammar)
                return 1
            var original = to_string(self.api[].cvc5_grammar_to_string(grammar))
            var shown = to_string(self.api[].cvc5_grammar_to_string(copied))
            assert_equal(shown, original)
            assert_true("Γ" in shown and "true" in shown)
            self.api[].cvc5_grammar_release(copied)
            self.api[].cvc5_grammar_release(grammar)
            return shown.byte_length()

    def alive(self) raises:
        assert_true(to_string(self.api[].cvc5_get_version(self.solver)).byte_length() > 0)


def sample(path: String, phase: Int, operations: Int, elapsed: Int, checksum: Int) raises:
    var rss = resident_kb()
    with open(path, "a") as file:
        file.write(String(phase, "\t", operations, "\t", elapsed, "\t", rss, "\t", checksum, "\n"))


struct RoundControl[T: Control](Control):
    """Test final graph cleanup, independently of application lifecycle policy."""
    var mode: String

    def __init__(out self, mode: String):
        self.mode = mode

    def step(self) raises -> Int:
        var work = Self.T(self.mode)
        return work.step()

    def alive(self):
        pass


def measure[T: Control](work: T, operations: Int, warmup: Int, path: String) raises:
    for _ in range(warmup):
        _ = work.step()
    # Capture actual mapped paths after loading, independently of the env hint.
    save_maps(path + ".maps")
    var started = Int(perf_counter_ns())
    var checksum = 0
    sample(path, 0, 0, 0, 0)
    var interval = max(1, operations // 20)
    for i in range(operations):
        checksum += work.step()
        if (i + 1) % interval == 0 or i + 1 == operations:
            sample(path, 1, i + 1, Int(perf_counter_ns()) - started, checksum)
    work.alive()  # retain the owner through the last measured checkpoint


def main() raises:
    var args = argv()
    if len(args) != 7:
        raise Error("expected: public|raw mode operations warmup samples.tsv live|round")
    var operations = Int(args[3])
    var warmup = Int(args[4])
    var path = args[5]
    if operations < 1 or warmup < 0:
        raise Error("invalid operation count")
    if args[6] != "live" and args[6] != "round":
        raise Error("invalid lifetime")
    _ = c_api()  # capture the loaded libraries even with zero warmup rounds
    with open(path, "w") as file:
        file.write("phase\toperations\telapsed_ns\trss_kib\tchecksum\n")
    if args[1] == "public":
        if args[6] == "round":
            measure(RoundControl[PublicControl](args[2]), operations, warmup, path)
        else:
            measure(PublicControl(args[2]), operations, warmup, path)
    elif args[1] == "raw":
        if args[6] == "round":
            measure(RoundControl[RawControl](args[2]), operations, warmup, path)
        else:
            measure(RawControl(args[2]), operations, warmup, path)
    else:
        raise Error("unknown layer")
    sample(path, 2, operations, 0, 0)  # graph released; RSS need not fall
    print("completed", operations, "operations")
