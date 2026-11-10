"""Write the facts #282 asks every result to carry: commit, hashes, versions, platform, date."""

import argparse
import datetime
import hashlib
import json
from pathlib import Path
import platform
import subprocess


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--install', default='/opt/egm-v2')
    parser.add_argument('--source', required=True, help='checkout of the candidate commit')
    parser.add_argument('--opencode', default='/opt/opencode-2.2.6/node_modules/.bin/opencode')
    parser.add_argument('--model', default='opencode-go/longcat-2.5-free')
    args = parser.parse_args()
    install = Path(args.install)
    identity = json.loads((install / 'installation.json').read_text())
    binary = Path(args.opencode).resolve()
    package = next((p for p in binary.parents if (p / 'package.json').exists()), None)
    print(json.dumps({
        'date_utc': datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%d'),
        'egm_candidate_commit': subprocess.check_output(['git', '-C', args.source, 'rev-parse', 'HEAD'], text=True).strip(),
        'egm_candidate_remote': subprocess.check_output(['git', '-C', args.source, 'remote', 'get-url', 'origin'], text=True).strip(),
        'installation': {k: identity.get(k) for k in ('name', 'version', 'host_version', 'interface', 'status', 'config_sha256')},
        'installed_package_hashes': identity['sha256'],
        'installation_json_sha256': hashlib.sha256((install / 'installation.json').read_bytes()).hexdigest(),
        'opencode_version': subprocess.check_output([args.opencode, '--version'], text=True).strip(),
        'opencode_package': json.loads((package / 'package.json').read_text()).get('name') if package else None,
        'opencode_binary_sha256': hashlib.sha256(binary.read_bytes()).hexdigest(),
        'model': args.model,
        'model_note': 'Model ID as requested and as echoed by the provider; the provider does not expose a backend revision.',
        'platform': {'system': platform.system(), 'release': platform.release(), 'machine': platform.machine(),
                     'python': platform.python_version()},
    }, indent=2))


if __name__ == '__main__':
    main()
