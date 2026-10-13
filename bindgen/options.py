"""Join option descriptions from pinned TOML with defaults from the pinned binary."""
import json
from pathlib import Path
import subprocess
import tempfile
import tomllib

from . import config


def declarations(source_dir=None):
    root = source_dir or config.SOURCE_DIR
    files = sorted((root / 'src/options').glob('*_options.toml'))
    assert files, 'Missing option declarations; run pixi run fetch'
    found = {}
    for path in files:
        module = tomllib.loads(path.read_text())
        for option in module.get('option', []):
            if not option.get('long'):
                continue
            name = option['long'].split('=', 1)[0]
            assert name not in found, f'Duplicate option: {name}'
            found[name] = {
                'module': module['name'], 'source': path.relative_to(root).as_posix(),
                'declaration': option,
            }
    return found


def runtime_info():
    """Compilation checks the extractor's use of the release's C metadata API."""
    with tempfile.TemporaryDirectory() as directory:
        binary = Path(directory) / 'options-info'
        library = config.BINARY_DIR / 'lib'
        subprocess.run([config.c_compiler(), '-std=c11', '-Wall', '-Wextra', '-Werror',
                        '-I', str(config.INCLUDE_DIR), str(Path(__file__).with_name('options_info.c')),
                        '-L', str(library), f'-Wl,-rpath,{library}', '-lcvc5', '-o', str(binary)],
                       check=True, capture_output=True, text=True, timeout=60)
        result = subprocess.run([str(binary)], check=True, capture_output=True, text=True, timeout=20)
    return json.loads(result.stdout)


def join(declared, records):
    found = {}
    for info in records:
        name = info['name']
        assert name in declared, f'API option has no source declaration: {name}'
        record = {**declared[name], **info}
        assert name not in found or found[name] == record, f'Conflicting option alias: {name}'
        found[name] = record
    assert found, 'No option information extracted'
    return dict(sorted(found.items()))


def extract():
    return join(declarations(), runtime_info())
