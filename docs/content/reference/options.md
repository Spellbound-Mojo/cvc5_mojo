# Solver option reference

This catalog comes from the pinned cvc5 release. The generator queries its
C API for canonical option names, aliases, value kinds, defaults, bounds,
and modes, then joins those records with descriptions in the same release's
option declarations. Each entry links to its source at the pinned commit.

Defaults below are those reported for a fresh solver in the pinned binary.
Selecting a logic or other options can affect solver configuration; these
values are not a report of your running solver's final settings. Options
and modes are listed as reported by the release, including expert and
undocumented categories. Listing an option does not imply that it can be
changed after solving or combined with every other option.

Use the exact name and a string value with
[`Solver.setOption`](solver.md#Solver.setOption). Start with the
[configuration guide](../guides/solver-options.md) for models, incremental
queries, conflict explanations, and resource limits. The current Mojo
availability of introspection methods is shown in the Solver reference.

Descriptions retain upstream terminology, including references to command
line syntax. A `void` value kind has no scalar default reported by the API;
the catalog does not invent one. Numeric bounds appear only when the API
reports them, and mode descriptions are included when present in the source.

## Catalog by upstream module

<!-- options: all -->
