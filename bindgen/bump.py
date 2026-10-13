"""Move the pin in cvc5-version.toml to a new cvc5 release.

Resolves the release tag and commit, downloads the binary and source
archives, computes their sha256, and rewrites cvc5-version.toml, the
context of recipes/cvc5_mojo/recipe.yaml and the PyPI pin of the oracle
environment in pixi.toml. Run `pixi run generate` afterwards and review
`pixi run --locked api-diff`.

Usage:
    python -m bindgen.bump              # latest cvc5 release
    python -m bindgen.bump 1.4.2        # a specific version
    python -m bindgen.bump --refresh-binaries  # add supported builds of the current release

Prints `bumped <old> -> <new>` or `up to date <version>`. Set GITHUB_TOKEN
to avoid GitHub API rate limits.
"""

import argparse
import hashlib
import json
import os
import re
import sys
import urllib.request

from . import config

REPO = "cvc5/cvc5"
BINARY_ARCHITECTURES = {("Linux", "x86_64"): "linux-64", ("Linux", "arm64"): "linux-aarch64",
                        ("macOS", "arm64"): "osx-arm64"}
RECIPE = config.ROOT / "recipes" / "cvc5_mojo" / "recipe.yaml"


def _api(path):
    req = urllib.request.Request(f"https://api.github.com/repos/{REPO}/{path}")
    req.add_header("Accept", "application/vnd.github+json")
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(req) as resp:
        return json.load(resp)


def _sha256(url):
    print(f"hashing {url}", flush=True)
    h = hashlib.sha256()
    with urllib.request.urlopen(url) as resp:
        while chunk := resp.read(1 << 20):
            h.update(chunk)
    return h.hexdigest()


def _commit(tag):
    ref = _api(f"git/ref/tags/{tag}")["object"]
    while ref["type"] == "tag":  # annotated tag
        ref = _api(f"git/tags/{ref['sha']}")["object"]
    return ref["sha"]


def release_binaries(release, current=None):
    """Select supported official shared builds and hash newly selected assets."""
    binaries = {}
    for asset in release['assets']:
        match = re.fullmatch(r'cvc5-(Linux|macOS)-(x86_64|arm64)-shared\.zip', asset['name'])
        if not match or match.groups() not in BINARY_ARCHITECTURES:
            continue
        target = BINARY_ARCHITECTURES[match.groups()]
        url = asset['browser_download_url']
        previous = (current or {}).get(target, {})
        digest = previous['sha256'] if previous.get('url') == url else _sha256(url)
        binaries[target] = dict(url=url, sha256=digest, root=asset['name'].removesuffix('.zip'))
    if set(binaries) != set(BINARY_ARCHITECTURES.values()):
        raise RuntimeError("release is missing a required shared build")
    return {target: binaries[target] for target in sorted(binaries)}


def render(version, tag, commit, binaries, src_sha):
    binary_sections = '\n'.join(
        f'[binary.{target}]\nurl = "{spec["url"]}"\nsha256 = "{spec["sha256"]}"\nroot = "{spec["root"]}"\n'
        for target, spec in binaries.items())
    return f'''# The cvc5 release that the bindings are generated from.
#
# Single source of truth: every bindgen step reads this file, and
# `pixi run --locked bump` rewrites it when cvc5 publishes a new release.
# Do not edit by hand.
version = "{version}"
tag = "{tag}"
commit = "{commit}"

# Official prebuilt shared libraries, selected and hashed from the release.
{binary_sections}
# Source archive of the same tag. Only the files listed in
# bindgen/fetch.py:SOURCE_PATHS are extracted: the C API implementation,
# the Python bindings, and the Python unit tests and examples.
[source]
url = "https://github.com/{REPO}/archive/refs/tags/{tag}.tar.gz"
sha256 = "{src_sha}"
root = "cvc5-{tag}"
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('version', nargs='?')
    parser.add_argument('--refresh-binaries', action='store_true',
                        help='Refresh supported binary assets, preserving the current version by default')
    args = parser.parse_args()
    current = config.pinned()
    requested = args.version or (current['version'] if args.refresh_binaries else None)
    release = _api(f"releases/tags/cvc5-{requested}" if requested else "releases/latest")
    tag = release['tag_name']
    version = tag.removeprefix("cvc5-")
    if version == current["version"] and not args.refresh_binaries:
        print(f"up to date {version}")
        return
    unchanged = version == current["version"]
    commit = _commit(tag)
    if unchanged and commit != current['commit']:
        raise RuntimeError('upstream release tag moved; refusing to refresh its binaries')
    binaries = release_binaries(release, current.get('binary') if unchanged else None)
    src_sha = current['source']['sha256'] if unchanged else _sha256(f"https://github.com/{REPO}/archive/refs/tags/{tag}.tar.gz")
    pin_text = render(version, tag, commit, binaries, src_sha)

    recipe = RECIPE.read_text()
    if not unchanged:
        recipe = re.sub(r'(?m)^(  version: )"[^"]*"', rf'\g<1>"{version}.0"', recipe)
    recipe = re.sub(r'(cvc5_version: )"[^"]*"', rf'\g<1>"{version}"', recipe)
    for spec in binaries.values():
        asset = re.escape(spec['root'] + '.zip')
        recipe, count = re.subn(rf"({asset}\n\s+sha256: )\w+", rf"\g<1>{spec['sha256']}", recipe)
        if count != 1:
            raise RuntimeError(f"recipe must select exactly one source for {spec['root']}")

    # The oracle environment's official Python bindings follow the pin.
    pixi = config.ROOT / "pixi.toml"
    manifest = pixi.read_text()
    if not unchanged:
        manifest = re.sub(r'(?m)^(version = )"[^"]*"', rf'\g<1>"{version}.0"', manifest)
    manifest = re.sub(r'(?m)^(cvc5 = )"==[^"]*"', rf'\g<1>"=={version}"', manifest)
    # Validate every source replacement before writing any of the manifests.
    config.VERSION_FILE.write_text(pin_text)
    RECIPE.write_text(recipe)
    pixi.write_text(manifest)
    print(f"refreshed binaries for {version}" if unchanged else f"bumped {current['version']} -> {version}")


if __name__ == "__main__":
    main()
