"""Copy the shareable evidence of a run into the repository, sanitized.

Kept: the analysis, the operator log, the files the workflow wrote, the captured model
requests and OpenCode's session exports (both xz-compressed; read with `xz -dc`). Local paths, account
and organisation identifiers and provider billing details are replaced or dropped.
Never copied: OpenCode's database, its auth files, server logs, or the raw event stream.
The script refuses to write if a credential-like string survives.
"""

import argparse
import lzma
import json
from pathlib import Path
import re
import shutil
import sys

FORBIDDEN = [r'Bearer\s+[A-Za-z0-9._-]{8,}', r'"authorization"', r'\borg_[0-9A-Za-z]{10,}', r'sk-[A-Za-z0-9]{16,}',
             r'gh[pousr]_[A-Za-z0-9]{20,}', r'[A-Za-z0-9._%+-]+@(?!fixture\.invalid)[A-Za-z0-9.-]+\.[a-z]{2,}\b(?<!\.md)(?<!\.py)(?<!\.json)(?<!\.txt)']


def scrubber(run: Path):
    fixture = json.loads((run / 'fixture.json').read_text())
    root = fixture['root']
    replacements = [(root, '<RUN>'), (str(run), '<RUNDIR>'), (str(Path.home()), '<HOME>')]

    def scrub(text: str) -> str:
        for old, new in replacements:
            text = text.replace(old, new)
        text = re.sub(r'/tmp/claude-\d+/[^/"\\ ]+/[0-9a-f-]{36}/scratchpad', '<SCRATCH>', text)
        return re.sub(r'\borg_[0-9A-Za-z]{10,}', '<ORG>', text)
    return scrub


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('run')
    parser.add_argument('destination')
    args = parser.parse_args()
    run, destination = Path(args.run), Path(args.destination)
    scrub = scrubber(run)
    outputs = {}
    for name in ('run.json', 'analysis.json', 'operator.jsonl', 'project-changes.json', 'sessions.json'):
        if (run / name).exists():
            outputs[name] = scrub((run / name).read_text())
    fixture = json.loads((run / 'fixture.json').read_text())
    outputs['fixture.json'] = scrub(json.dumps({k: fixture[k] for k in ('markers', 'model', 'author', 'design', 'project')}, indent=2) + '\n')
    lines = []
    for line in (run / 'provider-requests.jsonl').read_text().split('\n'):
        if not line:
            continue
        record = json.loads(line)
        record.pop('header_names', None)
        usage = (record.get('response') or {}).get('usage')
        if isinstance(usage, dict):
            usage.pop('opencode', None)  # billing details of the account
        lines.append(scrub(json.dumps(record)))
    packed = {'provider-requests.jsonl.xz': '\n'.join(lines) + '\n'}
    sessions = {}
    for path in sorted((run / 'sessions').glob('*.json')):
        export = json.loads(path.read_text())
        export = export.get('data') or export
        (export.get('info') or {}).pop('projectID', None)
        sessions[path.stem] = export
    packed['sessions.json.xz'] = scrub(json.dumps(sessions))
    artifacts = {str(p.relative_to(run)): scrub(p.read_text(errors='replace'))
                 for p in sorted((run / 'artifacts').rglob('*')) if p.is_file()} if (run / 'artifacts').exists() else {}
    everything = {**outputs, **packed, **artifacts}
    for name, text in everything.items():
        for pattern in FORBIDDEN:
            hit = re.search(pattern, text)
            if hit:
                sys.exit(f'refusing to export {name}: matches {pattern!r} near {text[max(0, hit.start() - 40):hit.start() + 20]!r}')
    if destination.exists():
        shutil.rmtree(destination)
    destination.mkdir(parents=True)
    for name, text in {**outputs, **artifacts}.items():
        (destination / name).parent.mkdir(parents=True, exist_ok=True)
        (destination / name).write_text(text)
    for name, text in packed.items():
        (destination / name).write_bytes(lzma.compress(text.encode(), preset=9 | lzma.PRESET_EXTREME))
    size = sum(p.stat().st_size for p in destination.rglob('*') if p.is_file())
    print(f'{destination}: {len(everything)} files, {size / 1024:.0f} KiB')


if __name__ == '__main__':
    main()
