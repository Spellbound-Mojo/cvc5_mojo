"""Stage the snapshot's native dependency closure and bundled license notices.

Used by the conda recipe and by local packaging checks. No downloads or changes
to the release archive: byte-identical library aliases become relative symlinks.
"""

import argparse
import json
from pathlib import Path
import shutil
import sys

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from bindgen import c_library, config


def dependency_closure(inventory, roots):
    """Resolve bundled dependencies by filename; leave system libraries external."""
    names = {alias: name for name, info in inventory.items() for alias in [name, *info['aliases']]}
    selected, external = set(), set()
    pending = list(roots)
    def bundled_name(reference):
        # Only loader-relative Mach-O references can refer to this bundle.
        # Absolute system paths must remain external even if basenames match.
        if reference.startswith(('@rpath/', '@loader_path/')):
            name = Path(reference).name
            if name not in names:
                raise ValueError(f"missing bundled Mach-O dependency: {reference}")
            return name
        return reference
    for root in pending:
        if root not in names:
            raise ValueError(f"missing C API library: {root}")
    while pending:
        name = names[pending.pop()]
        if name in selected:
            continue
        selected.add(name)
        info = inventory[name]
        for soname in info['soname']:
            if names.get(bundled_name(soname)) != name:
                raise ValueError(f"missing or conflicting SONAME alias: {soname}")
        for dependency in info['needed']:
            local = bundled_name(dependency)
            if local in names:
                pending.append(local)
            else:
                external.add(dependency)
    return {name: inventory[name] for name in sorted(selected)}, sorted(external)


def shipped(snapshot, target):
    """The C API roots, and the libraries and external dependencies a package
    for `target` ships, from the snapshot's native inventory."""
    roots = sorted({config.library_filename(f['library'], target) for f in snapshot['c_functions'].values()})
    return roots, *dependency_closure(snapshot['native_libraries'][target], roots)


def stage(release, prefix, project=config.ROOT, target=None):
    target = target or config.platform_name()
    snapshot = json.loads((project / 'api/cvc5-api.json').read_text())
    if target not in snapshot['native_libraries']:
        raise ValueError(f"unsupported package platform: {target}")
    inventory = c_library.native_inventory(release / 'lib')
    if inventory != snapshot['native_libraries'][target]:
        raise ValueError("release libraries differ from the generated snapshot")
    roots, libraries, external = shipped(snapshot, target)
    license_source = release / 'licenses'
    licenses = sorted(p for p in license_source.rglob('*') if p.is_file())
    if not licenses or not (release / 'COPYING').is_file():
        raise ValueError("release is missing COPYING or bundled license notices")
    for name in ('LICENSE', 'NOTICE'):
        if not (project / name).is_file():
            raise ValueError(f"project is missing {name}")
    dest = prefix / 'lib/cvc5_mojo'
    lic = prefix / 'share/licenses/cvc5_mojo'
    # Refuse to merge into an earlier staging result with potentially stale files.
    if dest.exists() or lic.exists():
        raise ValueError("native library or license destination already exists")
    (dest / 'lib').mkdir(parents=True)
    lic.mkdir(parents=True)
    for name, info in libraries.items():
        shutil.copy2(release / 'lib' / name, dest / 'lib' / name)
        for alias in info['aliases']:
            (dest / 'lib' / alias).symlink_to(name)
    shutil.copytree(license_source, lic / 'cvc5-bundled-licenses')
    shutil.copy2(release / 'COPYING', lic / 'cvc5-COPYING')
    for name in ('LICENSE', 'NOTICE'):
        shutil.copy2(project / name, lic / name)
    manifest = dict(cvc5=snapshot['cvc5'], platform=target, roots=roots, libraries=libraries,
                    external_dependencies=external,
                    license_files=sorted(str(p.relative_to(lic)) for p in lic.rglob('*') if p.is_file()))
    (dest / 'native-libraries.json').write_text(json.dumps(manifest, indent=2) + '\n')
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--release', type=Path, required=True)
    parser.add_argument('--prefix', type=Path, required=True)
    parser.add_argument('--platform', default=config.platform_name(), help='Target conda platform')
    args = parser.parse_args()
    manifest = stage(args.release.resolve(), args.prefix.resolve(), target=args.platform)
    libraries = manifest['libraries']
    print(f"Staged {len(libraries)} native libraries and "
          f"{sum(len(info['aliases']) for info in libraries.values())} relative symlinks")
    print("External dependencies: " + ', '.join(manifest['external_dependencies']))


if __name__ == '__main__':
    main()
