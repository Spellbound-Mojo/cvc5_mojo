"""Build and run cvc5's Python unit tests and examples, translated to Mojo by bindgen.translate.

Every file in tests/cvc5/ is built against the precompiled package and
the installed apn_mojo dependency, run from the repository root, and must
pass. Translated examples match the official Python output recorded by
bindgen.oracle and its exit status. Explicit model policies validate the
model in the executable and compare all non-model output exactly.
Each test that the [tests] table of
bindgen/overrides.toml leaves out is translated into a module of its own,
and each example that [examples] leaves out is built too; each must reproduce
its documented failure, and crashes/timeouts always fail. If one passes, its
entry is stale, as is one that bindgen.translate reports stale
(tests/cvc5/translation.json).

Every program is built with `-D CVC5_MOJO_TRACE=<file>`, so the raw layer
records each C function it calls (`ffi.trace`). A full run writes the C
functions the passing tests and examples call to tests/cvc5/calls.json,
which the coverage report renders; CI requires the committed file to match.
A JSON report is written to the output directory.
Use --test MODULE.TEST for individual tests; --update-calls extends the
same-release trace inventory after a successful targeted run.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
import difflib
import json
import re
from pathlib import Path

from docs_contract import ROOT
from verify_docs_examples import precompile, run
from bindgen import config, report as coverage, translate


def comparable_output(text, patterns):
    """Normalize only the model fields discovered in the source, in order.

    Model assertions are checked in the executable. Missing, reordered or extra
    output still fails comparison; a blanket line-prefix filter would hide it.
    """
    lines = text.splitlines(keepends=True)
    start = 0
    for pattern in patterns:
        for i in range(start, len(lines)):
            match = re.fullmatch(pattern, lines[i].removesuffix('\n'))
            if match:
                line = lines[i]
                for group in reversed(range(1, len(match.groups()) + 1)):
                    a, b = match.span(group)
                    line = line[:a] + '<checked model value>' + line[b:]
                lines[i], start = line, i + 1
                break
        else:
            raise ValueError('missing model output matching ' + pattern)
    return ''.join(lines)


def record_calls(records, version, *, extend=False, reachable=None):
    """Record successful traces; targeted runs may extend a same-release baseline.

    A targeted run preserves old observations except functions with no public
    call site left in the generated binding. Only a full run removes other
    old observations. Every selected test must pass before recording calls.
    """
    calls = set().union(*(set(r['calls']) for r in records if r['passed'] and not r['kind'].startswith('left-out')))
    if reachable is not None and not calls <= reachable:
        raise ValueError('trace contains calls absent from the public inventory: ' + str(sorted(calls - reachable)))
    if extend:
        baseline = json.loads(config.CALLS_FILE.read_text())
        if baseline['cvc5'] != version:
            raise ValueError('cannot extend C-call coverage from another cvc5 release')
        calls.update(baseline['calls'])
        if reachable is not None:
            calls.intersection_update(reachable)
    config.CALLS_FILE.write_text(json.dumps(dict(cvc5=version, calls=sorted(calls)), indent=1) + '\n')
    return len(calls)


def expected_failure(spec, compiled, executed, why):
    """Only the documented failure counts; crashes and timeouts never do."""
    code = compiled['returncode']
    if code is None or code < 0:
        return False
    if spec['phase'] == 'compile':
        return code > 0 and spec['match'] in compiled['stderr']
    if code != 0 or executed is None:
        return False
    code = executed['returncode']
    if code is None or code < 0:
        return False
    if spec['phase'] == 'run':
        return code > 0 and spec['match'] in executed['stdout'] + executed['stderr']
    return spec['phase'] == 'output' and code == 0 and why.startswith('output differs:')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', default=str(ROOT / 'build' / 'cvc5-tests'), help='The report directory')
    parser.add_argument('--only', help='Run only test files whose name contains this text')
    parser.add_argument('--test', action='append', default=[], metavar='MODULE.TEST',
                        help='Translate and run just this test and its compile-fail blocks; repeatable')
    parser.add_argument('--update-calls', action='store_true',
                        help='Extend the committed C-call coverage with a successful targeted run')
    parser.add_argument('--compile-timeout', type=int, default=600, help='Seconds per compilation')
    parser.add_argument('--run-timeout', type=int, default=900, help='Seconds per test program')
    parser.add_argument('--jobs', type=int, default=2, help='Concurrent compilations')
    args = parser.parse_args()
    folder = Path(args.output).resolve()
    (folder / 'bin').mkdir(parents=True, exist_ok=True)
    (folder / 'left_out').mkdir(exist_ok=True)
    (folder / 'trace').mkdir(exist_ok=True)
    package, built = precompile(folder, args.compile_timeout)

    translation = json.loads(config.TRANSLATION_FILE.read_text())
    comparisons = {translate.example_name(Path(name)): entry.get('model_output', [])
                   for name, entry in translation['examples'].items()}
    status = json.loads((config.CVC5_EXAMPLES_DIR / 'status.json').read_text())
    exclusions = config.overrides()['tests']
    tasks = [('tests', p.stem, p) for p in sorted(config.CVC5_TESTS_DIR.glob('test_*.mojo'))]
    tasks += [('compile-fail', name, config.CVC5_TESTS_DIR / 'compile_fail' / f'{name}.mojo')
              for name in translation['compile_fail']]
    api = translate.Api(json.loads(config.SNAPSHOT_FILE.read_text()))
    for stem, tests in translate.left_out_tests().items():
        for name in tests:
            source = config.SOURCE_DIR / translate.TEST_DIR / f'{stem}.py'
            path = folder / 'left_out' / f'{stem}__{name}.mojo'
            path.write_text(translate.translate_file(source, api, only=name)['text'])
            tasks.append(('left-out test', f'{stem}.{name}', path))
    for file, entry in translation['examples'].items():
        name = translate.example_name(Path(file))
        kind = 'example' if 'run' in entry else 'left-out example' if 'left_out' in entry else None
        if kind:
            tasks.append((kind, name, config.CVC5_EXAMPLES_DIR / f'{name}.mojo'))
    if args.test:
        tasks = [t for t in tasks if t[0] == 'compile-fail' and any(
            t[1].startswith(selector.replace('.', '__') + '__') for selector in args.test)]
        for selector in args.test:
            stem, sep, name = selector.partition('.')
            if not sep or f'{stem}.py' not in translation['files']:
                parser.error(f'unknown test: {selector}')
            entry = translate.translate_file(config.SOURCE_DIR / translate.TEST_DIR / f'{stem}.py', api, only=name)
            if entry['run'] != [name]:
                parser.error(f'{selector}: {entry["not_translated"] or "no such test"}')
            path = folder / 'left_out' / f'{stem}__{name}.mojo'
            path.write_text(entry['text'])
            tasks.append(('left-out test' if selector in exclusions else 'selected test', selector, path))
    tasks = [t for t in tasks if not args.only or args.only in t[1]]
    assert tasks, 'No matching tests'

    def outcome(kind, name, executed):
        """(passed, why not)."""
        if executed is None:
            return False, 'does not compile'
        if kind in ('tests', 'left-out test', 'selected test'):
            return executed['returncode'] == 0, f'exit {executed["returncode"]}'
        if executed['returncode'] != status[name]:
            return False, f'exit {executed["returncode"]}; Python exited {status[name]}'
        expected = (config.CVC5_EXAMPLES_DIR / f'{name}.out').read_text()
        actual = executed['stdout']
        try:
            expected, actual = [comparable_output(text, comparisons.get(name, [])) for text in (expected, actual)]
        except ValueError as error:
            return False, str(error)
        if actual != expected:
            diff = difflib.unified_diff(expected.splitlines(), actual.splitlines(),
                                        'Python', 'Mojo', lineterm='')
            return False, 'output differs:\n' + '\n'.join(list(diff)[:40])
        return True, ''

    def execute(task):
        kind, name, path = task
        binary = folder / 'bin' / (path.stem if kind != 'example' and kind != 'left-out example' else f'example_{name}')
        trace = folder / 'trace' / f'{binary.name}.txt'
        trace.unlink(missing_ok=True)
        build = ['mojo', 'build', '-D', f'CVC5_MOJO_TRACE={trace}', '-I', str(package), str(path),
                 '-o', str(binary)]
        compiled = run(build, args.compile_timeout)
        executed = run([str(binary)], args.run_timeout) if compiled['returncode'] == 0 and kind != 'compile-fail' else None
        passed, why = outcome(kind, name, executed)
        expected = None
        if kind == 'compile-fail':
            line = translation['compile_fail'][name]['line']
            passed = expected_failure(dict(phase='compile', match=f'{path.name}:{line}:'), compiled, None, why)
            why = '' if passed else 'expected a compiler diagnostic at the argument-rejection block'
        elif kind.startswith('left-out'):
            spec = exclusions[name] if kind == 'left-out test' else dict(phase='output')
            expected = not passed and expected_failure(spec, compiled, executed, why)
        if expected is not None:
            print('STALE' if passed else 'expected failure:' if expected else 'UNEXPECTED FAILURE:', kind, name, flush=True)
            if not passed and not expected:
                print(why, (executed or compiled)['stderr'], flush=True)
        else:
            print('PASS' if passed else 'FAIL', kind, name, flush=True)
            if not passed:
                print(why, flush=True)
                print((executed or compiled)['stderr'][-2000:], flush=True)
        called = sorted(set(trace.read_text().split())) if passed and trace.exists() else []
        return dict(kind=kind, name=name, passed=passed, expected_failure=expected, why=why,
                    compile=compiled, run=executed, calls=called)

    with ThreadPoolExecutor(max_workers=args.jobs) as executor:
        records = list(executor.map(execute, tasks))
    failed = [r['name'] for r in records if not r['passed'] and not r['expected_failure']]
    stale = [f'overrides.toml [tests] "{r["name"]}" is stale: the test passes; delete the entry'
             for r in records if r['kind'] == 'left-out test' and r['passed']]
    stale += [f'overrides.toml [examples] "{r["name"]}" is stale: it prints what Python prints; delete the entry'
              for r in records if r['kind'] == 'left-out example' and r['passed']]
    stale += translation['stale']
    (folder / 'report.json').write_text(json.dumps(dict(failed=failed, stale=stale, package=built, records=records),
                                                   indent=2))
    for problem in stale:
        print(problem, flush=True)
    targeted = bool(args.only or args.test)
    if (args.update_calls or not targeted) and not failed and not stale:
        calls = record_calls(records, translation['cvc5'], extend=targeted,
                             reachable=coverage.public_c_functions(json.loads(config.SNAPSHOT_FILE.read_text())))
        print(f'wrote {config.CALLS_FILE.relative_to(ROOT)}: {calls} C functions called', flush=True)
    if failed or stale:
        print('FAILED', flush=True)
        return 1
    count = lambda kind: sum(r['kind'] == kind for r in records)
    tests = sum(len(translation['files'][f'{r["name"]}.py']['run']) for r in records if r['kind'] == 'tests')
    tests += count('selected test')
    print(f'TRANSLATED CVC5 TESTS PASS: {tests} tests ({count("tests")} complete modules, '
          f'{count("selected test")} individually selected); {count("example")} examples '
          f'match their comparison policy; {count("compile-fail")} compile-fail blocks checked; '
          f'{count("left-out test") + count("left-out example")} documented failures reproduced',
          flush=True)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
