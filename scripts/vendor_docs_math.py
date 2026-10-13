"""Copy the pinned KaTeX distribution from npm ci; builds never use the network."""
import argparse
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parent.parent


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true', help='Verify the bundle without writing')
    args = parser.parse_args()
    package = ROOT / 'docs/qa/node_modules/katex'
    pin = json.loads((ROOT / 'docs/qa/package.json').read_text())['devDependencies']['katex']
    assert json.loads((package / 'package.json').read_text())['version'] == pin, 'Run npm ci in docs/qa'
    destination = ROOT / 'docs/theme/assets/katex'
    files = {'LICENSE': package / 'LICENSE'}
    files.update({name: package / 'dist' / name for name in ('katex.min.js', 'katex.min.css')})
    files.update({f'fonts/{p.name}': p for p in (package / 'dist/fonts').iterdir() if p.is_file()})
    for name, source in files.items():
        target = destination / name
        if args.check:
            assert target.is_file() and target.read_bytes() == source.read_bytes(), f'Stale math asset: {target}'
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
    actual = {p.relative_to(destination).as_posix() for p in destination.rglob('*') if p.is_file()}
    assert actual == set(files), 'Unexpected files in math bundle; review before removing obsolete assets'
    print(f'KaTeX {pin}: {len(files)} bundled files verified')


if __name__ == '__main__':
    main()
