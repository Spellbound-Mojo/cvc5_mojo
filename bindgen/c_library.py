"""Find the shared library of the release that exports each C API function.

The C API is split across libraries: the parser functions (`cvc5_parser_*`,
`cvc5_sm_*`, `cvc5_cmd_*`) live in libcvc5parser, the rest in libcvc5. The
raw layer loads each library and resolves every function from its own.

LLVM reads exported symbols and native dependencies without executing foreign
code. Each supported release archive must export the same C API from the same
library families. Missing or conflicting definitions fail generation.

Usage: python -m bindgen.c_library   (prints a summary)
"""

import hashlib
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

from . import c_headers, config


def _tool(name):
    local = Path(sys.prefix) / "bin" / name
    found = str(local) if local.is_file() else shutil.which(name)
    if not found:
        raise RuntimeError(f"native extraction needs {name}; install the locked llvm-tools dependency")
    return found


def _inspect(tool, *args):
    return subprocess.check_output([_tool(tool), *map(str, args)], text=True,
                                   env={**os.environ, "LC_ALL": "C"})


def library_stem(filename):
    """Remove the platform suffix and numeric ABI version from a library name."""
    return re.sub(r"(?:\.so(?:\.\d+)*|(?:\.\d+)*\.dylib)$", "", filename)


def _elf_metadata(path):
    dynamic = _inspect("llvm-readelf", "-d", path)
    versions = _inspect("llvm-readelf", "--version-info", path)
    tags = {}
    for tag, value in re.findall(r"\((NEEDED|SONAME|RPATH|RUNPATH)\).*?\[([^\]]+)\]", dynamic):
        tags.setdefault(tag, []).append(value)
    return dict(soname=tags.get("SONAME", []), needed=tags.get("NEEDED", []),
                rpath=tags.get("RPATH", []), runpath=tags.get("RUNPATH", []),
                symbol_versions=sorted(set(re.findall(r"Name: ((?:GLIBC|GLIBCXX|CXXABI)_[\d.]+)", versions))))


def _macho_metadata(path):
    headers = _inspect("llvm-objdump", "--macho", "--private-headers", path)
    tags, minimum_os = {}, []
    for block in re.split(r"(?m)^Load command \d+\n", headers)[1:]:
        command = re.search(r"(?m)^\s*cmd (LC_\w+)\s*$", block)
        if not command:
            raise ValueError(f"unrecognized Mach-O load command in {path}")
        kind = command[1]
        if kind in ('LC_BUILD_VERSION', 'LC_VERSION_MIN_MACOSX'):
            field = 'minos' if kind == 'LC_BUILD_VERSION' else 'version'
            value = re.search(rf'(?m)^\s*{field} ([\d.]+)$', block)
            if not value:
                raise ValueError(f"missing deployment target in {path}")
            minimum_os.append(value[1])
        field = "path" if kind == "LC_RPATH" else "name"
        if kind == "LC_RPATH" or kind.endswith("_DYLIB"):
            value = re.search(rf"(?m)^\s*{field} (.+) \(offset \d+\)$", block)
            if not value:
                raise ValueError(f"missing {field} in {kind} of {path}")
            tags.setdefault(kind, []).append(value[1])
    return dict(soname=tags.get("LC_ID_DYLIB", []),
                needed=[v for k, values in tags.items() if k.endswith("_DYLIB") and k != "LC_ID_DYLIB" for v in values],
                rpath=tags.get("LC_RPATH", []), runpath=[], symbol_versions=[],
                minimum_os=sorted(set(minimum_os)))


def native_inventory(lib_dir=None):
    """Extract byte identities, aliases and ELF/Mach-O dependencies.

    Only identical bytes within the same library family are deduplicated.
    LLVM can inspect every supported archive on either Linux or macOS.
    """
    lib_dir = lib_dir or config.BINARY_DIR / "lib"
    groups = {}
    for path in sorted(lib_dir.iterdir()):
        stem = library_stem(path.name)
        if stem == path.name:
            continue
        if not path.resolve().is_relative_to(lib_dir.resolve()):
            raise ValueError(f"library escapes release directory: {path}")
        with path.open("rb") as stream:
            digest = hashlib.file_digest(stream, "sha256").hexdigest()
        groups.setdefault((stem, digest), []).append(path)
    result = {}
    for (_, digest), paths in sorted(groups.items()):
        canonical = max(paths, key=lambda p: (len(p.name), p.name))
        metadata = _macho_metadata(canonical) if canonical.suffix == ".dylib" else _elf_metadata(canonical)
        result[canonical.name] = dict(sha256=digest, size=canonical.stat().st_size,
            aliases=sorted(p.name for p in paths if p != canonical), **metadata)
    if not result:
        raise ValueError(f"no shared libraries in {lib_dir}")
    return result


def exports(names, lib_dir=None):
    """Return {C function: library stem}, independent of the host OS."""
    lib_dir = lib_dir or config.BINARY_DIR / "lib"
    wanted = set(names)
    out = {}
    for path in sorted(lib_dir.glob("libcvc5*")):
        stem = library_stem(path.name)
        if path.name not in (stem + ".so", stem + ".dylib"):
            continue
        args = ["--defined-only", "--extern-only", "--format=posix"]
        if path.suffix != ".dylib":
            args.append("--dynamic")
        for line in _inspect("llvm-nm", *args, path).splitlines():
            symbol = line.split()[0]
            if path.suffix == ".dylib":
                symbol = symbol.removeprefix("_")
            symbol = symbol.split("@")[0]  # ELF symbol version
            if symbol not in wanted:
                continue
            if symbol in out and out[symbol] != stem:
                raise ValueError(f"multiple libraries export {symbol}")
            out[symbol] = stem
    if missing := wanted - out.keys():
        raise ValueError(f"declared in the headers but exported by no library: {', '.join(sorted(missing))}")
    return out


def main():
    found = exports([r["name"] for r in c_headers.parse()])
    counts = {}
    for library in found.values():
        counts[library] = counts.get(library, 0) + 1
    print(f"{len(found)} C API functions exported by " + ", ".join(f"{k} ({v})" for k, v in sorted(counts.items())))


if __name__ == "__main__":
    main()
