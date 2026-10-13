# 11. Color a graph

Assign each vertex an integer representing a color. Bound the available
colors and require the endpoints of every edge to differ. A satisfying
assignment is then a valid coloring.

Prerequisites: [integer constraints](integers.md) and
[results and models](models.md).

## Model a triangle

All three vertices in a triangle are adjacent. Its colors must therefore
be pairwise distinct. Two available colors are insufficient; three suffice.

<!-- example: docs/examples/coloring.mojo -->

The function builds a fresh solver for each color budget. Its loop creates
three symbolic integers with bounds `0 <= vertex < colors`. The all-distinct
constraint expresses the three edges compactly for this particular graph.

The successful case checks the returned model's bounds and edge condition,
rather than requiring a particular permutation of color numbers. Color
labels have no intrinsic meaning here: swapping red and blue changes the
printed assignment without changing the validity of the coloring.

## Generalize to an edge list

For a general graph, create one term per vertex, then loop over the edge
list and assert a disequality for each pair of endpoints. Do not assert
that every vertex has a different color. Nonadjacent vertices may share a
color, and forbidding that would solve a different problem.

The Mojo loops construct a finite collection of formulas. They are not
quantifiers inside the solver. The graph's size is known to the program
constructing the model, and each edge becomes an explicit assertion.

Fixing one vertex's color can remove equivalent assignments caused by
renaming colors. Such a symmetry restriction is justified only when the
color labels really are interchangeable. If “red” represents a resource
with special restrictions, arbitrarily fixing a vertex to red can remove
valid solutions.

## Exercise: remove an edge

What happens if the triangle becomes a path with two edges?

**Worked answer.** Two colors now suffice: the endpoint vertices can share
one color while the middle vertex uses the other. Replace the all-distinct
constraint with just the two edge disequalities. This demonstrates why the
graph's edge list, rather than an all-distinct shortcut, must define the
general encoding.

Next: [scheduling](scheduling.md).
