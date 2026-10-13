# Plugin

Plugins let cvc5 call your Mojo code during solving. Implement the `Plugin`
trait in a struct, put an instance in an `ArcPointer`, and register it with
`Solver.addPlugin`. You can supply application lemmas or observe learned
clauses and theory lemmas.

## Add a rule during search

This example supplies the application rule `x >= 0` from `check()`. Together
with the asserted constraint `x < 0`, it makes the query unsatisfiable.

<!-- example: docs/examples/plugins.mojo -->

For a fixed rule like this, `assertFormula` is simpler. A plugin becomes
useful when your application computes additional constraints during search
or needs to observe what the solver learns. The plugin receives no current
model or assignment from `check()`; it is not a model callback.

The returned lemmas must be Boolean terms from the solver's term manager.
cvc5 treats them as constraints. Your application is responsible for their
meaning and validity: returning `False` forces unsatisfiability, whether or
not the original assertions were contradictory. Avoid returning a lemma
that is valid only under a temporary assumption without encoding that
assumption in the lemma.

## Choose the callbacks you need

| Method | Mojo behavior |
|---|---|
| `check(mut self)` | Return a `List[Term]`. The default returns an empty list. cvc5 calls it periodically during search; do not depend on an exact call count. |
| `notifySatClause(mut self, clause)` | Observe a learned SAT clause. The default does nothing. |
| `notifyTheoryLemma(mut self, lemma)` | Observe a theory lemma. The default does nothing. |
| `getName()` | A static method returning a compile-time `StaticString`, used for debugging. The default is `"MojoPlugin"`. |

An observer can store counters or append the received `Term` to a list in
its struct. Read its state afterward through `plugin[]`. Stored terms hold
their own references, so they remain usable after the callback and solver
have finished. The upstream
[`test_plugin_listen`](https://github.com/Spellbound-Mojo/cvc5_mojo/blob/main/tests/cvc5/test_solver.mojo) exercises both
notifications. Its configuration uses `sat-solver=minisat` and
`plugin-notify-sat-clause-in-solve=false`; the latter changes when SAT
notifications are delivered. Register plugins and set options before the
first query.

Mojo uses trait conformance instead of Python subclassing. Names are static
because the pinned C `get_name` callback has no state parameter. The other
three callbacks receive the registered instance and can mutate its fields.

## Ownership and errors

Registration retains the `ArcPointer` and a stable callback table for the
native solver's lifetime. You can drop your local pointer after registration,
or keep it to inspect the callback state. Copies of a solver share its
registrations. A solver obtained from `InputParser.getSolver()` uses the
same registration storage, including when the parser outlives the original
Mojo solver value. There is no plugin removal API.

Parsed `Command` values retain the parser state too, so releasing the local
parser does not leave its native solver with dangling callback pointers.

Keep the callback's data graph independent of its solver. Storing that
solver in the plugin creates a reference cycle; break any such cycle
explicitly. As with the rest of these bindings, do not share solver object
graphs or mutable plugin instances between threads.

Callbacks may raise Mojo errors. The bridge catches the error before it
crosses C, suppresses further user callbacks for that solver, and raises it
when the enclosing solver operation returns. This also applies to
`Command.invoke`. The native solve is not immediately interrupted; use
the usual solver resource limits when you need a bounded search. Discard
the solver after a callback error: later operations raise the stored error
rather than returning a potentially misleading result.

Build terms through the associated `TermManager` inside callbacks. Calling
back into the same solver, including through a copied or parser-derived
handle, raises a reentry error. The bridge also rejects non-Boolean lemmas,
null lemmas, and lemmas from another term manager.

## API reference

<!-- api: Plugin -->
