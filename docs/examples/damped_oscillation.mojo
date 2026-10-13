"""Certify a damped signal envelope over uncertain parameters and time intervals."""

from std.testing import assert_true
from cvc5_mojo import TermManager, Solver, Term, Kind


def real(tm: TermManager, value: Int) raises -> Term:
    return tm.mkTerm(Kind.TO_REAL, tm.mkInteger(value))


# docs:begin configuration
def configured(tm: TermManager, logic: String, budget: Int) raises -> Solver:
    var solver = Solver(tm)
    solver.setLogic(logic)
    solver.setOption("rlimit-per", String(budget))
    solver.setOption("tlimit-per", "1000")
    return solver^
# docs:end configuration


def interval(tm: TermManager, value: Term, lower: Term, upper: Term) raises -> Term:
    return tm.mkTerm(Kind.AND,
        tm.mkTerm(Kind.GEQ, value, lower), tm.mkTerm(Kind.LEQ, value, upper))


def outside(tm: TermManager, value: Term, bound: Term) raises -> Term:
    return tm.mkTerm(Kind.OR,
        tm.mkTerm(Kind.LT, value, tm.mkTerm(Kind.NEG, bound)),
        tm.mkTerm(Kind.GT, value, bound))


def direct_query(tm: TermManager) raises:
    var solver = configured(tm, "QF_NRAT", 1)
    # docs:begin signal
    var amplitude = tm.mkConst(tm.getRealSort(), "amplitude")
    var damping = tm.mkConst(tm.getRealSort(), "damping")
    var frequency = tm.mkConst(tm.getRealSort(), "frequency")
    var phase = tm.mkConst(tm.getRealSort(), "phase")
    var time = tm.mkConst(tm.getRealSort(), "time")
    var zero = real(tm, 0)
    var one = real(tm, 1)
    var two = real(tm, 2)
    var quarter = tm.mkTerm(Kind.DIVISION, one, real(tm, 4))
    solver.assertFormula(interval(tm, amplitude, zero, one))
    solver.assertFormula(interval(tm, damping, one, two))
    solver.assertFormula(interval(tm, frequency, one, two))
    solver.assertFormula(interval(tm, phase, tm.mkTerm(Kind.NEG, quarter), quarter))
    solver.assertFormula(interval(tm, time, zero, two))
    var exponent = tm.mkTerm(Kind.NEG, tm.mkTerm(Kind.MULT, damping, time))
    var angle = tm.mkTerm(Kind.ADD, tm.mkTerm(Kind.MULT, frequency, time), phase)
    var signal = tm.mkTerm(Kind.MULT, amplitude,
        tm.mkTerm(Kind.EXPONENTIAL, exponent), tm.mkTerm(Kind.SINE, angle))
    solver.assertFormula(outside(tm, signal, one))
    # docs:end signal
    var result = solver.checkSat()
    assert_true(result.isUnknown())
    print("direct query with budget 1: unknown")


def certify_sine(tm: TermManager) raises -> Bool:
    var solver = configured(tm, "QF_NRAT", 100000)
    var angle = tm.mkConst(tm.getRealSort(), "arbitrary_angle")
    solver.assertFormula(outside(tm, tm.mkTerm(Kind.SINE, angle), real(tm, 1)))
    var result = solver.checkSat()
    if result.isSat():
        raise Error("sine range has a counterexample")
    return result.isUnsat()


def certify_rate(tm: TermManager, lower: Int, upper: Int) raises -> Bool:
    var solver = configured(tm, "QF_NRA", 100000)
    # docs:begin rate
    var damping = tm.mkConst(tm.getRealSort(), "damping")
    var time = tm.mkConst(tm.getRealSort(), "time")
    solver.assertFormula(interval(tm, damping, real(tm, 1), real(tm, 2)))
    solver.assertFormula(interval(tm, time, real(tm, lower), real(tm, upper)))
    solver.assertFormula(tm.mkTerm(Kind.LT,
        tm.mkTerm(Kind.MULT, damping, time), real(tm, lower)))
    # docs:end rate
    var result = solver.checkSat()
    if result.isSat():
        raise Error("damping-times-time lower bound has a counterexample")
    return result.isUnsat()


def certify_decay(tm: TermManager, lower: Int, upper: Int, denominator: Int, budget: Int) raises -> Bool:
    if not certify_rate(tm, lower, upper):
        return False
    var solver = configured(tm, "QF_NRAT", budget)
    # docs:begin decay
    # The rate certificate gives u = damping*time >= lower.
    var u = tm.mkConst(tm.getRealSort(), "rate_times_time")
    solver.assertFormula(tm.mkTerm(Kind.GEQ, u, real(tm, lower)))
    solver.assertFormula(tm.mkTerm(Kind.LT,
        tm.mkTerm(Kind.EXPONENTIAL, u), real(tm, denominator)))
    # Proving exp(u) >= denominator > 0 gives
    # exp(-u) = 1/exp(u) <= 1/denominator.
    # docs:end decay
    var result = solver.checkSat()
    if result.isSat():
        raise Error("exponential lower bound has a counterexample")
    return result.isUnsat()


def certify_product(tm: TermManager, denominator: Int) raises -> Bool:
    var solver = configured(tm, "QF_NRA", 100000)
    # docs:begin product
    var amplitude = tm.mkConst(tm.getRealSort(), "amplitude")
    var decay = tm.mkConst(tm.getRealSort(), "decay_enclosure")
    var sine = tm.mkConst(tm.getRealSort(), "sine_enclosure")
    var zero = real(tm, 0)
    var one = real(tm, 1)
    var bound = tm.mkTerm(Kind.DIVISION, one, real(tm, denominator))
    solver.assertFormula(interval(tm, amplitude, zero, one))
    solver.assertFormula(interval(tm, decay, zero, bound))
    solver.assertFormula(interval(tm, sine, tm.mkTerm(Kind.NEG, one), one))
    solver.assertFormula(outside(tm, tm.mkTerm(Kind.MULT, amplitude, decay, sine), bound))
    # docs:end product
    var result = solver.checkSat()
    if result.isSat():
        raise Error("product enclosure has a counterexample")
    return result.isUnsat()


def main() raises:
    var tm = TermManager()
    direct_query(tm)
    var sine_ok = certify_sine(tm)
    assert_true(sine_ok)
    # docs:begin coverage
    var early_ok = certify_decay(tm, 0, 1, 1, 100000) and certify_product(tm, 1)
    assert_true(early_ok)
    print("[0, 1]: absolute signal <= 1 certified")
    var late_ok = certify_decay(tm, 1, 2, 2, 1)
    assert_true(not late_ok)
    var complete = sine_ok and early_ok and late_ok
    assert_true(not complete)
    print("[1, 2] with budget 1: inconclusive")
    print("whole time window: not yet certified")

    late_ok = certify_decay(tm, 1, 2, 2, 100000) and certify_product(tm, 2)
    complete = sine_ok and early_ok and late_ok
    assert_true(complete)
    print("[1, 2]: absolute signal <= 1/2 certified")
    print("whole time window: absolute signal <= 1 certified")
    # docs:end coverage
