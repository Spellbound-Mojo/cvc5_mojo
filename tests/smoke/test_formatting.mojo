"""Single-pass formatting keeps value, null, lifetime, and error contracts."""
from std.ffi import OwnedDLHandle, _DLCallable
from std.sys import argv
from std.testing import assert_equal, assert_true
from cvc5_mojo import Command, Datatype, DatatypeConstructor, DatatypeConstructorDecl, DatatypeDecl, DatatypeSelector, Grammar, InputLanguage, InputParser, Kind, Op, Result, Solver, Sort, SynthResult, Term, TermManager
from cvc5_mojo._c.ffi import CChars, trace
from cvc5_mojo._c.raw import c_api


def begin[label: StaticString]():
    trace(label)
    trace("formatting:once")


def compare[T: Writable](value: T, text: String) raises:
    trace("formatting:write")
    var written = String()
    value.write_to(written)
    trace("formatting:constructor")
    var constructed = String(value)
    trace("formatting:end")
    assert_equal(text, written)
    assert_equal(text, constructed)


def owned_text() raises -> String:
    var tm = TermManager()
    return tm.mkInteger("12345678901234567890123456789012345678901234567890").toString()


def native_values() raises:
    var tm = TermManager()
    var boolean = tm.getBooleanSort()
    var term = tm.mkConst(boolean, "π😀")
    begin["formatting:Term"]()
    compare(term, term.toString())
    begin["formatting:Sort"]()
    compare(boolean, boolean.toString())
    var op = tm.mkOp(Kind.BITVECTOR_EXTRACT, 7, 4)
    begin["formatting:Op"]()
    compare(op, op.toString())
    var solver = Solver(tm)
    solver.setLogic("QF_UF")
    var result = solver.checkSat()
    begin["formatting:Result"]()
    compare(result, result.toString())
    assert_equal(result.toString(), "sat")

    var decl = tm.mkDatatypeDecl("Box")
    var cons = tm.mkDatatypeConstructorDecl("box")
    cons.addSelector("value", boolean)
    decl.addConstructor(cons)
    begin["formatting:DatatypeDecl"]()
    compare(decl, decl.toString())
    begin["formatting:DatatypeConstructorDecl"]()
    compare(cons, cons.toString())
    var datatype = tm.mkDatatypeSort(decl).getDatatype()
    var constructor = datatype[0]
    var selector = constructor[0]
    begin["formatting:Datatype"]()
    compare(datatype, datatype.toString())
    begin["formatting:DatatypeConstructor"]()
    compare(constructor, constructor.toString())
    begin["formatting:DatatypeSelector"]()
    compare(selector, selector.toString())

    var synth = Solver(tm)
    synth.setOption("sygus", "true")
    synth.setLogic("ALL")
    var start = tm.mkVar(boolean, "G")
    var grammar = synth.mkGrammar([], [start])
    grammar.addRule(start, tm.mkTrue())
    begin["formatting:Grammar"]()
    compare(grammar, grammar.toString())
    var before = grammar.toString()
    var alias = grammar
    grammar.addRule(start, tm.mkFalse())
    var after = grammar.toString()
    assert_true(before != after and "false" in after)
    assert_equal(alias.toString(), after)
    assert_true("false" not in before, "returned strings must own their data")
    _ = synth.synthFun("f", [], boolean)
    synth.addSygusConstraint(tm.mkTrue())
    var synthesis = synth.checkSynth()
    begin["formatting:SynthResult"]()
    compare(synthesis, synthesis.toString())

    var reader = Solver(tm)
    var parser = InputParser(reader)
    parser.setStringInput(InputLanguage.SMT_LIB_2_6, "(set-logic QF_UF)", "format")
    var command = parser.nextCommand()
    begin["formatting:Command"]()
    compare(command, command.toString())
    var retained = owned_text()
    _ = tm.mkString("other").toString()
    assert_equal(retained, "12345678901234567890123456789012345678901234567890")
    # Existing Command.toString is a mirrored, raising native method. Keep its
    # null rejection distinct from the Writable null marker.
    var caught = False
    try:
        _ = Command().toString()
    except e:
        caught = String(e).startswith("cvc5: ")
    assert_true(caught)
    assert_equal(String(Command()), "null")
    assert_equal(term.toString(), String(term))


def null_values() raises:
    trace("formatting:nulls")
    assert_equal(Term().toString(), "null")
    assert_equal(Sort().toString(), "null")
    assert_equal(Result().toString(), "none")
    assert_equal(SynthResult().toString(), "(NONE)")
    assert_equal(Op().toString(), "NULL_TERM")
    assert_equal(Grammar().toString(), "")
    assert_equal(Datatype().toString(), "Datatype(null)")
    assert_equal(DatatypeConstructor().toString(), "DatatypeConstructor(null)")
    assert_equal(DatatypeConstructorDecl().toString(), "DatatypeConstructorDecl(null)")
    assert_equal(DatatypeDecl().toString(), "DatatypeDecl(null)")
    assert_equal(DatatypeSelector().toString(), "DatatypeSelector(null)")
    trace("formatting:end")


def fail(shim_path: String, fault: String, route: String) raises:
    var tm = TermManager()
    var integer = tm.mkInteger(Int(42))
    var api = c_api()
    var shim = OwnedDLHandle(shim_path)
    api[]._cvc5_term_to_string = rebind[_DLCallable[CChars, MutUntrackedOrigin]](
        shim.get_function[CChars]("format_" + fault))
    if route == "once":
        _ = integer.toString()
    elif route == "write":
        var text = String()
        integer.write_to(text)
    else:
        _ = String(integer)
    _ = shim^
    raise Error("formatting unexpectedly returned")


def main() raises:
    var args = argv()
    if len(args) == 4:
        fail(args[1], args[2], args[3])
        return
    native_values()
    null_values()
    print("single-pass formatting passed")
