"""Check an installed candidate against its own installation.json and against a
fresh install from the candidate commit. Prints a JSON summary; exit 1 on mismatch."""

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check(install: Path) -> dict:
    identity = json.loads((install / 'installation.json').read_text())
    recorded = identity['sha256']
    actual = {str(p.relative_to(install)): sha(p) for p in sorted(install.rglob('*'))
              if p.is_file() and not p.is_symlink() and p.name not in ('installation.json', 'opencode.json')}
    config = json.loads((install / 'opencode.json').read_text())
    return {
        'identity': {k: identity.get(k) for k in ('name', 'version', 'host_version', 'interface', 'status')},
        'files_recorded': len(recorded), 'files_present': len(actual),
        'hash_mismatches': sorted(k for k in recorded if actual.get(k) != recorded[k]),
        'unrecorded_files': sorted(set(actual) - set(recorded)),
        'config_sha256_matches': sha(install / 'opencode.json') == identity['config_sha256'],
        'commands': sorted(config.get('commands', {})),
        'reviewers': sorted(k for k, v in config.get('agents', {}).items() if v.get('mode') == 'subagent'),
        'primary': sorted(k for k, v in config.get('agents', {}).items() if v.get('mode') == 'primary'),
        'plugins': [Path(p['package']).name for p in config.get('plugins', [])],
        # b6c8913 linked skills from <install>/skills; later candidates point V2 at the bundle's own directory.
        'skill_links': sorted(p.name for p in (install / 'skills').iterdir() if p.is_symlink())
        if (install / 'skills').is_dir() else [],
        'skill_paths': config.get('skills', []),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--install', default='/opt/egm-v2')
    parser.add_argument('--source', help='checkout of the candidate commit, to compare a fresh install')
    args = parser.parse_args()
    install = Path(args.install)
    result = {'install': check(install)}
    ok = (not result['install']['hash_mismatches'] and not result['install']['unrecorded_files']
          and result['install']['config_sha256_matches'])
    if args.source:
        source = Path(args.source)
        result['source_commit'] = subprocess.check_output(['git', '-C', str(source), 'rev-parse', 'HEAD'], text=True).strip()
        result['source_clean'] = not subprocess.check_output(['git', '-C', str(source), 'status', '--porcelain'], text=True)
        with tempfile.TemporaryDirectory() as temporary:
            fresh = Path(temporary) / 'fresh'
            subprocess.run([sys.executable, '-I', str(source / 'adapters/opencode/install.py'), str(fresh),
                            '--interface', 'v2'], check=True, stdout=subprocess.DEVNULL)
            a = json.loads((install / 'installation.json').read_text())['sha256']
            b = json.loads((fresh / 'installation.json').read_text())['sha256']
            # opencode.json embeds the absolute install path, so compare it with paths normalised.
            normal = lambda root: (root / 'opencode.json').read_text().replace(str(root.resolve()), '<INSTALL>')
            result['matches_fresh_install'] = {
                'file_hashes_equal': a == b, 'config_equal_modulo_path': normal(install) == normal(fresh)}
            ok = ok and a == b and normal(install) == normal(fresh)
    result['ok'] = ok
    print(json.dumps(result, indent=2))
    sys.exit(0 if ok else 1)


if __name__ == '__main__':
    main()
