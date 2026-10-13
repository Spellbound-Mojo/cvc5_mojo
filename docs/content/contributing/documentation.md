# Maintaining the docs

This site is the project's documentation: its architecture, decisions, API
reference and examples. There are no separate design documents; when a
design decision changes, the relevant page here changes with it.

## Build and review

```sh
pixi run --locked -e docs docs-serve
pixi run --locked -e docs docs-build
pixi run --locked -e docs docs-check
pixi run --locked docs-test --output .cache/docs-examples-001
pixi run --locked -e oracle docs-oracle-test --output .cache/docs-oracle-001
```

- **`docs` environment.** It pins MkDocs 1.6.1 and Pygments 2.19.2.
- **`docs-build`** writes the static site to `.cache/docs-site`.
- **`docs-check`** runs the audit, builds in strict mode, then checks every
  rendered local link, anchor and asset, duplicate HTML ids, and that every
  documentation page is in the search index, including section landing pages.
  It also checks local assets referenced by CSS.
- **`docs-test`** builds and runs every example the site includes.
- **`docs-oracle-test`** runs paired Python programs in the pinned oracle
  environment and compares them with the same expected output as Mojo.

The site needs no Mojo toolchain and no cvc5 download: the reference is
rendered from the committed snapshot.

## Where things live

| Path | Contents |
|---|---|
| `mkdocs.yml` | Site configuration and navigation |
| `docs/content/` | The pages, in Markdown |
| `docs/examples/` | Every program the site includes |
| `docs/examples.json` | The expected standard output of each included program |
| `api/cvc5-api.json` | The snapshot the reference and coverage pages are rendered from |
| `docs/hooks.py` | MkDocs hooks: version, Mojo series and cvc5 release for the theme; the audit; directives; source downloads |
| `docs/theme/` | The theme shared by our projects: `main.html` and `404.html` templates, and `assets/` with styles, scripts, favicon and bundled fonts with their licenses |
| `scripts/docs_contract.py` | The audit, example regions, equation fences, and directive rendering |
| `docs/qa/` | Pinned browser and math tooling; the browser checks |
| `scripts/vendor_docs_math.py` | Reproducible local KaTeX bundling and verification |
| `bindgen/reference.py`, `report.py`, `docstrings.py` | Rendering of the reference, coverage report and docstrings |

The Architecture section is a short overview for application authors.
Put detailed internals, maintenance procedures, and validation reports in
the Contributing navigation groups. Keep existing page URLs and incoming
links intact when changing navigation. When removing a page, remove its
navigation entry and update incoming links to relevant existing pages.

## Directives

Pages include generated material with HTML-comment directives:

```text
<!-- api: Term -->
<!-- api: enums -->
<!-- example: docs/examples/quickstart.mojo -->
<!-- source: docs/examples/<file>.mojo -->
<!-- excerpt: docs/examples/quickstart.mojo#terms -->
<!-- coverage: report -->
<!-- coverage: handles -->
<!-- coverage: tests -->
<!-- coverage: calls -->
<!-- translated: quickstart -->
<!-- kinds: EXPONENTIAL SINE COSINE -->
<!-- options: produce-models incremental -->
<!-- options: all -->
<!-- python-example: docs/examples/migration.mojo -->
```

- **`api`** with a class name renders that class from the snapshot:
  - the class description;
  - a summary table, with whether the current Mojo package defines each
    method;
  - every mirrored method with its actual Mojo declarations when available,
    a separately labeled upstream Python signature, documentation, and binding.
    Mojo signatures come from `bindgen.gen_api.signatures`, the same owner
    that emits the bindings;
  - the methods that are not mirrored.

  `api: enums` renders every enum and its values.
- **`example`** renders a complete program as one frame: its file name and
  download link, the code, the run command and the expected output. The
  program must be listed in `docs/examples.json`.
- **`excerpt`** renders a named region from a program in the executable
  manifest. Full-program rendering and excerpts read the same source and
  strip the region markers. The complete program remains available through
  its `example` directive.
- **`source`** renders a file from `docs/examples/` that is not run on its
  own.
- **`python-example`** takes a Mojo manifest key and renders its paired
  Python file, oracle run command, and shared expected output. Excerpts can
  also select named regions from that registered Python file.
- **`coverage`** renders the coverage report (`report`), handle ownership
  (`handles`), translated test coverage (`tests`), or the native calls recorded
  by the translated test runner (`calls`).
- **`translated`** renders a generated example from `tests/cvc5/examples/`,
  its run command, and the expected output recorded by the Python oracle.
- **`kinds`** renders a selected operator table. Names are checked against
  the snapshot, and descriptions come from `enum_docs.Kind`, extracted by
  `bindgen.enums` from the pinned headers. Summary conversion stays in
  `bindgen.docstrings` and table rendering in `bindgen.reference`.
- **`options`** selects option names or `all`. `bindgen.options` extracts
  metadata from the pinned binary and descriptions from its source TOML;
  `bindgen.reference` renders both through the existing docstring converter.

Directives inside fenced code blocks are left alone. Directives never run
library code while the site builds.

## Rules the audit enforces

The build fails unless:

- every page starts with a `# ` title;
- no page contains a hand-written ` ```mojo ` block: include maintained
  files, so readers see exactly what was tested (use `text` fences for
  signatures and sketches);
- the `api` directives name every Python class in the snapshot, and
  `enums`, exactly once, and every class has a description;
- the set of `example` directives equals the set of programs in
  `docs/examples.json`, and each expected output ends with a newline;
- every `source` directive resolves to a `.mojo` or `.py` file within `docs/examples/`;
- every paired Python file is included and shares its Mojo program's expected
  output; working-directory settings name a known runner mode;
- every excerpt names a tested program and an existing, nonempty region;
  region names cannot repeat, nest, or have unmatched markers;
- every `coverage` directive names a known topic;
- every `translated` directive names an example marked runnable in `tests/cvc5/translation.json`;
- every `kinds` directive selects distinct, documented names from the
  snapshot's `Kind` enum.
- every `options` directive selects distinct names from the option snapshot
  or requests the whole catalog.

## Adding an example

1. Write a complete program in `docs/examples/`: a `main` that asserts its
   results with `std.testing`, and a one-line docstring that starts with a
   capital letter.
2. Run it, check its output independently, and add the path and exact output
   to `docs/examples.json`. Never record the output of a failing program.
3. Include it on the page it illustrates with an `example` directive, and list
   it in the [example gallery](../examples/index.md).
4. Run `docs-test` for it (`--only <name>`) and `docs-check`.

For a language comparison, add a `python` path to the Mojo program's
manifest entry and include it with `python-example`. Keep one expected
`stdout` for the pair and run `docs-oracle-test` as well. Python examples
are downloaded alongside Mojo sources; the site build never executes either.

For an external consumer, set `working_directory` to `isolated`. The runner
copies the program's directory, including adjacent modules, outside the
checkout, builds and executes there, and sets `CVC5_MOJO_LIBRARY` explicitly.
It verifies that the checkout-relative library fallback is absent. Reuse
this mode instead of adding a separate consumer runner.

Executables have a default hard timeout of 30 seconds per process group;
`--run-timeout` changes it for a deliberate check. Compilation has its own
`--compile-timeout`. A timeout fails the example and terminates its children.
It must never be recorded as the solver's `unknown` result.
Interrupting or terminating the runner also stops all active process groups,
including those launched by its worker threads.

## Tutorial conventions

The [main course](../tutorials/index.md) assumes basic Mojo and introduces
SMT concepts in order. The [transcendental course](../tutorials/transcendentals/index.md)
builds on real arithmetic and counterexample queries. Keep each lesson
centered on a concrete problem, explain the encoding and result, and give
an exercise with a worked answer.

Prefer mathematical assertions to an arbitrary model ordering. For unique
small models, verify the exact answer independently. For multiple valid
models, check the requirements. Do not record the output of a failing or
inconclusive example as though it were a successful proof; an example
teaching `unknown` must explicitly assert and explain that result.

Use short inline notation for simple expressions and `math` fences for
longer display equations. Keep the runnable source as the only copy of
executable Mojo. An exercise may describe changes to a copy, but its output
must not be confused with the original tested output.

### Explain an excerpt

Mark a coherent step in the maintained program with comment lines:

```text
    # docs:begin constraint
    <the program's existing statements>
    # docs:end constraint
```

Include it with `excerpt: docs/examples/<program>.mojo#constraint`. Indentation
is removed from the excerpt for display. Introduce the step before the code
and explain its result afterward. Include the complete program elsewhere
on the page or in the same application sequence; use a Markdown-enabled
`details` element when the full listing would interrupt the walkthrough.

Markers are not line numbers, so nearby edits do not silently change the
selected code. The audit checks the markers even for a full example whose
regions are not currently included.

### Equations and diagrams

A display equation is written as a fenced block with language `math` and
TeX content, for example `\sin x \le 1`. The central renderer escapes that
content into a display element.
The page loads the bundled KaTeX distribution only when it has an equation;
rendering emits both visual HTML and MathML. Plain TeX remains visible
when JavaScript is disabled. Unsupported TeX fails the browser check.

Small diagrams live in `docs/content/assets/figures/` as SVG. Include
meaningful alternative text and a caption, and explain the assumptions
in surrounding prose. A schematic must not be presented as a numerical
certificate.

For changes to operator extraction or rendering, also run:

```sh
pixi run --locked -e docs python -m unittest discover -s tests -p 'test_*.py'
```

## Theme

The theme is the small custom MkDocs theme our projects share:

- **Templates.** Jinja templates for the page shell, navigation and search
  page.
- **Styles.** One stylesheet, `assets/site.css`.
- **Scripts.** Theme switching, mobile navigation, copy buttons and search.
- **No external requests.** Text and math fonts and KaTeX are bundled; search
  uses MkDocs' generated index with its bundled Lunr. The browser check blocks
  external requests so a hidden CDN dependency fails verification.

Keep URLs relative, so the site works under any path. Project-specific additions include equation rendering and checks for the
documentation workflows. Keep the common layout and relative-URL behavior.

The header shows the version from `pixi.toml` and links to its GitHub
release. The sidebar and footer name the Mojo series and the pinned cvc5
release. All are read at build time.

## Browser checks and math bundle

Building the site does not require Node or the network. Updating the math
bundle or running browser QA uses Node 24 and the exact npm dependencies
in `docs/qa/package-lock.json`:

```sh
npm ci --prefix docs/qa --ignore-scripts --no-audit --no-fund
python3 scripts/vendor_docs_math.py --check
docs/qa/node_modules/.bin/playwright install chromium
pixi run --locked -e docs docs-check
node docs/qa/check.mjs
```

On a clean Linux CI image, Playwright's `install --with-deps chromium` also
installs the browser's system dependencies. The browser check starts a
loopback HTTP server under the site's deployment prefix. It checks local
assets, equation rendering, search, narrow-screen overflow, theme persistence,
the skip link, and opening and closing mobile navigation with the keyboard.
Review its screenshots in `.cache/docs-browser/` as well as its exit status.
These are focused Chromium checks, not a complete cross-browser or
accessibility audit.

To update KaTeX, change the exact dependency in `docs/qa/package.json`,
refresh the lock with npm, then run `python3 scripts/vendor_docs_math.py`.
Review the bundled changes under `docs/theme/assets/katex/`, including the
license and fonts. `--check` compares every file against the installed pinned
distribution and rejects extras. Builds always use the committed bundle.
The upstream [KaTeX API](https://katex.org/docs/api) documents the renderer.

## Publishing

`.github/workflows/docs.yml` runs renderer unit tests, `docs-check`, bundle
verification, and browser checks on pull requests and pushes to `main`. It
deploys to GitHub Pages only when the repository is public, so the site
cannot be published while the project is private.
