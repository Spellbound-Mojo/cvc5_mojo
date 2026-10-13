# 8. Try alternatives with assertion scopes

Many tasks keep a fixed set of requirements while trying different
candidates. Assertion scopes let you add a temporary condition, check it,
and remove it without reconstructing the whole problem.

Prerequisite: [results and models](models.md).

## Preserve the base problem

The base problem is `0 <= x <= 10`. The first candidate asks for `x > 10`
and fails. The second asks for `x = 7` and succeeds.

<!-- example: docs/examples/incremental.mojo -->

Enable incremental solving before the first query. A `push` establishes a
new assertion level. Assertions added afterward belong to that level; a
matching `pop` removes them. The two bounds asserted before either push
remain in place throughout.

| Point in the program | Active assertions |
|---|---|
| Initial setup | `0 <= x`, `x <= 10` |
| First scope | The base bounds and `x > 10` |
| After the first pop | The base bounds |
| Second scope | The base bounds and `x = 7` |

The successful second query also checks that the first candidate did not
remain asserted. Without the first `pop`, both candidate conditions would
accumulate and the second check would still be unsatisfiable.

## Scope changes affect assertions

The term `x` is still usable after a pop. Popping a level changes the
solver's assertion stack; it does not erase terms from the term manager.
Similarly, a saved result still describes its original query, not the
current assertion stack.

Read a candidate's model values before popping the candidate. In code that
can raise inside a scope, make balancing the push and pop explicit on the
recovery path. A fresh solver per independent problem can be clearer when
the setup cost is small or error handling is complicated.

Copying a `Solver` value shares its underlying state in the current
bindings. It does not create an independent assertion stack. Construct
another solver when you need independent mutable problems; see
[ownership](../start/ownership.md).

## Exercise: nested scopes

Inside the `x = 7` scope, push again and assert `x < 5`. What remains after
popping once?

**Worked answer.** The innermost query is `unsat`. One pop removes only
`x < 5`, restoring the satisfiable `x = 7` scope with the base bounds.
A second pop removes `x = 7` as well.

Next: [conflicting requirements](unsat-cores.md).
