"""Repository paths and the pinned cvc5 release."""

import json
import os
import pathlib
import platform
import sys
import tomllib

ROOT = pathlib.Path(__file__).resolve().parent.parent
VERSION_FILE = ROOT / "cvc5-version.toml"
OVERRIDES_FILE = ROOT / "bindgen" / "overrides.toml"
MANUAL_DIR = ROOT / "bindgen" / "manual"

THIRD_PARTY = ROOT / "third_party"
BINARY_DIR = THIRD_PARTY / "cvc5"
SOURCE_DIR = THIRD_PARTY / "cvc5-src"
INCLUDE_DIR = BINARY_DIR / "include"
# Verification runs through the locked Pixi Python environment. Mojo finds
# installed packages here without extra import paths; reports hash this artifact.
ENV_PREFIX = pathlib.Path(sys.prefix)
APN_PACKAGE_DIR = ENV_PREFIX / "lib" / "mojo"

API_DIR = ROOT / "api"
SNAPSHOT_FILE = API_DIR / "cvc5-api.json"
NULL_VALUES_FILE = API_DIR / "null-values.json"

PACKAGE_DIR = ROOT / "src" / "cvc5_mojo"
ENUMS_FILE = PACKAGE_DIR / "enums.mojo"
RAW_FILE = PACKAGE_DIR / "_c" / "raw.mojo"

CVC5_TESTS_DIR = ROOT / "tests" / "cvc5"  # cvc5's Python unit tests, translated
TRANSLATION_FILE = CVC5_TESTS_DIR / "translation.json"  # which tests run, and why the others do not
CVC5_EXAMPLES_DIR = CVC5_TESTS_DIR / "examples"  # cvc5's Python examples, translated, with Python's output
CALLS_FILE = CVC5_TESTS_DIR / "calls.json"  # the C functions they call, from `pixi run --locked cvc5-tests`


def pinned():
    """Return the parsed cvc5-version.toml."""
    with open(VERSION_FILE, "rb") as fh:
        return tomllib.load(fh)


def platform_name():
    """Conda platform for the native toolchain and solver."""
    targets = {("Linux", "x86_64"): "linux-64", ("Linux", "aarch64"): "linux-aarch64",
               ("Linux", "arm64"): "linux-aarch64", ("Darwin", "arm64"): "osx-arm64"}
    try:
        return targets[platform.system(), platform.machine()]
    except KeyError:
        raise RuntimeError("cvc5_mojo supports Linux x86-64/ARM64 and macOS Apple Silicon") from None


def library_filename(stem, target=None):
    """Unversioned shared-library filename for a conda target."""
    return stem + (".dylib" if (target or platform_name()).startswith("osx-") else ".so")


def binary_dir(target):
    """Keep the host build at the runtime's existing checkout discovery path."""
    return BINARY_DIR if target == platform_name() else THIRD_PARTY / ("cvc5-" + target)


def apn_installed():
    """Report the installed conda build; Pixi owns its pin and archive hash."""
    records = list((ENV_PREFIX / "conda-meta").glob("apn_mojo-*.json"))
    if len(records) != 1 or not (APN_PACKAGE_DIR / "apn_mojo.mojoc").is_file():
        raise RuntimeError("apn_mojo is not installed; run pixi install --locked and use pixi run --locked")
    record = json.loads(records[0].read_text())
    return {key: record[key] for key in ("name", "version", "build", "channel", "url", "sha256")
            if key in record}


def overrides():
    """Return the parsed bindgen/overrides.toml."""
    with open(OVERRIDES_FILE, "rb") as fh:
        return tomllib.load(fh)


def c_compiler():
    return os.environ.get("CC", "cc")
