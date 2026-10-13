# Upgrading cvc5

An upgrade moves the pin in `cvc5-version.toml` to a new cvc5 release and
regenerates the bindings from it. This page describes the commands, the
workflow that runs them, and what each kind of change in cvc5 needs.

## The pipeline

```sh
pixi run --locked bump [version]   # default: cvc5's latest release
pixi run generate                  # also updates pixi.lock for the new oracle pin
pixi run --locked api-diff         # Markdown summary of the API change
pixi run --locked test
```

`generate` runs without `--locked`: once `bump` has changed the oracle's
PyPI pin in `pixi.toml`, pixi must update `pixi.lock`.

**`bump`.** It resolves the release tag and its commit, downloads both
archives, and computes their sha256. It then rewrites `cvc5-version.toml`,
the context of the conda recipe, and the oracle's PyPI pin. A new cvc5
version also resets the package revision to zero in the recipe and
`pixi.toml`: cvc5 `1.4.2` would become package `1.4.2.0`, with source tag
`v1.4.2.0`. That tag is created during release preparation, not by `bump`.
If the pin is already current, it prints `up to date` and preserves the
current package revision. `pixi run --locked bump --refresh-binaries`
refreshes supported architecture assets of the current release without
resetting that revision. It resolves the official release assets, hashes
new archives, and updates both platform sources in the recipe. A moved
upstream tag is rejected.

**`api-diff`.** It compares the regenerated snapshot with the committed one
and lists:

- C functions added, removed, changed in signature, or newly deprecated;
- handle types whose ownership mode changed;
- enum values added, removed, or renumbered;
- Python methods added or removed, and binding changes.

## Automation

The workflow `.github/workflows/cvc5-update.yml` runs twice a year, on
15 January and 15 July at 06:17 UTC, and has a manual dispatch with an
optional version. On 2026-10-13, GitHub reported it as **manually
disabled**, with permission for Actions to create pull requests also off. Enabling it remains
[planned](../contributing/roadmap.md). Once enabled, each run:

1. bumps the pin;
2. regenerates;
3. writes the API diff;
4. runs the gate, the tests, and the package build;
5. opens a pull request on branch `cvc5-<version>`.

The pull request description consists of the API diff and the test log.
Test failures are recorded and still allow PR creation. A regeneration
failure stops the workflow before the tests and PR step. Creating a review report for generation failures remains
follow-up work. The workflow does not merge or publish a package.

Three repository details matter:

- **Workflow state.** Enable `cvc5-update` in the repository's Actions tab
  before relying on its schedule or manual dispatch.

- **A setting.** Settings › Actions › General › Workflow permissions ›
  "Allow GitHub Actions to create and approve pull requests" must be on.
- **CI does not run on these pull requests.** GitHub does not start other
  workflows for a pull request opened with `GITHUB_TOKEN`, so this workflow
  runs the tests itself.

## What each kind of change needs

The table lists how each kind of change in cvc5 shows up after a bump, and
who acts on it.

| cvc5 change | How it shows up | Who acts |
|---|---|---|
| New C function | "C functions added"; the raw layer picks it up | Nobody |
| New Python method that joins | "Python methods added: auto" | Nobody |
| New Python method that does not join | Gate: unresolved | Add an entry to `overrides.toml` |
| A method with an override is removed | Gate: stale override | Delete the entry |
| Changed signature | The compile check, "C signatures changed", and the regenerated code | Review |
| Renumbered enum | "Enum changes"; regenerated | Nobody |
| Changed wrapper style | Gate: join fraction below the minimum | Fix the extractors |
| Changed ownership of a handle type | The handle table in the diff, and the lifetime and leak tests | Review |
| Behavior change | The translated tests, and the examples' recorded output in `tests/cvc5/examples/` | Review |
| Newly deprecated Python method | "Binding changes" | See the [open questions](../contributing/roadmap.md#open-questions) |

`bump` also moves the oracle environment's PyPI pin (`cvc5==…` in
`pixi.toml`), so the differential tests compare against the same release.
