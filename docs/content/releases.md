# Release notes

## 1.4.1.0 — in preparation

This is the first planned modular-community release. It binds **cvc5 1.4.1**
on **Linux x86-64, Linux ARM64, and macOS Apple Silicon**, using **Mojo 1.1.0** and **apn_mojo 1.0.1**. The package
is not published yet, and its source tag `v1.4.1.0` has not been created.
The last version component is the bindings revision; a bindings-only
update would be `1.4.1.1`.

### Included functionality

- Generated bindings for the non-deprecated Python base API, with exact
  integers and rationals supplied by apn_mojo.
- Plugin callbacks for supplying lemmas and observing solver notifications.
- Oracle function callbacks through `Oracle.evaluate` and
  `Solver.declareOracleFun`, with retained state and contained callback errors.
- Python-compatible status queries on null results and synthesis results,
  and supported queries on null proofs.
- Silent sort inequality, Unicode string handling, checked numeric
  conversions, and ownership that keeps native parents alive.
- Tested tutorials, a transcendental-functions course, a scheduling
  application, and a generated API reference.

### Distribution

The recipe targets `linux-64`, `linux-aarch64`, and `osx-arm64`, selects the matching
native archive for each architecture, and includes the solver and parser with
their bundled dependencies, and installs one physical copy of each needed
library with relative symlinks for its aliases. It preserves the upstream
license notices and records the native library inventory. The package
requires Mojo 1.1 (`>=1.1.0,<1.2.0a0`), apn_mojo 1.0.1, and on Linux
`libstdcxx >=11`. See [installation](start/installation.md) for the
commands to use after publication and [packaging](architecture/packaging.md)
for remaining work.

### Compatibility and limits

The deprecated methods from the pinned Python API, `Term.toPythonObj`, and
the Pythonic convenience layer are not included. macOS requires Apple
Silicon and macOS 15 or later; Intel Macs and 32-bit ARM are not targeted. Oracle callbacks are experimental and must
be deterministic and stay with their registering solver. See
[support and limitations](guides/status.md) for the complete boundaries,
including upstream memory behavior and solver limits.

### Release validation

On Linux x86-64 the full test gate and every documentation example pass.
The conda recipe builds and passes its tests with the channel's
`rattler-build` on Linux x86-64 and on macOS Apple Silicon, where cvc5's
translated unit tests and examples also pass. A fresh consumer project
installs the package and runs the examples on both. Linux ARM64 has not
run natively before submission; the channel's CI is its first native
build and test. See [platform validation](architecture/packaging.md#platform-validation).
