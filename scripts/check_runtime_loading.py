"""Check isolated loading, partial initialization cleanup, and independent threads."""
import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import tempfile

from docs_contract import ROOT
from verify_docs_examples import precompile, run
from run_soak_tests import fingerprint
from run_matched_controls import libraries
from bindgen import c_headers, config, gen_raw


def classified(result, expected, tail):
    """Only normal, complete execution with the intended outcome can pass."""
    if result is None or result['returncode'] != 0:
        return False
    lines = result['stdout'].splitlines()
    suffix = tail.splitlines()
    if expected is None:
        return lines == suffix
    return (len(lines) == len(suffix) + 2 and lines[0] == 'load-error'
            and expected in lines[1] and lines[2:] == suffix)


def closed_before_checkpoint(lines, tags, attempts=None, owners=()):
    """A failed initialization must unload its test DSOs before main finishes."""
    if lines.count('checkpoint') != 1:
        return False
    index = lines.index('checkpoint')
    if index != len(lines) - 1:
        return False  # Process-exit cleanup must not conceal a live handle.
    counts = Counter(lines[:index])
    pairs = [('open ' + tag, 'close ' + tag) for tag in tags]
    pairs += [('create ' + owner, 'destroy ' + owner) for owner in owners]
    if set(counts) != {item for pair in pairs for item in pair}:
        return False
    for opened, closed in pairs:
        live = 0
        for line in lines[:index]:
            live += int(line == opened) - int(line == closed)
            if live < 0:
                return False
        if live or (attempts is not None and counts[opened] != attempts):
            return False
    return True


def build_fixtures(folder):
    snap = json.loads(config.SNAPSHOT_FILE.read_text())
    bound, _ = gen_raw.classify(snap)
    lib = config.BINARY_DIR / 'lib'
    records = []

    def build(directory, name, source, links=()):
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / (name + '.c')
        path.write_text(source)
        cmd = [config.c_compiler(), '-shared', '-fPIC', '-std=gnu11', '-Wall', '-Wextra', '-Werror',
               '-I', str(config.INCLUDE_DIR), '-I', 'tests/binding', str(path), *links,
               '-o', str(directory / name)]
        result = dict(command=cmd, **run(cmd, 120))
        records.append(result)
        if result['returncode']:
            raise RuntimeError(result['stderr'])

    def marker(tag):
        return f'#define TAG "{tag}"\n#include "loading.h"\n'

    missing = {}
    for label, library, last in [('missing-main-early', 'libcvc5.so', False),
                                 ('missing-main-late', 'libcvc5.so', True),
                                 ('missing-parser-symbol', 'libcvc5parser.so', True)]:
        names = [n for n, b in bound.items() if config.library_filename(b['library']) == library]
        omitted = names[-1 if last else 0]
        missing[label] = omitted
        for dll, tag in [('libcvc5.so', 'main'), ('libcvc5parser.so', 'parser')]:
            # Resolution-only fixtures: no fabricated API body may be executed.
            source = marker(tag) + '\n'.join(f'void {n}(void) {{ abort(); }}'
                     for n, b in bound.items() if config.library_filename(b['library']) == dll and n != omitted)
            build(folder / label, dll, source + '\n')
    # Opening the second DSO fails after the first one is already owned.
    build(folder / 'missing-parser-file', 'libcvc5.so', marker('main'))

    cls, method = snap['runtime']['version_method'].split('.')
    getter = snap['python'][cls]['methods'][method]['binding']['c'][0]
    declaration = snap['c_functions'][getter]
    params = ', '.join(p['type'] + ' ' + p['name'] for p in declaration['params'])
    unused = ''.join(f'(void){p["name"]}; ' for p in declaration['params'])
    owner_type = snap['python'][cls]['section']
    new, delete = c_headers.owner_lifecycle(snap['c_functions'], owner_type)
    parent_type = snap['c_functions'][new]['params'][0]['type'][:-1]
    parent_new, parent_delete = c_headers.owner_lifecycle(snap['c_functions'], parent_type)
    wrappers = ''
    for name, action, owner in [(parent_new, 'create', 'parent'), (new, 'create', 'owner'),
                                (delete, 'destroy', 'owner'), (parent_delete, 'destroy', 'parent')]:
        f = snap['c_functions'][name]
        params = ', '.join(p['type'] + ' ' + p['name'] for p in f['params']) or 'void'
        arguments = ', '.join(p['name'] for p in f['params'])
        call = f'original({arguments});'
        if f['returns'] != 'void':
            call = f'{f["returns"]} result = ' + call
        wrappers += (f'{f["returns"]} {name}({params}) {{\n'
                     f'  __typeof__(&{name}) original = (__typeof__(&{name}))dlsym(RTLD_NEXT, "{name}");\n'
                     f'  if (!original) abort();\n  {call}\n  event("{action} {owner}\\n");\n'
                     + ('  return result;\n' if f['returns'] != 'void' else '') + '}\n')
    for label, value in [('wrong-version', '"0.0-test"'), ('invalid-version-utf8', '"\\xff"')]:
        source = '#define _GNU_SOURCE\n' + marker('main') + '#include <cvc5/c/cvc5.h>\n#include <dlfcn.h>\n' + wrappers
        params = ', '.join(p['type'] + ' ' + p['name'] for p in declaration['params'])
        source += f'{declaration["returns"]} {getter}({params}) {{ {unused}return {value}; }}\n'
        build(folder / label, 'libcvc5.so', source,
              ['-Wl,--no-as-needed', str(lib / 'libcvc5.so'), '-Wl,-rpath,' + str(lib)])
        (folder / label / 'libcvc5parser.so').symlink_to(lib / 'libcvc5parser.so')
    # File selection including spaces/Unicode, and precedence over a bad prefix.
    installed = folder / 'prefix π space' / 'lib/cvc5_mojo/lib'
    installed.mkdir(parents=True)
    for name in ('libcvc5.so', 'libcvc5parser.so'):
        (installed / name).symlink_to(lib / name)
    incomplete = folder / 'incomplete-prefix' / 'lib/cvc5_mojo/lib'
    incomplete.mkdir(parents=True)
    (incomplete / 'libcvc5.so').symlink_to(lib / 'libcvc5.so')
    return missing, records


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', default='build/runtime-loading')
    parser.add_argument('--optimization', default='3', help='Comma-separated 0,3')
    parser.add_argument('--route', choices=('source', 'package', 'both'), default='both')
    parser.add_argument('--jobs', type=int, default=2)
    parser.add_argument('--repetitions', type=int, default=3, help='Fresh successful thread-start processes per build')
    parser.add_argument('--rounds', type=int, default=50, help='Error/recovery rounds per thread')
    args = parser.parse_args()
    levels = [int(x) for x in args.optimization.split(',')]
    if not levels or len(set(levels)) != len(levels) or any(x not in (0, 3) for x in levels) or min(args.jobs, args.repetitions, args.rounds) < 1:
        parser.error('invalid matrix, repetition, round, or job count')
    output = Path(args.output).resolve()
    output.mkdir(parents=True, exist_ok=True)
    folder = Path(tempfile.mkdtemp(prefix='run-', dir=output))
    fixtures = folder / 'fixtures'
    missing, builds = build_fixtures(fixtures)
    package, package_build = precompile(folder, 300)
    lib = config.BINARY_DIR / 'lib'
    explicit = lambda p: {'CVC5_MOJO_LIBRARY': str(p / 'libcvc5.so')}
    cases = [
        ('pinned', explicit(lib), None, []),
        ('checkout', {}, None, []),
        ('no-library', {}, 'not found; set', []),
        ('prefix', {'CONDA_PREFIX': str(fixtures / 'prefix π space')}, None, []),
        ('relative-explicit', {'CVC5_MOJO_LIBRARY': 'third_party/cvc5/lib/libcvc5.so'}, None, []),
        ('explicit-precedence', {**explicit(lib), 'CONDA_PREFIX': str(fixtures / 'incomplete-prefix')}, None, []),
        ('prefix-missing-parser', {'CONDA_PREFIX': str(fixtures / 'incomplete-prefix')}, 'not found beside libcvc5.so', []),
        ('bare-name', {'CVC5_MOJO_LIBRARY': 'libcvc5.so'}, 'must include the library directory', []),
        ('missing-library', explicit(fixtures / 'absent'), 'libcvc5.so', []),
        ('missing-parser-file', explicit(fixtures / 'missing-parser-file'), 'not found beside libcvc5.so', ['main']),
        ('wrong-version', explicit(fixtures / 'wrong-version'), 'expected cvc5', ['main']),
        ('invalid-version-utf8', explicit(fixtures / 'invalid-version-utf8'), 'UTF-8', ['main']),
        *[(label, explicit(fixtures / label), name, ['main', 'parser']) for label, name in missing.items()],
    ]
    paths = [*config.PACKAGE_DIR.rglob('*.mojo'), config.SNAPSHOT_FILE, ROOT / 'pixi.lock',
             ROOT / 'bindgen/gen_raw.py', config.APN_PACKAGE_DIR / 'apn_mojo.mojoc', Path(__file__).resolve(),
             ROOT / 'scripts/verify_docs_examples.py', ROOT / 'scripts/run_matched_controls.py',
             ROOT / 'tests/smoke/test_loading.mojo', ROOT / 'tests/smoke/test_threads.mojo',
             ROOT / 'tests/smoke/memory_support.mojo', ROOT / 'tests/binding/loading.h']
    paths += list((config.BINARY_DIR / 'lib').glob('libcvc5*.so')) + list(fixtures.rglob('*.c'))
    hashes = fingerprint(paths)
    routes = ('source', 'package') if args.route == 'both' else (args.route,)
    tasks = [(route, level, assertions) for route in routes for level in levels for assertions in (False, True)]

    def execute(task):
        route, level, assertions = task
        label = f'{route}-O{level}-' + ('assert' if assertions else 'release')
        compilations, records = {}, []
        for program in ('loading', 'threads'):
            binary = folder / f'{program}-{label}'
            cmd = ['mojo', 'build', '--Werror', f'-O{level}', *(['-D', 'ASSERT=all'] if assertions else []),
                   '-I', 'src' if route == 'source' else str(package),
                   f'tests/smoke/test_{program}.mojo', '-o', str(binary)]
            compiled = dict(command=cmd, **run(cmd, 600))
            compilations[program] = compiled
            if compiled['returncode']:
                print('BUILD FAIL', label, program, compiled['stderr'], flush=True)
                continue
            for name, additions, expected, tags in cases:
                # Ordinary loader cases use serial cached access. Instrumented
                # failures also use uncached CApi construction to check every unwind.
                modes = ['cache', 'direct'] if tags and program == 'loading' else ['cache']
                for mode in modes:
                    repetitions = args.repetitions if program == 'threads' and name == 'pinned' else 1
                    if program == 'threads' and expected is None and name != 'pinned':
                        continue
                    for repetition in range(repetitions):
                        stem = folder / f'{program}-{label}-{name}-{mode}-{repetition}'
                        events, maps = stem.with_suffix('.events'), stem.with_suffix('.maps')
                        env = os.environ.copy()
                        for key in ('CVC5_MOJO_LIBRARY', 'CONDA_PREFIX', 'CVC5_MOJO_TEST_EVENTS'):
                            env.pop(key, None)
                        env['LD_LIBRARY_PATH'] = str(lib)
                        env['CVC5_MOJO_TEST_EVENTS'] = str(events)
                        env.update(additions)
                        count = 20 if program == 'loading' and mode == 'direct' else 2 if program == 'loading' else args.rounds
                        arg = mode if program == 'loading' else 'failure' if expected else 'success'
                        cmd = [str(binary), arg, str(count), str(maps)]
                        cwd = folder if name in ('no-library', 'prefix') else ROOT
                        result = dict(command=cmd, cwd=str(cwd), **run(cmd, 120, env=env, cwd=cwd))
                        tail = (('loaded\n' if expected is None else '') + f'attempts {count}\n' if program == 'loading'
                                else f'threads passed: 16 of 16\nrounds {count}\nthread test passed\n')
                        passed = classified(result, expected, tail)
                        observed = events.read_text().splitlines() if events.exists() else []
                        owners = ('parent', 'owner') if name in ('wrong-version', 'invalid-version-utf8') else ()
                        cleanup = closed_before_checkpoint(observed, tags, count if mode == 'direct' else 1 if program == 'loading' else None, owners) if tags else None
                        mapped = libraries(maps) if expected is None else None
                        if cleanup is not None:
                            passed = passed and cleanup
                        if mapped is not None:
                            passed = passed and mapped['matched']
                        record = dict(case=name, program=program, mode=mode, repetition=repetition, passed=passed,
                                      expected_error=expected, run=result, cleanup=cleanup, events=observed, libraries=mapped)
                        records.append(record)
                        if not passed:
                            print('FAIL', label, json.dumps(record), flush=True)
        passed = len(compilations) == 2 and all(c['returncode'] == 0 for c in compilations.values()) and bool(records) and all(r['passed'] for r in records)
        print('PASS' if passed else 'FAIL', label, len(records), 'processes', flush=True)
        return dict(route=route, optimization=level, assertions=assertions, passed=passed, compile=compilations, records=records)

    with ThreadPoolExecutor(max_workers=args.jobs) as executor:
        records = list(executor.map(execute, tasks))
    passed = all(r['passed'] for r in records)
    report = dict(passed=passed, settings=vars(args), run_directory=str(folder), source_and_dependency_hashes=hashes,
                  fixture_builds=builds, package=package_build, records=records)
    (folder / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
    (output / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
    return int(not passed)


if __name__ == '__main__':
    raise SystemExit(main())
