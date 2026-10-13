"""Reject new or stale generation omissions before writing build output."""


def check(actual, allowed, label):
    problems = [f"{label}: unexpected omission {name}: {actual[name]}" for name in sorted(actual.keys() - allowed.keys())]
    problems += [f"{label}: stale allowed omission {name}" for name in sorted(allowed.keys() - actual.keys())]
    problems += [f"{label}: missing reason for {name}" for name, reason in allowed.items() if not reason]
    if problems:
        raise SystemExit("generation policy failed:\n  " + "\n  ".join(problems))


def missing_methods(table):
    return {f"{cls}.{name}": reason for cls, methods in table.items()
            for name, (overloads, reason) in methods.items() if not overloads}
