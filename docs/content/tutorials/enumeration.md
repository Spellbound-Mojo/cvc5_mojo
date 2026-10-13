# 10. Enumerate a finite solution space

To find more than one model, exclude the assignment you have already seen
and query again. When the selected symbols have finitely many possible
assignments, a final `unsat` result establishes that enumeration is complete.

Prerequisites: [results and models](models.md) and
[incremental solving](incremental.md).

## Block the tuple

Find nonnegative integer pairs `(x, y)` with `x + y = 2`. There are three:
`(0, 2)`, `(1, 1)`, and `(2, 0)`.

<!-- example: docs/examples/enumeration.mojo -->

After each satisfiable result, the program reads both coordinates and adds
the negation of their conjunction:

```text
NOT (x = previous_x AND y = previous_y)
```

This excludes exactly that pair. Requiring `x != previous_x` and
`y != previous_y` separately would exclude all assignments sharing either
coordinate, which can skip valid solutions in a general problem.

The example's test checks that every returned pair belongs to the known
solution set, that no pair repeats, and that the final count is three.
It prints the count rather than a solver-dependent enumeration order.

## Know what completeness means

The nonnegative bounds and fixed sum bound both coordinates above by two.
That mathematical fact makes the selected space finite. Removing those
bounds admits infinitely many integer pairs, so this loop would no longer
be a complete terminating enumeration procedure.

If the larger model has additional symbols, blocking only `(x, y)`
enumerates distinct projections onto those coordinates. Different internal
assignments with the same pair are deliberately combined. Include more
symbols in the blocking formula if their distinctions matter to your task.

An `unknown` result cannot be treated as exhaustion. The example raises
instead of printing “all solutions found” in that case. An application
could return the partial list together with an explicit incomplete status.

## Exercise: change the sum

How many nonnegative integer pairs sum to three?

**Worked answer.** Four: `(0, 3)`, `(1, 2)`, `(2, 1)`, `(3, 0)`. More
generally, a nonnegative integer total `n` gives `n + 1` ordered pairs.
Update the expected set as well as the total and count in a copy of the
program. The blocking formula does not change.

Next: [graph coloring](coloring.md).
