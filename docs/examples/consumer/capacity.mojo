"""Describe a consumer application's worker-capacity requirement."""

from cvc5_mojo import TermManager, Term, Kind


def required_capacity(tm: TermManager, workers: Term, tasks: Int) raises -> Term:
    # Each worker can process three tasks in this application.
    var capacity = tm.mkTerm(Kind.MULT, tm.mkInteger(3), workers)
    return tm.mkTerm(Kind.AND,
        tm.mkTerm(Kind.GEQ, workers, tm.mkInteger(0)),
        tm.mkTerm(Kind.GEQ, capacity, tm.mkInteger(tasks)))
