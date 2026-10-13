"""Build the binding-boundary regressions from source and package, with and without assertions."""
import argparse
from collections import Counter
from fractions import Fraction
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import re

from verify_docs_examples import precompile, run
from run_soak_tests import fingerprint
from run_matched_controls import libraries
from bindgen import config, gen_api
import binding_sequences
import owner_construction

PROGRAMS = ('strings', 'null_printing', 'formatting', 'integer_boundaries', 'numeric_conversions', 'collections', 'returned_collections', 'retention', 'ownership', 'ownership_construction', 'return_conversion', 'compound', 'sequences', 'plugins', 'oracles')


def build_native(name, level, folder, *, source=None, output_name=None, flags=(), link_flags=None):
    """Compile an independent native fixture against the cached headers/libraries."""
    lib = config.BINARY_DIR / 'lib'
    binary = folder / (output_name or f'{name}-c-O{level}')
    link = (['-L', str(lib), '-Wl,-rpath,' + str(lib), '-lcvc5']
            if link_flags is None else list(link_flags))
    command = [config.c_compiler(), '-std=gnu11', f'-O{level}', '-Wall', '-Wextra', '-Werror',
               *flags, '-I', str(config.INCLUDE_DIR), source or f'tests/binding/{name}.c',
               *link, '-o', str(binary)]
    return binary, dict(command=command, **run(command, 120))


def compound_equivalent(control, other):
    """Require completed native/Mojo runs and the exact semantic observations."""
    return (control is not None and other is not None
            and control['returncode'] == other['returncode'] == 0
            and len(control['stdout'].splitlines()) > 1
            and control['stdout'].endswith('compound FFI passed\n')
            and other['stdout'] == control['stdout'])


def ownership_accounting(lines, snapshot):
    """Check completed fixture sections release owners and query references.

    The trace records call attempts, not returned addresses. All constructors
    and result-producing calls in this fixture must succeed; expected errors
    occur in scalar getters or argument conversion. Other handle families and
    array elements are exercised semantically but not counted by this check.
    """
    model = gen_api.Model(snapshot)
    owners = {cls: model.lifecycle(cls) for cls in model.owners}
    result_type = model.classes['Result']['ctype']
    copy, release = model.lifecycle('Result')
    exports = [name for name, f in model.cf.items() if f['returns'] == result_type and name != copy]
    expected = ['borrowed', 'handles', 'exceptions', 'buffers', 'done']
    seen, sections, calls = [], {}, Counter()
    valid = True
    for line in lines:
        if line.startswith('ownership:'):
            if seen:
                sections[seen[-1]] = calls
            seen.append(line.removeprefix('ownership:'))
            calls = Counter()
        else:
            valid = valid and bool(seen) and line in model.cf
            calls[line] += 1
    records = {}
    for section, count in sections.items():
        pairs = {cls: dict(created=count[new], deleted=count[delete]) for cls, (new, delete) in owners.items()}
        results = dict(received=sum(count[name] for name in exports), copied=count[copy], released=count[release])
        passed = (sum(v['created'] for v in pairs.values()) > 0
                  and all(v['created'] == v['deleted'] for v in pairs.values())
                  and results['received'] + results['copied'] == results['released']
                  and (section == 'buffers' or results['received'] > 0))
        records[section] = dict(passed=passed, owners=pairs, results=results)
    return dict(passed=valid and seen == expected and not calls and all(r['passed'] for r in records.values()), sections=records)


def formatting_accounting(lines, snapshot):
    """All native formatters: once/write/constructor must call 1/1/2 times."""
    _, table = gen_api.generated(snapshot)
    expected = {cls: methods['__str__' if '__str__' in methods else '__repr__'][0][0]['cname']
                for cls, methods in table.items() if '__str__' in methods or '__repr__' in methods}
    records, phases = {}, {}
    current = phase = None
    valid, nulls = True, False
    for line in lines:
        if not line.startswith('formatting:'):
            if phase:
                phases[phase][line] += 1
            continue
        marker = line.removeprefix('formatting:')
        if marker in expected:
            valid = valid and current is None and marker not in records
            current, phase, phases = marker, None, {}
        elif marker in ('once', 'write', 'constructor'):
            order = ('once', 'write', 'constructor')
            valid = (valid and current in expected and len(phases) < 3
                     and marker == order[min(len(phases), 2)])
            phase = marker
            phases[phase] = Counter()
        elif marker == 'nulls':
            valid = valid and current is None and not nulls
            nulls, current, phase, phases = True, 'nulls', 'nulls', {'nulls': Counter()}
        elif marker == 'end':
            if current == 'nulls':
                valid = valid and not phases['nulls']
            elif current in expected:
                wanted = {p: {expected[current]: n} for p, n in zip(('once', 'write', 'constructor'), (1, 1, 2))}
                records[current] = dict(passed=phases == wanted, calls=phases)
                valid = valid and records[current]['passed']
            else:
                valid = False
            current = phase = None
        else:
            valid = False
    return dict(passed=valid and current is None and nulls and records.keys() == expected.keys(),
                formatters=records, nulls_checked=nulls)


def formatting_failure(result, fault):
    """Only the deliberately injected non-raising formatter abort may pass."""
    # Mojo 1.1 abort prints its diagnostic to stdout and emits SIGILL on Linux.
    # A bare signal, another crash, or an unrelated assertion is not evidence.
    message = ('Cannot construct a String from invalid UTF-8 data' if fault == 'utf8'
               else "cvc5: invalid argument '42'")
    return (result['returncode'] == -4 and result['stdout'].startswith('ABORT: ')
            and message in result['stdout']
            and 'formatting unexpectedly returned' not in result['stdout'] + result['stderr'])


def integer_literal_accounting(lines, snapshot):
    """Each declared literal must take its exact-range constructor once."""
    _, table = gen_api.generated(snapshot)
    constructors = {o['params'][0].mojo: o['cname']
                    for o in table['TermManager']['mkInteger'][0] if o.get('cname')}
    # The fixture owns the case inventory; Python independently decides range.
    fixture = (config.ROOT / 'tests/smoke/test_integer_boundaries.mojo').read_text()
    values = re.findall(r'check_literal\["(-?\d+)"\]', fixture)
    expected = {v: constructors['Int' if -(2**63) <= int(v) < 2**63 else 'String'] for v in values}
    records, calls = {}, Counter()
    state, current, valid = 'outside', None, bool(values) and len(values) == len(expected)
    for line in lines:
        if line == 'integer_literal:begin':
            valid = valid and state == 'outside'
            state, current, calls = 'value', None, Counter()
        elif line == 'integer_literal:end':
            valid = valid and state == 'calls' and current in expected
            if current in expected:
                matched = calls == {expected[current]: 1}
                records[current] = dict(passed=matched, calls=calls)
                valid = valid and matched
            state, current = 'outside', None
        elif line == 'integer_literal:done':
            valid = valid and state == 'outside'
            state = 'done'
        elif line.startswith('integer_literal:'):
            valid = False
        elif state == 'value':
            valid = valid and line in expected and line not in records
            current, state = line, 'calls'
        elif state == 'calls':
            calls[line] += 1
    return dict(passed=valid and state == 'done' and records.keys() == expected.keys(), cases=records)


def numeric_cases(snapshot):
    """Independently choose exact native routes from fixture values and C signatures."""
    model, table = gen_api.generated(snapshot)
    def ctor(method, types):
        return next(o['cname'] for o in table['TermManager'][method][0]
                    if o.get('cname') and [p.mojo for p in o['params']] == types)
    integer_native, integer_text = (ctor('mkInteger', [t]) for t in ('Int', 'String'))
    real_native, real_text = ctor('mkReal', ['Int', 'Int']), ctor('mkReal', ['String'])
    bv_native, bv_text = ctor('mkBitVector', ['Int', 'UInt64']), ctor('mkBitVector', ['Int', 'String', 'Int'])
    ints = snapshot['python']['Term']['methods']['getIntegerValue']['binding']['c']
    reals = snapshot['python']['Term']['methods']['getRealValue']['binding']['c']
    def scalar(functions, returns):
        return next(n for n in functions if model.cf[n]['returns'] == returns)
    signed, unsigned, integer_output = (scalar(ints, t) for t in ('int64_t', 'uint64_t', 'const char*'))
    # Native predicates are named beside their corresponding typed getter.
    signed_check, unsigned_check = (n.replace('_get_', '_is_') for n in (signed, unsigned))
    real_check, real_output, real_get = (scalar(reals, t) for t in ('bool', 'const char*', 'void'))
    assert signed_check in model.cf and unsigned_check in model.cf
    fit = lambda n: -(2**63) <= n < 2**63
    text = (config.ROOT / 'tests/smoke/test_numeric_conversions.mojo').read_text()
    cases = {}
    for value in re.findall(r'check_integer\["(-?\d+)"\]', text):
        n = int(value)
        get = [signed_check]
        if fit(n):
            get += [signed]
        else:
            get += [unsigned_check, unsigned if 0 <= n < 2**64 else integer_output]
        cases['integer', (value,)] = {'new': Counter([integer_native if fit(n) else integer_text]), 'get': Counter(get)}
    for num, den in re.findall(r'check_real\["(-?\d+)", "(\d+)"\]', text):
        n, d = int(num), int(den)
        value = Fraction(n, d)
        direct = fit(value.numerator) and fit(value.denominator)
        get = [real_check, real_get if fit(value.numerator) and value.denominator < 2**64 else real_output]
        cases['real', (num, den)] = {'pair': Counter([real_native if fit(n) and fit(d) else real_text]),
                                    'rational': Counter([real_native if direct else real_text]), 'get': Counter(get)}
    for width, value in re.findall(r'check_bv\[(\d+), "(-?\d+)"\]', text):
        n = int(value)
        direct = 0 <= n < 2**64 and n.bit_length() <= int(width)
        cases['bv', (value,)] = {'new': Counter([bv_native if direct else bv_text])}
    return cases


def numeric_accounting(lines, snapshot):
    """Require every declared case, ordered phases, and exactly the selected calls."""
    expected = numeric_cases(snapshot)
    observed = {}
    kind = phase = None
    values, phases = [], {}
    valid, done = True, False
    for line in lines:
        if line.startswith('numeric:'):
            marker = line.removeprefix('numeric:')
            if marker in ('integer', 'real', 'bv'):
                valid = valid and kind is None and not done
                kind, phase, values, phases = marker, None, [], {}
            elif marker in ('new', 'get', 'pair', 'rational'):
                key = (kind, tuple(values))
                order = list(expected.get(key, {}))
                valid = valid and len(phases) < len(order) and marker == (order[len(phases)] if len(phases) < len(order) else None)
                phase = marker
                phases[phase] = Counter()
            elif marker == 'end':
                key = (kind, tuple(values))
                valid = valid and key in expected and key not in observed and phases == expected.get(key)
                observed[key] = phases
                kind = phase = None
            elif marker == 'done':
                valid = valid and kind is None and not done
                done = True
            else:
                valid = False
        elif phase:
            phases[phase][line] += 1
        elif kind:
            values.append(line)
    return dict(passed=valid and done and kind is None and observed.keys() == expected.keys(),
                cases={kind + ':' + '/'.join(values): dict(passed=calls == expected.get((kind, values)), calls=calls)
                       for (kind, values), calls in observed.items()})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', default='build/contracts')
    parser.add_argument('--jobs', type=int, default=2)
    parser.add_argument('--only', help='Comma-separated substrings selecting contract fixtures')
    parser.add_argument('--optimization', default='3', help='Comma-separated optimization levels: 0,1,3')
    parser.add_argument('--sanitize', choices=('address',), help='Instrument Mojo; cached native libraries remain uninstrumented')
    parser.add_argument('--ownership-iterations', type=int, default=0,
                        help='Repeat borrowed-owner/exception graphs without tracing; zero enables semantic reference accounting')
    parser.add_argument('--conversion-iterations', type=int, default=0,
                        help='Repeat native return-conversion fault and recovery graphs after warmup')
    parser.add_argument('--sequence-seeds', default='0,1,42', help='Comma-separated seeds for stateful differential checks')
    parser.add_argument('--sequence-steps', type=int, default=128, help='Generated operations after mandatory boundary cases')
    parser.add_argument('--sequence-input', help='Replay a saved sequence instead of generating seeds')
    args = parser.parse_args()
    levels = [int(n) for n in args.optimization.split(',')]
    if not levels or len(set(levels)) != len(levels) or any(n not in (0, 1, 3) for n in levels):
        parser.error('optimization levels must be 0, 1 or 3 without duplicates')
    if args.sanitize and levels != [1]:
        parser.error('use --optimization 1 with the pinned Mojo AddressSanitizer')
    if min(args.ownership_iterations, args.conversion_iterations, args.sequence_steps) < 0:
        parser.error('iteration counts must be nonnegative')
    seeds = [int(seed, 0) for seed in args.sequence_seeds.split(',')]
    if len(set(seeds)) != len(seeds):
        parser.error('sequence seeds must be unique')
    folder = Path(args.output).resolve()
    folder.mkdir(parents=True, exist_ok=True)
    package, built = precompile(folder, 300)
    filters = args.only.split(',') if args.only else []
    tasks = [(name, route, assertions, level) for name in PROGRAMS if not filters or any(word in name for word in filters)
             for route in ('source', 'package') for assertions in (False, True) for level in levels]
    if not tasks:
        raise SystemExit('No matching contract tests')
    controls = {}
    if any(name == 'compound' for name, *_ in tasks):
        for level in levels:
            binary, compiled = build_native('compound', level, folder)
            maps = folder / f'compound-c-O{level}'
            command = [str(binary), str(maps)]
            executed = dict(command=command, **run(command, 120)) if compiled['returncode'] == 0 else None
            loaded = libraries(Path(str(maps) + '.maps'))
            controls[level] = dict(compile=compiled, run=executed, libraries=loaded)
            (folder / f'compound-c-O{level}.json').write_text(json.dumps(controls[level], indent=2) + '\n')
            if not compound_equivalent(executed, executed) or not loaded['matched']:
                raise SystemExit('Native compound control failed: ' + json.dumps(controls[level]))
    sequence_controls, sequences = {}, []
    if any(name == 'sequences' for name, *_ in tasks):
        sequences = binding_sequences.corpus(folder / 'sequence-inputs', seeds, args.sequence_steps, args.sequence_input)
        for level in levels:
            binary, compiled = build_native('sequences', level, folder)
            if compiled['returncode']:
                raise SystemExit(compiled['stderr'])
            cases = {}
            for case in sequences:
                stem = folder / f'sequences-c-O{level}-{case["name"]}'
                cases[case['name']] = binding_sequences.execute(binary, None, case, stem)
            sequence_controls[level] = dict(compile=compiled, cases=cases)
            (folder / f'sequences-c-O{level}.json').write_text(json.dumps(sequence_controls[level], indent=2) + '\n')
            if not all(case['passed'] for case in cases.values()):
                raise SystemExit('Native sequence control disagrees with the model; see ' + str(folder / f'sequences-c-O{level}.json'))
    shim, shim_build = folder / 'return-faults.so', None
    if any(name == 'return_conversion' for name, *_ in tasks):
        command = [config.c_compiler(), '-shared', '-fPIC', '-std=gnu11', '-O2', '-Wall', '-Wextra', '-Werror',
                   '-I', str(config.INCLUDE_DIR), 'tests/binding/return_faults.c', '-ldl', '-o', str(shim)]
        shim_build = dict(command=command, **run(command, 120))
        (folder / 'shim-build.json').write_text(json.dumps(shim_build, indent=2) + '\n')
        if shim_build['returncode'] != 0:
            raise SystemExit(shim_build['stderr'])
    format_shim = folder / 'format-faults.so'
    if any(name == 'formatting' for name, *_ in tasks):
        _, compiled = build_native('format_faults', 3, folder, output_name=format_shim.name,
                                    flags=['-shared', '-fPIC'])
        (folder / 'format-shim-build.json').write_text(json.dumps(compiled, indent=2) + '\n')
        if compiled['returncode']:
            raise SystemExit(compiled['stderr'])
    owner_shim = folder / 'owner-faults.so'
    if any(name == 'ownership_construction' for name, *_ in tasks):
        source = owner_construction.generate(folder)
        _, compiled = build_native('owner_faults', 3, folder, source=str(source), output_name=owner_shim.name,
                                    flags=['-shared', '-fPIC'], link_flags=['-ldl'])
        (folder / 'owner-shim-build.json').write_text(json.dumps(compiled, indent=2) + '\n')
        if compiled['returncode']:
            raise SystemExit(compiled['stderr'])
    paths = [*config.PACKAGE_DIR.rglob('*.mojo'), config.SNAPSHOT_FILE, config.ROOT / 'bindgen/gen_api.py',
             config.ROOT / 'pixi.lock', Path(__file__).resolve()]
    paths += [config.ROOT / 'scripts/owner_construction.py']
    paths += [config.ROOT / f'tests/smoke/test_{name}.mojo' for name in PROGRAMS]
    paths += [config.ROOT / 'tests/binding/return_faults.c', config.ROOT / 'tests/binding/format_faults.c',
              config.APN_PACKAGE_DIR / 'apn_mojo.mojoc']
    paths += [config.ROOT / 'tests/binding/compound.c', config.ROOT / 'tests/binding/support.h',
              config.ROOT / 'tests/smoke/memory_support.mojo', config.ROOT / 'scripts/run_matched_controls.py']
    paths += [config.ROOT / 'tests/binding/sequences.c', config.ROOT / 'scripts/binding_sequences.py',
              config.ROOT / 'scripts/verify_docs_examples.py']
    paths += list((folder / 'sequence-inputs').glob('*'))
    paths += list((config.BINARY_DIR / 'lib').glob('libcvc5*.so'))
    hashes = fingerprint(paths)

    def execute(task):
        name, route, assertions, level = task
        label = f'{name}-{route}-' + ('assert' if assertions else 'release') + f'-O{level}'
        binary = folder / label
        flags = ['-D', 'ASSERT=all'] if assertions else []
        source = f'tests/smoke/test_{name}.mojo'
        if args.sanitize:
            flags += ['--sanitize', args.sanitize, '-g1']
            # Scan after fixture locals and shims have unwound, while process
            # globals (including CApi) still exist. Native DSO shutdown has a
            # separate direct-C diagnostic; unloading loses its stack symbols.
            driver = folder / (label + '-driver.mojo')
            driver.write_text(f'from test_{name} import main as run_fixture\n'
                              'from std.ffi import external_call\n'
                              'def main() raises:\n'
                              '    run_fixture()\n'
                              '    external_call["__lsan_do_leak_check", NoneType]()\n')
            flags += ['-I', 'tests/smoke']
            source = str(driver)
        if name == 'ownership_construction':
            flags += ['-I', str(folder)]
        trace = folder / (label + '.calls')
        traced = name in ('formatting', 'integer_boundaries', 'numeric_conversions') or (name == 'ownership' and args.ownership_iterations == 0)
        if traced:
            trace.unlink(missing_ok=True)
            flags += ['-D', 'CVC5_MOJO_TRACE=' + str(trace)]
        compiled = run(['mojo', 'build', '--Werror', f'-O{level}', *flags,
                        '-I', 'src' if route == 'source' else str(package),
                        source, '-o', str(binary)], 600)
        arguments = [str(args.ownership_iterations)] if name == 'ownership' and args.ownership_iterations else []
        if name == 'return_conversion':
            arguments = [str(shim), '0', str(args.conversion_iterations)]
        if name == 'ownership_construction':
            arguments = [str(owner_shim)]
        comparisons = None
        if name == 'sequences' and compiled['returncode'] == 0:
            comparisons = {}
            for layer in ('raw', 'public'):
                for case in sequences:
                    key = f'{layer}-{case["name"]}'
                    comparisons[key] = binding_sequences.execute(binary, layer, case, folder / (label + '-' + key),
                                                                 sequence_controls[level]['cases'][case['name']])
            executed = list(comparisons.values())[-1]['run']
        elif name == 'compound' and compiled['returncode'] == 0:
            comparisons = {}
            for layer in ('raw', 'public'):
                maps = folder / (label + '-' + layer)
                command = [str(binary), layer, str(maps)]
                result = dict(command=command, **run(command, 180))
                loaded = libraries(Path(str(maps) + '.maps'))
                comparisons[layer] = dict(run=result, libraries=loaded,
                                          passed=compound_equivalent(controls[level]['run'], result) and loaded['matched'])
            executed = comparisons['public']['run']
        else:
            executed = run([str(binary), *arguments], 180) if compiled['returncode'] == 0 else None
        passed = executed is not None and executed['returncode'] == 0
        if name == 'null_printing' and executed is not None:
            # Sort comparisons must not leak native debugging prints to stdout.
            passed = passed and executed['stdout'] == 'null formatting test passed\n'
        if comparisons is not None:
            passed = passed and all(r['passed'] for r in comparisons.values())
        accounting = None
        if traced:
            account = {'formatting': formatting_accounting, 'integer_boundaries': integer_literal_accounting,
                       'numeric_conversions': numeric_accounting, 'ownership': ownership_accounting}[name]
            accounting = account(trace.read_text().splitlines() if trace.exists() else [],
                                 json.loads(config.SNAPSHOT_FILE.read_text()))
            passed = passed and accounting['passed']
        failures = {}
        if name == 'formatting' and compiled['returncode'] == 0:
            if trace.exists():
                trace.rename(folder / (label + '-success.calls'))
            for fault in ('native', 'utf8'):
                for format_route in ('once', 'write', 'constructor'):
                    command = [str(binary), str(format_shim), fault, format_route]
                    result = dict(command=command, **run(command, 60))
                    key = fault + '-' + format_route
                    failures[key] = dict(passed=formatting_failure(result, fault), run=result)
                    if trace.exists():
                        trace.rename(folder / (label + '-' + key + '.calls'))
            passed = passed and all(r['passed'] for r in failures.values())
        print('PASS' if passed else 'FAIL', label, flush=True)
        if not passed:
            print((executed or compiled)['stderr'], flush=True)
            if accounting is not None:
                print(json.dumps(accounting), flush=True)
            if comparisons is not None:
                print(json.dumps(comparisons), flush=True)
            if failures:
                print(json.dumps(failures), flush=True)
        return dict(name=name, route=route, assertions=assertions, optimization=level,
                    sanitizer=args.sanitize,
                    leak_checkpoint='after fixture cleanup, before process globals teardown' if args.sanitize else None,
                    ownership_iterations=args.ownership_iterations if name == 'ownership' else None,
                    conversion_iterations=args.conversion_iterations if name == 'return_conversion' else None,
                    passed=passed, compile=compiled, run=executed, accounting=accounting,
                    comparisons=comparisons, formatting_failures=failures)

    with ThreadPoolExecutor(max_workers=args.jobs) as executor:
        records = list(executor.map(execute, tasks))
    passed = all(r['passed'] for r in records)
    (folder / 'report.json').write_text(json.dumps(dict(passed=passed, package=built, shim=shim_build, native_controls=controls,
                                                     sequence_controls=sequence_controls,
                                                     sequence_settings=dict(seeds=seeds, steps=args.sequence_steps, replay=args.sequence_input),
                                                     source_and_dependency_hashes=hashes, records=records), indent=2) + '\n')
    return int(not passed)


if __name__ == '__main__':
    raise SystemExit(main())
