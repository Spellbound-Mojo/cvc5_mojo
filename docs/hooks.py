"""Include the generated API reference, maintained examples and source downloads."""
from pathlib import Path
import re
import sys
import tomllib

from mkdocs.structure.files import File

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'scripts'))
from docs_contract import EXAMPLES, TRANSLATED, audit_docs, render_markdown


def on_config(config):
    # The released version, the supported Mojo series and the pinned cvc5
    # release come from pixi.toml and cvc5-version.toml; the theme shows them.
    pixi = tomllib.loads((ROOT / 'pixi.toml').read_text())
    mojo = re.match(r'[=<>~^ ]*(\d+\.\d+)', pixi['dependencies']['mojo'])
    config.extra['version'] = pixi['workspace']['version']
    config.extra['mojo'] = mojo[1]
    config.extra['cvc5'] = tomllib.loads((ROOT / 'cvc5-version.toml').read_text())['version']
    return config


def on_pre_build(config):
    audit_docs()


def on_files(files, config):
    # Theme assets are static files of the custom theme directory; MkDocs copies them.
    sources = (list((ROOT / 'src/cvc5_mojo').rglob('*.mojo'))
               + [p for p in EXAMPLES.rglob('*') if p.suffix in ('.mojo', '.py')]
               + list(TRANSLATED.glob('*.mojo')))
    for path in sorted(sources):
        files.append(File.generated(config, 'downloads/' + path.relative_to(ROOT).as_posix(), abs_src_path=str(path)))
    return files


def on_page_markdown(markdown, page, config, files):
    rendered = render_markdown(markdown, page.file.src_uri)
    page.meta['has_math'] = '<div class="math-display">' in rendered
    return rendered
