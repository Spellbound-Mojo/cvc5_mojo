# 2. Explain an impossible request

A customer now asks for job C to finish by time six. The base workshop
model is feasible, but this extra request conflicts with the dependency
chain A → B → C, whose durations sum to seven.

Start with the [shared scheduling model](model.md). Enable unsat-core
production before checking, as the complete program does during setup.

## Isolate the new requirement

Use a pushed scope for the rush request. Its constraint concerns only C;
it does not impose a deadline on every job. An `unsat` result means this
request cannot be satisfied alongside the base requirements.

<!-- excerpt: docs/examples/schedule_application.mojo#conflict -->

The returned core contains asserted terms. The program maps each one to a
label by comparing it with the original requirement terms. Here Mojo
`term == requirement` compares the symbolic expressions; it does not build
a new SMT equality. Logical equality inside a constraint instead uses
`mkTerm(Kind.EQUAL, ...)`.

The special rush constraint gets its own label, “C must finish by 6.” The
other labels come from the same list that was assembled with the model.
Keeping a source formula with its label avoids trying to diagnose the
problem by parsing printed SMT syntax.

## Interpret the explanation carefully

The core is an inconsistent subset of the assertions. It is not necessarily
the smallest inconsistent subset, nor a unique explanation. Its order and
choice of redundant requirements need not remain stable. That is why the
program checks that every core term has a recognized label, without
recording one particular core ordering as expected output.

The rush request must appear in a valid core here: the base model was
already shown satisfiable. The program checks this property explicitly.
The final `pop` removes the request, allowing the same solver to proceed
to deadline search.

An interface can present the labels as conflicting requirements and let a
person revise one. Choosing which requirement to relax is an application
decision. A core by itself does not rank the cost or importance of a change.

## Exercise: explain the mathematical conflict

Why is the six-unit deadline impossible even if the second machine were
unlimited?

**Worked answer.** A cannot start before zero. B cannot start until A's two
units finish, and C cannot start until B's three units finish. C then needs
two units itself. These dependencies force C's end to be at least seven,
independently of the capacity constraints and job D.

Next: [find and certify the minimum deadline](optimization.md).
