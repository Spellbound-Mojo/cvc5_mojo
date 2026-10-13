"""Replayable binding operation streams and an independent exact-arithmetic model."""
from fractions import Fraction
from pathlib import Path
import random

from verify_docs_examples import run
from run_matched_controls import libraries

SLOTS = 8
MARKER = 'sequence passed'
WIDTHS = (1, 2, 7, 8, 31, 32, 63, 64, 65, 127, 128, 256, 257)
BOUNDARIES = tuple(sorted({0, 1, -1, *(sign * (2**width + delta)
    for width in (31, 32, 63, 64, 127, 256) for sign in (-1, 1) for delta in (-1, 0, 1))}))


def generate(seed, steps):
    rng = random.Random(seed)
    ops = []
    for i, value in enumerate(BOUNDARIES):
        forms = (0, 1, 2) if -(2**63) <= value < 2**63 else (0, 1)
        for form in forms:
            ops.append(('I', i % SLOTS, value, form))
    for width in WIDTHS:
        for value in (0, -(2**(width - 1)), 2**width - 1):
            for form in (0, 1):
                ops.append(('B', width, 10, str(value), form))
        for base in (2, 16):
            ops.append(('B', width, base, format(2**width - 1, 'b' if base == 2 else 'x'), 0))
    for i in range(6):
        for n, d in ((0, 3), (-6, 3), (2**64 + 1, 2**64 - 1), (-2**127, 2**128 - 1)):
            ops.append(('Q', n, d, i))
    ops += [('V', SLOTS, *range(SLOTS))]
    for kind in range(6):
        ops += [('E', kind, kind, 65, 2**65), ('C', kind, kind), ('G',)]
    ops += [('R',), ('G',), ('P', 0, 0), ('P', 0, 1), ('V', 0), ('G',)]
    for _ in range(steps):
        kind = rng.choice('IICCAAQBBVVGGREPP')
        a, b, c = (rng.randrange(SLOTS) for _ in range(3))
        if kind == 'I':
            value = rng.choice(BOUNDARIES) if rng.randrange(2) else rng.randrange(-2**257, 2**257)
            form = rng.randrange(3 if -(2**63) <= value < 2**63 else 2)
            ops.append((kind, a, value, form))
        elif kind == 'C':
            ops.append((kind, a, b))
        elif kind == 'A':
            ops.append((kind, a, b, c, rng.randrange(2)))
        elif kind == 'Q':
            ops.append((kind, rng.choice(BOUNDARIES), rng.choice((1, 3, 17, 2**32-1, 2**64+1)), rng.randrange(6)))
        elif kind == 'B':
            width = rng.choice(WIDTHS)
            base = rng.choice((2, 10, 16))
            value = rng.randrange(-2**(width-1) if base == 10 else 0, 2**width)
            text = str(value) if base == 10 else format(value, 'b' if base == 2 else 'x')
            ops.append((kind, width, base, text, rng.randrange(2) if base == 10 else 0))
        elif kind == 'V':
            size = rng.choice((0, 1, 2, 7, 8, 17, 31))
            ops.append((kind, size, *(rng.randrange(SLOTS) for _ in range(size))))
        elif kind == 'E':
            width = rng.choice(WIDTHS)
            ops.append((kind, rng.randrange(6), a, width, 2**width))
        elif kind == 'P':
            ops.append((kind, a, b))
        else:
            ops.append((kind,))
    return ops


def encode(operations):
    return ''.join(' '.join(map(str, op)) + '\n' for op in operations)


def read(path):
    return [tuple(line.split()) for line in Path(path).read_text().splitlines() if line]


def expected(operations):
    slots, saved, out = [0] * SLOTS, [], []
    for step, row in enumerate(operations):
        op, *args = map(str, row)
        if op == 'I':
            a, value, form = map(int, args)
            slots[a] = value
            value = str(value)
        elif op == 'C':
            a, b = map(int, args)
            slots[a] = slots[b]
            value = str(slots[a])
        elif op == 'A':
            a, b, c, minus = map(int, args)
            slots[a] = slots[b] - slots[c] if minus else slots[b] + slots[c]
            value = str(slots[a])
        elif op == 'Q':
            n, d, form = map(int, args)
            rational = Fraction(n, d)
            value = f'{rational.numerator}/{rational.denominator}'
        elif op == 'B':
            width, base, text, form = args
            value = str(int(text, int(base)) % 2**int(width))
        elif op in ('V', 'G'):
            if op == 'V':
                size, *indices = map(int, args)
                assert len(indices) == size
                saved = [slots[i] for i in indices]
            value = '[' + ','.join(map(str, saved)) + ']'
        elif op == 'R':
            value = 'reset'
        elif op == 'E':
            kind, a, width, overflow = map(int, args)
            value = 'recovered ' + str(slots[a])
        elif op == 'P':
            a, b = map(int, args)
            value = str(int(slots[a] == slots[b]))
        else:
            raise ValueError('Unknown operation: ' + op)
        out.append(f'{step} {op} {value}')
    return '\n'.join([*out, MARKER, ''])


def failure(result, operations):
    """Retain failure category/opcode while shrinking; never accept a crash as success."""
    if result is None:
        return ('missing-run',)
    if result['returncode'] is None:
        return ('timeout',)
    if result['returncode'] != 0:
        return ('exit', result['returncode'])
    wanted_text = expected(operations)
    if result['stdout'] == wanted_text:
        return None
    wanted, actual = wanted_text.splitlines(), result['stdout'].splitlines()
    for i, line in enumerate(wanted):
        if i >= len(actual) or actual[i] != line:
            return ('output', str(operations[i][0]) if i < len(operations) else 'completion')
    return ('output', 'trailing')


def minimize(operations, predicate, budget=80):
    """Delete chunks, preserving the predicate; every subsequence is valid from zero slots."""
    current, calls, parts = list(operations), 0, 2
    while current and calls < budget:
        size = max(1, (len(current) + parts - 1) // parts)
        changed = False
        for start in range(0, len(current), size):
            candidate = current[:start] + current[start + size:]
            calls += 1
            if predicate(candidate):
                current, parts, changed = candidate, max(2, parts - 1), True
                break
            if calls >= budget:
                break
        if not changed:
            if parts >= len(current):
                break
            parts = min(len(current), parts * 2)
    return current, calls


def corpus(folder, seeds, steps, replay=None):
    """Persist exact inputs and model observations, including an external replay."""
    folder.mkdir(parents=True, exist_ok=True)
    cases = []
    inputs = [('replay', read(replay))] if replay else [(f'seed-{seed}', generate(seed, steps)) for seed in seeds]
    for name, operations in inputs:
        path = folder / (name + '.txt')
        path.write_text(encode(operations))
        (folder / (name + '.expected')).write_text(expected(operations))
        cases.append(dict(name=name, path=path, operations=operations))
    return cases


def execute(binary, layer, case, stem, control=None):
    """Execute a stream, check the independent model and C, and reduce failures."""
    import json

    def command(path, maps):
        return [str(binary), *([layer] if layer else []), str(path), str(maps)]

    maps = Path(str(stem) + '.maps')
    maps.unlink(missing_ok=True)
    cmd = command(case['path'], stem)
    result = dict(command=cmd, **run(cmd, 120))
    issue = failure(result, case['operations'])
    loaded = libraries(maps)
    matches_c = control is None or result['stdout'] == control['run']['stdout']
    reduction = None
    if issue is not None and issue != ('timeout',):
        candidate_path = Path(str(stem) + '.candidate.txt')
        def preserves(candidate):
            candidate_path.write_text(encode(candidate))
            return failure(run(command(candidate_path, stem), 15), candidate) == issue
        reduced, calls = minimize(case['operations'], preserves)
        path = Path(str(stem) + '.minimized.txt')
        path.write_text(encode(reduced))
        Path(str(stem) + '.minimized.expected').write_text(expected(reduced))
        replay = dict(command=command(path, stem), **run(command(path, stem), 15))
        reduction = dict(input=str(path), operations=len(reduced), probes=calls,
                         preserved=failure(replay, reduced) == issue, replay=replay)
    record = dict(passed=issue is None and loaded['matched'] and matches_c,
                  input=str(case['path']), operations=len(case['operations']),
                  failure=issue, libraries=loaded, matches_c=matches_c, run=result, reduction=reduction)
    Path(str(stem) + '.json').write_text(json.dumps(record, indent=2) + '\n')
    return record
