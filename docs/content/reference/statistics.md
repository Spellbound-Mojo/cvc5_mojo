# Statistics

Solvers and term managers keep statistics about their work. Python returns
each statistic as a dict with the keys `default`, `internal`, and `value`.
Mojo returns a `Stat`, which has them as fields:

- `default: Bool`, whether the statistic still has its default value;
- `internal: Bool`, whether it is internal to cvc5;
- `value: Stat.Value`, a `Variant[Int, Float64, String, Dict[String, UInt64]]`.
  Test its type with `value.isa[Int]()`, and read it with `value[Int]`. A
  histogram maps names to counts.

So Python's `stats["name"]["value"]` is `stats["name"].value[Int]`, and
`stats.get()` returns a `Dict[String, Stat]`. A `Stat` prints as Python
prints the dict, for example `{'default': False, 'internal': True, 'value': 0.0}`.
See the [base API](../architecture/layers.md#hand-written-methods).

<!-- api: Statistics -->
