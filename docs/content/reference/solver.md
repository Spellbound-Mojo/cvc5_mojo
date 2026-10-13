# Solver

A solver holds assertions, options, and a logic. It answers satisfiability
queries and gives models, unsat cores, interpolants, abducts, quantifier
elimination, synthesis, and proofs. The results and proofs it returns stay
valid after the solver is destroyed; see
[ownership and errors](../start/ownership.md).

`getOptionInfo` returns an `OptionInfo`. Its fields are the keys of the dict
that Python returns: `name`, `aliases`, `setByUser`, `category`, `type`,
`current`, `default`, `minimum`, `maximum`, and `modes`. It prints as Python
prints the dict. See the [base API](../architecture/layers.md#hand-written-methods).

<!-- api: Solver -->
