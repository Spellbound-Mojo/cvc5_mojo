# Packaging

Version **1.4.1.0** is being prepared for the modular-community conda
channel. The recipe builds and passes its tests with the channel's
`rattler-build` on Linux x86-64 and macOS; publication is pending.

## Channel and recipe

`recipes/cvc5_mojo/recipe.yaml` targets **linux-64, linux-aarch64, and osx-arm64**. It
downloads the matching official shared build and checksum for each
platform. The macOS package is for Apple Silicon.
Intel Macs and 32-bit ARM builds are skipped.
The [installation guide](../start/installation.md#install-the-package)
lists the consumer commands to use once the package is published.

- **Compiler.** Build and host environments use Mojo 1.1.0. The run
  requirement, `pin_compatible('mojo-compiler', upper_bound='x.x')`,
  renders as `>=1.1.0,<1.2.0a0`: any Mojo 1.1 patch release. A precompiled
  `.mojoc` is tied to its compiler's minor version, so a new Mojo minor
  needs a new build.
- **Package format.** The precompiled module is installed at
  `$PREFIX/lib/mojo/cvc5_mojo.mojoc`.
- **Tests.** The recipe runs five programs from the tagged source against
  the installed packages, without `-I`: `tests/smoke/test_smoke.mojo`,
  `test_lifetimes.mojo`, and `test_api.mojo` (APN values, statistics, and
  the parser), and `docs/examples/plugins.mojo` and `oracles.mojo`
  (callbacks). Native libraries are found through `$CONDA_PREFIX`; see
  [loading the library](runtime.md#loading-the-library).
- **Build tools.** Python and LLVM's tools stage and inspect the native
  libraries. They are build dependencies, not new binding runtime APIs.

## Version and source

The version is cvc5's version followed by a bindings revision:
`1.4.1.0` binds cvc5 1.4.1; `1.4.1.1` would change only the bindings.
`pixi.toml` and the recipe use the same version. An upstream `bump` moves
both to the new cvc5 version with revision zero.

The recipe builds from the tag `v${{ version }}`, currently `v1.4.1.0`, of
[Spellbound-Mojo/cvc5_mojo](https://github.com/Spellbound-Mojo/cvc5_mojo).
As of 2026-10-13 neither the public repository nor the tag exists. Before
submitting the recipe:

1. Review and commit the release contents, including generated files.
2. Publish the release tree as one commit in the public repository, and
   push `v1.4.1.0` at that commit; keep published release tags fixed.
3. Build the recipe from that tag and record the resolved commit in the
   release notes or channel PR.

For local recipe validation before publication, use a temporary recipe
whose first source is the working tree, with `path` and
`use_gitignore: true`. Preserve the checked upstream archive URL and hash.
Do not submit that local-source recipe to the channel.

## apn_mojo

The [base API](layers.md#base-api) takes and returns apn_mojo's `Integer`
and `Rational`. Version 1.0.1 is
[published on modular-community](https://prefix.dev/channels/modular-community/packages/apn_mojo).
The recipe requires it in build, host, and run environments. The checkout
installs it through Pixi, and `pixi.lock` records the build and checksum.
Update the recipe and Pixi pins together when upgrading.

## Bundling libcvc5

The native libraries live in `$PREFIX/lib/cvc5_mojo/lib`, separate from
other packages' libraries. The staging command is shared by local checks
and the recipe:

```sh
pixi run --locked python -m bindgen.package_native \
  --release third_party/cvc5 --prefix build/native-package-check
```

Use a fresh destination for each run. The staging tool refuses to merge
with an existing native-library or license directory.

`bindgen.c_library` extracts each library's checksum, byte size, aliases,
SONAME or Mach-O install name, dependencies, search paths, ELF symbol
versions, and Mach-O deployment targets into the
API snapshot, keyed by conda platform. Staging verifies those facts against
the supplied release and rejects a library from the wrong architecture.
C API exports must agree across all pinned archives. Their shared library
stems receive `.so` on Linux and `.dylib` on macOS. Starting with these
C API libraries, staging
follows dependencies within the archive. Unused JNI and C++ convenience
libraries, CMake files, libtool metadata, and pkg-config files are omitted.

The release zip stores library aliases as full copies. Staging keeps the
most specific filename for each byte-identical library family and makes
relative symlinks for its aliases. Different bytes are never deduplicated.
The libraries themselves are unchanged, and binary relocation stays
disabled. Linux uses upstream relative RUNPATHs. macOS uses `@rpath`
install names with `@loader_path` search paths, preserving the upstream
code signatures as well as the library bytes. These paths are recorded in
the inventory. Missing loader-relative dependencies fail staging; absolute
system-library references remain external.

`$PREFIX/lib/cvc5_mojo/native-libraries.json` records the shipped libraries,
aliases, external dependency names, and installed license paths. System
dependencies stay external:

- **Linux.** The shipped libraries need glibc 2.33, below the 2.34 that
  Mojo itself needs, and libstdc++ symbols up to `GLIBCXX_3.4.29`, from
  GCC 11. The recipe requires `libstdcxx >=11` on Linux.
  `tests/bindgen/test_packaging.py` checks that bound against the symbol
  versions in the snapshot, so a bump that needs a newer libstdc++ fails
  until the bound rises.
- **macOS.** The shipped libraries target macOS 11 and link only the
  system `libc++` and `libSystem`. The package declares no minimum macOS
  version; Mojo's own requirement, macOS 15, applies.

The recipe removes Mojo's `share/max/firstActivation` marker after
compilation so it is not distributed as package content.

## Platform validation

| Target | Package build and recipe tests | Native execution |
|---|---|---|
| `linux-64` | Built and tested locally with `rattler-build` 0.30.0 | The full `test` gate, `docs-test`, and a fresh consumer installation |
| `linux-aarch64` | Configured; first built by the channel's CI | Not validated before submission; the channel's CI runs the recipe tests on an ARM runner |
| `osx-arm64` | Built and tested locally with `rattler-build` 0.30.0 on macOS 26.6.2 (M2 Max) | cvc5's translated tests and examples, the smoke tests other than `test_threads.mojo`, and a fresh consumer installation; see [development](../contributing/development.md#environment) for the Linux-only gates |

All targets use cvc5 1.4.1, Mojo 1.1.0, and apn_mojo 1.0.1. `fetch` places
the host’s solver at `third_party/cvc5` and the other builds at
`third_party/cvc5-<platform>`. LLVM inspects their exported symbols and
native dependencies without executing foreign binaries. The C ABI checks
and Mojo compilation still use the host toolchain.

For the Linux x86-64 archive, staging reduces 113,780,200 bytes of shared
library files to 37,661,432 bytes: six libraries and twelve relative
symlinks. This preserves the library bytes and all eight license files.
These measurements describe that archive, not every platform.

On 2026-10-13 both local package builds passed the recipe tests. In a
fresh Pixi project with only the three channels,
`pixi add "mojo==1.1.0" "cvc5_mojo==1.4.1.0"` resolved apn_mojo 1.0.1, and
the quickstart, integer, plugin, and oracle examples ran with `mojo run`
and as a built executable, without `-I` or `CVC5_MOJO_LIBRARY`. In the
macOS package the aliases are symlinks and the upstream code signatures
verify. The `Linux ARM64` workflow builds the recipe and runs its tests
on an ARM runner, the way the channel's CI does: from the checkout on each
push, and from the release tag on demand.

## Licenses

`NOTICE` records the project's provenance and the upstream components.
Staging copies the project `LICENSE` and `NOTICE`, upstream `COPYING`, and
the complete upstream `licenses/` directory into
`$PREFIX/share/licenses/cvc5_mojo`. The recipe also includes those notices
in its package license metadata. The native inventory lists their paths
so the staged files can be checked against the source archive.

## Remaining work

- Publish the reviewed source as `Spellbound-Mojo/cvc5_mojo` with the tag
  `v1.4.1.0`, rebuild the recipe from the tag, and submit it to
  modular-community.
- After the upload succeeds, verify a fresh installation on all three
  platforms and update the installation page and
  [release notes](../releases.md).
