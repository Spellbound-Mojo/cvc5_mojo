# Troubleshooting

Run commands from the repository root, with the pinned tools:

```sh
pixi run --locked mojo --version
pixi run --locked mojo run -I src your_program.mojo
```

Compare a failing call with the nearest [example](../examples/index.md) and
its entry in the [API reference](../reference/index.md).

| Symptom | What to check |
|---|---|
| `libcvc5.so not found` or `libcvc5.dylib not found` | Run `pixi run --locked fetch`, which places the library in `third_party/cvc5/lib`. Then run programs from the repository root, or set `CVC5_MOJO_LIBRARY` to the full path of the main library (`libcvc5.so` on Linux or `libcvc5.dylib` on macOS). The matching parser library is loaded from the same directory, so the same advice applies when the message names it. See [where the library is found](../start/installation.md#where-the-library-is-found). |
| `module 'cvc5_mojo' not found` | Pass `-I src` from the repository root, or an absolute path to the binding sources. Use `-I build` for the precompiled package. |
| `module 'apn_mojo' not found` | Run `pixi install --locked`, then build with `pixi run --locked mojo`. The released dependency is installed in the Pixi environment; remove any old `-I third_party/apn_mojo` argument. |
| An error message starts with `cvc5: ` | cvc5 rejected the call; the rest is cvc5's own message. For example, `expecting an arithmetic subterm` means that a term of the wrong sort was passed. The call had no effect, and your program can catch the error and continue; see [errors are Mojo errors](../start/ownership.md#errors-are-mojo-errors). |
| A method that Python accepts does not compile | Mojo resolves overloads by type. Check the Mojo signature in the reference: a Python `int` of any size is an `Integer`, a list is a `List[Term]`, and a deprecated `Solver.mk*` method is called on the `TermManager`. |
| `mojo build` fails with `undefined reference to dlerror@GLIBC_2.34` | The C compiler's sysroot is too old for Mojo's runtime. `pixi.toml` pins `sysroot_linux-64 >= 2.34`; reinstall the environment with `pixi install --locked`. |
| `pixi run --locked check-api` fails | See [the completeness gate](#the-completeness-gate-fails). |
| CI reports generated files that differ | A generated file was edited, or the generator changed without regenerating. Run `pixi run --locked generate`, review the diff, and commit the regenerated files with the generator change. |

## A crash without a stack trace

A crash under `mojo run` prints no symbols. To get a symbolized trace, build
with line tables and run the binary:

```sh
pixi run --locked mojo build -debug-level=line-tables -I src program.mojo -o .cache/program
.cache/program
```

A crash inside the native cvc5 library usually comes from a lifetime error: a handle used
after cvc5 freed its object. Mojo destroys a value right after its last use,
so check which values are still used after the crash point. Also check the
[ownership rule](../architecture/runtime.md#handle-ownership) of each handle
type involved.

## The completeness gate fails

`pixi run --locked check-api` prints the reason:

| Reason | What to do |
|---|---|
| Unresolved Python methods | Add an entry for each one to `bindgen/overrides.toml`. |
| A stale override | Delete the entry. |
| The share of automatically joined methods is below the minimum | Investigate the extractors. |

See [working on the generator](../contributing/generator.md).

## An arithmetic equality reports mismatched sorts

Inspect both operands with `getSort`. Construct real constants with `mkReal`,
or convert an integer term with `Kind.TO_REAL` when a real equality needs it.
The [real-arithmetic tutorial](../tutorials/reals.md) shows the explicit
conversion and explains why the chosen sort changes the question.

## A query returns `unknown`

An inconclusive query is not an unsatisfiable problem. Preserve the status
and inspect resource budgets, domain assumptions, and logic selection.
The [solver-limits tutorial](../tutorials/transcendentals/results.md) shows
an explicit `unknown` branch and discusses bounded queries and reformulation.
