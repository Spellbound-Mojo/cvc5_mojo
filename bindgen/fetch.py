"""Download and verify the pinned cvc5 release into third_party/.

Artifacts pinned by sha256 in cvc5-version.toml:

* the host's official shared-library build -> third_party/cvc5
  (headers for extraction, native libraries for tests and packaging);
* other supported builds -> third_party/cvc5-<platform>
  (native inventory extraction without executing foreign code);
* the source archive of the same tag -> third_party/cvc5-src
  (C API implementation, Python bindings, Python tests and examples).

Each directory carries a stamp with the artifact's sha256, so a pin change
refetches automatically and an unchanged pin is a no-op. Pixi installs the
published apn_mojo dependency separately, using pixi.toml and pixi.lock.

Usage: python -m bindgen.fetch
"""

import hashlib
import io
import os
import shutil
import sys
import tarfile
import tempfile
import urllib.error
import urllib.request
import zipfile

from . import config

# Paths inside the source archive that bindgen reads. A trailing slash
# selects a directory tree.
SOURCE_PATHS = [
    "COPYING",
    "src/api/c/",
    "src/theory/quantifiers/oracle_checker.cpp",
    "src/api/python/cvc5.pxi",
    "src/api/python/cvc5.pxd",
    "src/options/",
    "test/unit/api/python/",
    "examples/api/python/",
]

STAMP = ".sha256"


def download(url, sha256):
    """Download the public release artifact and check its sha256."""
    print(f"downloading {url}", flush=True)
    try:
        with urllib.request.urlopen(url) as resp:
            data = resp.read()
    except urllib.error.HTTPError as e:
        sys.exit(f"downloading {url} failed: HTTP {e.code} {e.reason}")
    digest = hashlib.sha256(data).hexdigest()
    if digest != sha256:
        sys.exit(f"sha256 mismatch for {url}:\n  expected {sha256}\n  got      {digest}")
    return data


def up_to_date(dest, sha256):
    stamp = dest / STAMP
    return stamp.exists() and stamp.read_text().strip() == sha256


def extract_zip(data, root, dest):
    """Extract a zip, recreating symlinks (zipfile does not)."""
    with tempfile.TemporaryDirectory(dir=config.THIRD_PARTY) as tmp:
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            for info in zf.infolist():
                target = os.path.join(tmp, info.filename)
                mode = info.external_attr >> 16
                if info.is_dir():
                    os.makedirs(target, exist_ok=True)
                    continue
                os.makedirs(os.path.dirname(target), exist_ok=True)
                if (mode & 0o170000) == 0o120000:
                    os.symlink(zf.read(info).decode(), target)
                else:
                    with open(target, "wb") as out:
                        out.write(zf.read(info))
                    if mode & 0o111:
                        os.chmod(target, 0o755)
        shutil.rmtree(dest, ignore_errors=True)
        shutil.move(os.path.join(tmp, root), dest)


def extract_sources(data, root, dest, paths=SOURCE_PATHS):
    def wanted(name):
        if not name.startswith(root + "/"):
            return False
        rel = name[len(root) + 1 :]
        return any(rel == p or (p.endswith("/") and rel.startswith(p)) for p in paths)

    with tempfile.TemporaryDirectory(dir=config.THIRD_PARTY) as tmp:
        with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as tf:
            members = [m for m in tf.getmembers() if wanted(m.name)]
            try:
                tf.extractall(tmp, members=members, filter="data")
            except TypeError:  # Python < 3.11.4
                tf.extractall(tmp, members=members)
        shutil.rmtree(dest, ignore_errors=True)
        shutil.move(os.path.join(tmp, root), dest)


def fetch_binary(pin, target=None):
    target = target or config.platform_name()
    spec = pin["binary"][target]
    dest = config.binary_dir(target)
    if up_to_date(dest, spec["sha256"]):
        print(f"cvc5 {pin['version']} {target} binary already present")
        return
    extract_zip(download(spec["url"], spec["sha256"]), spec["root"], dest)
    (dest / STAMP).write_text(spec["sha256"] + "\n")
    print(f"cvc5 {pin['version']} {target} binary installed in {dest}")


def fetch_sources(pin):
    spec = pin["source"]
    dest = config.SOURCE_DIR
    if up_to_date(dest, spec["sha256"]) and all((dest / path).exists() for path in SOURCE_PATHS):
        print(f"cvc5 {pin['version']} sources already present")
        return
    extract_sources(download(spec["url"], spec["sha256"]), spec["root"], dest)
    (dest / STAMP).write_text(spec["sha256"] + "\n")
    print(f"cvc5 {pin['version']} sources installed in {dest}")


def main():
    config.THIRD_PARTY.mkdir(exist_ok=True)
    pin = config.pinned()
    for target in pin["binary"]:
        fetch_binary(pin, target)
    fetch_sources(pin)


if __name__ == "__main__":
    main()
