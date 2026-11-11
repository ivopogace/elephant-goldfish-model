"""Evaluate one candidate commit end to end with one command.

  campaign.py --source <checkout> --commit <sha> --output <new dir> \\
      --model opencode-go/deepseek-v4.1-flash --model opencode-go/qwen3.8-flash \\
      [--control-install /opt/egm-v2] [--quick] [--export results/<name>] [--human]

Steps: check out and install the commit, verify the install, run the candidate's own unit
tests and scripted probe, find each model's endpoint and check it answers, run the live
matrix (and the same probes on a control install, if given), analyze, classify, optionally
export sanitized results, and print a summary table ready to paste.

--quick runs only the short probes. --resume continues an interrupted campaign in the same
output directory. --human runs brainstorm, draft and review in sequence
with a person answering every gate, instead of the scripted matrix.
"""

import argparse
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import shutil
import signal
import subprocess
import sys

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
import classify_agents_md  # noqa: E402
import fixture as fixture_module  # noqa: E402
import opencode_api  # noqa: E402

# Each run gets its own time limit, so one slow model cannot stall the whole campaign.
FULL = [('symlink', 'parent_symlink_probe', ['--timeout', '300']), ('grep', 'parent_grep_probe', ['--timeout', '300']),
        ('linked-agents', 'review_stage5', ['--link-agents-md', '--timeout', '1500']),
        ('other-file', 'review_stage5', ['--link-other-file', '--timeout', '1500']),
        ('brainstorm-1', 'brainstorm', ['--timeout', '2700']), ('brainstorm-2', 'brainstorm', ['--timeout', '2700']),
        ('review-1', 'review', ['--timeout', '5400'])]
QUICK = FULL[:4]
CONTROL = [FULL[0], FULL[2], FULL[4]]


CHILDREN = []


def stop_children(*_):
    """If the campaign is terminated, end its drivers too; each one stops its own server."""
    for child in CHILDREN:
        if child.poll() is None:
            child.terminate()
    sys.exit(143)


def say(text: str):
    print(f'\n== {text}', flush=True)


def endpoints(opencode: str, install: Path, models: list, data_home: str, scratch: Path) -> dict:
    """Ask OpenCode where each model is served; providers differ (chat completions, messages)."""
    fx = fixture_module.build(scratch / 'endpoint-check', install, models[0], None)
    server = opencode_api.Server(opencode, fx['project'], fixture_module.environment(fx, data_home),
                                 str(scratch / 'endpoint-check.log'))
    try:
        listed = server.get('/api/model')['data']
    finally:
        server.stop()
    found = {}
    for model in models:
        provider, name = model.split('/', 1)
        entry = next((m for m in listed if m['providerID'] == provider and m['id'] == name), None)
        found[model] = (entry or {}).get('settings', {}).get('baseURL')
    return found


def drive(args, name: str, workflow: str, extra: list, install: Path, model: str, upstream: str, out: Path,
          foreground: bool = False) -> str:
    if (out / name / 'run.json').exists():  # finished in an earlier, interrupted campaign
        print(f'   {name}: already done', flush=True)
        return 'ok'
    shutil.rmtree(out / name, ignore_errors=True)  # a run that was cut off leaves no run.json
    command = [sys.executable, str(HERE / 'driver.py'), workflow, '--output', str(out / name), '--install', str(install),
               '--opencode', args.opencode, '--model', model, '--upstream', upstream, '--data-home', args.data_home,
               *extra]
    if foreground:
        return 'ok' if subprocess.run(command).returncode == 0 else 'failed'
    with open(out / f'{name}.log', 'w') as log:
        child = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL)
        CHILDREN.append(child)
        code = child.wait()
    print(f'   {name}: {"ok" if code == 0 else "did not complete, see " + str(out / (name + ".log"))}', flush=True)
    return 'ok' if code == 0 else 'failed'


def answers(run: Path) -> bool:
    """Did the model answer at all? A rate-limited model returns only errors."""
    log = run / 'provider-requests.jsonl'
    lines = [json.loads(line) for line in log.read_text().split('\n') if line] if log.exists() else []
    return any(record.get('status') == 200 for record in lines)


def table(out: Path, models: list, has_control: bool) -> str:
    def cell(model_dir: Path, side: str) -> dict:
        total = {'sessions': 0, 'ok': 0, 'denied': 0, 'followed': 0, 'other': 0, 'incomplete': 0, 'empty': 0,
                 'symlink': '-', 'failed': set()}
        for analysis in sorted(model_dir.glob(f'{side}-*/analysis.json')):
            a = json.loads(analysis.read_text())
            counts, run = a['counts'], analysis.parent
            reads = counts['reviewer_AGENTS_md_reads']
            total['sessions'] += sum(1 for d in a['dispatches'] if d['child_session'])
            total['ok'] += reads['completed']
            total['denied'] += reads['denied']
            verdicts = classify_agents_md.run_counts(run)
            total['followed'] += verdicts['followed']
            total['other'] += verdicts['followed_other']
            total['incomplete'] += len(counts['guard_incomplete_notices'])
            total['empty'] += len(counts.get('empty_reviews', []))
            if a['workflow'] == 'parent_symlink_probe':
                total['symlink'] = 'no prompt' if a['parent']['reads_through_symlinks_without_a_prompt'] else 'prompt'
            expected = {'reviewers_dispatched', 'no_planted_marker_in_any_review_returned_to_parent',
                        'every_completed_review_passed_the_guard_read_check'}
            if a['workflow'] in ('parent_grep_probe',):
                expected.add('no_secret_or_outside_marker_in_any_parent_request')
            if side == 'new':  # the control is the baseline; its failures are the point of comparison
                total['failed'] |= {f'{model_dir.name}/{run.name}:{k}' for k, v in a['checks'].items()
                                    if v is False and k not in expected}
        return total

    columns = []
    for model in models:
        label = model.split('/', 1)[1]
        model_dir = out / label
        if has_control and any(model_dir.glob('control-*/analysis.json')):
            columns.append((f'{label}, control', cell(model_dir, 'control')))
        if any(model_dir.glob('new-*/analysis.json')):
            columns.append((f'{label}, candidate', cell(model_dir, 'new')))
    rows = [('Reviewer sessions', 'sessions'), ('`AGENTS.md` reads that succeeded', 'ok'),
            ('`AGENTS.md` reads denied', 'denied'), ('Reviews that followed the `AGENTS.md` rule', 'followed'),
            ('Reviews that followed a rule in another linked file', 'other'),
            ('Incomplete-review notices', 'incomplete'), ('Empty reviews the guard accepted', 'empty'),
            ('`egm` reading `.env` through a symlink', 'symlink')]
    lines = ['| | ' + ' | '.join(name for name, _ in columns) + ' |', '| --- |' + ' --- |' * len(columns)]
    lines += [f'| {title} | ' + ' | '.join(str(data[key]) for _, data in columns) + ' |' for title, key in rows]
    failed = sorted(f for _, data in columns for f in data['failed'])
    lines += ['', 'Unexpected failed checks: ' + (', '.join(failed) if failed else 'none')]
    return '\n'.join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--source', required=True, help='git checkout that contains the candidate commit')
    parser.add_argument('--commit', required=True)
    parser.add_argument('--output', required=True, help='new directory for installs and runs')
    parser.add_argument('--model', action='append', required=True, help='provider/model; repeat for several')
    parser.add_argument('--control-install', help='an older install to run the control probes against')
    parser.add_argument('--opencode', default='/opt/opencode-2.2.6/node_modules/.bin/opencode')
    parser.add_argument('--data-home', default=str(Path.home() / '.local/share'))
    parser.add_argument('--jobs', type=int, default=4, help='runs in parallel')
    parser.add_argument('--quick', action='store_true', help='only the short probes')
    parser.add_argument('--human', action='store_true', help='a person answers the gates of brainstorm, draft, review')
    parser.add_argument('--export', help='directory for sanitized results, e.g. results/<name>')
    parser.add_argument('--resume', action='store_true', help='continue in an existing output directory')
    parser.add_argument('--no-fetch', action='store_true', help='do not fetch; the commit is already in the checkout')
    args = parser.parse_args()
    signal.signal(signal.SIGTERM, stop_children)
    source, out = Path(args.source).resolve(), Path(args.output).resolve()
    if out.exists() and not args.resume:
        sys.exit(f'{out} exists. Use --resume to continue an interrupted campaign there.')
    out.mkdir(parents=True, exist_ok=True)

    say(f'Candidate {args.commit}')
    assert not subprocess.check_output(['git', '-C', str(source), 'status', '--porcelain'], text=True), \
        'The source checkout has local changes'
    if not args.no_fetch:
        subprocess.run(['git', '-C', str(source), 'fetch', '-q', 'origin'], check=True)
    subprocess.run(['git', '-C', str(source), 'checkout', '-q', args.commit], check=True)
    head = subprocess.check_output(['git', '-C', str(source), 'rev-parse', 'HEAD'], text=True).strip()
    install = out / f'install-{head[:7]}'
    if not install.exists():
        subprocess.run([sys.executable, '-I', str(source / 'adapters/opencode/install.py'), str(install),
                        '--interface', 'v2'], check=True, stdout=subprocess.DEVNULL)
    check = subprocess.run([sys.executable, str(HERE / 'verify_install.py'), '--install', str(install), '--source', str(source)],
                           capture_output=True, text=True)
    (out / 'install-check.json').write_text(check.stdout)
    print(f'   commit {head}\n   install verified: {check.returncode == 0}')
    env_record = subprocess.run([sys.executable, str(HERE / 'record_environment.py'), '--install', str(install), '--source',
                                 str(source), '--opencode', args.opencode, '--model', ', '.join(args.model)],
                                capture_output=True, text=True)
    (out / 'environment.json').write_text(env_record.stdout)

    say('Offline checks')
    tests = subprocess.run([sys.executable, '-m', 'pytest', 'tests/unit/test_opencode_adapter.py', '-q', '-p', 'no:cacheprovider'],
                           cwd=source, capture_output=True, text=True)
    print('   unit tests: ' + (tests.stdout.strip().split('\n')[-1] if 'No module named pytest' not in tests.stderr
                               else 'skipped, pytest is not installed for this Python'))
    if (out / 'native-probe' / 'summary.json').exists():
        print('   scripted probe: already run')
    else:
        shutil.rmtree(out / 'native-probe', ignore_errors=True)
        probe = subprocess.run([sys.executable, str(source / 'tests/integration/opencode_v2_native_probe.py'), '--source',
                                str(source), '--opencode', args.opencode, '--output', str(out / 'native-probe')],
                               capture_output=True, text=True)
        print(f'   scripted probe: {"passed" if probe.returncode == 0 else "FAILED, see " + str(out / "native-probe")}')

    say('Models')
    shutil.rmtree(out / 'scratch', ignore_errors=True)
    served = endpoints(args.opencode, install, args.model, args.data_home, out / 'scratch')
    usable = []
    for model in args.model:
        label = model.split('/', 1)[1]
        if not served.get(model):
            print(f'   {model}: not offered by this login, skipped')
            continue
        (out / label).mkdir(exist_ok=True)
        drive(args, 'preflight', 'parent_symlink_probe', ['--timeout', '90'], install, model, served[model], out / label)
        if answers(out / label / 'preflight'):
            usable.append(model)
            print(f'   {model}: answers at {served[model]}')
        else:
            print(f'   {model}: no successful answer (rate limited or unavailable), skipped')
        shutil.rmtree(out / label / 'preflight', ignore_errors=True)
    if not usable:
        sys.exit('No model answered. Nothing was run.')

    if args.human:
        model = usable[0]
        label = model.split('/', 1)[1]
        say(f'Human run with {model}: answer each gate when asked')
        chain = out / label
        drive(args, 'human-1-brainstorm', 'brainstorm', ['--human'], install, model, served[model], chain, True)
        drive(args, 'human-2-draft', 'draft', ['--human', '--project-from', str(chain / 'human-1-brainstorm')],
              install, model, served[model], chain, True)
        drive(args, 'human-3-review', 'review', ['--human', '--project-from', str(chain / 'human-2-draft')],
              install, model, served[model], chain, True)
        runs = sorted(p.parent for p in chain.glob('human-*/run.json'))
    else:
        say('Live runs')
        jobs = []
        for model in usable:
            label = model.split('/', 1)[1]
            for name, workflow, extra in (QUICK if args.quick else FULL):
                jobs.append((f'new-{name}', workflow, extra, install, model, served[model], out / label))
            if args.control_install:
                for name, workflow, extra in (CONTROL[:2] if args.quick else CONTROL):
                    jobs.append((f'control-{name}', workflow, extra, Path(args.control_install), model, served[model], out / label))
        # Short probes first, so an interrupted campaign has already answered the cheap questions.
        jobs.sort(key=lambda job: int(job[2][job[2].index('--timeout') + 1]))
        with ThreadPoolExecutor(max_workers=args.jobs) as pool:
            list(pool.map(lambda job: drive(args, *job), jobs))
        runs = sorted(p.parent for p in out.glob('*/*/run.json'))

    say('Analysis')
    subprocess.run([sys.executable, str(HERE / 'analyze.py'), *map(str, runs)], check=True, stdout=subprocess.DEVNULL)
    subprocess.run([sys.executable, str(HERE / 'summarize.py'), *map(str, runs), '--json', str(out / 'summary.json'),
                    '--markdown', str(out / 'summary.md')], check=True, stdout=subprocess.DEVNULL)
    if args.export:
        export = Path(args.export).resolve()
        for run in runs:
            subprocess.run([sys.executable, str(HERE / 'sanitize.py'), str(run), str(export / run.parent.name / run.name)],
                           check=True, stdout=subprocess.DEVNULL)
        for name in ('summary.md', 'summary.json', 'environment.json'):
            shutil.copy2(out / name, export / name)
        print(f'   sanitized results in {export}')
    if args.human:
        for run in runs:
            a = json.loads((run / 'analysis.json').read_text())
            print(f"   {run.name}: {a['status']}, gates answered by a person: {a['checks']['gates_answered_by_a_person']}"
                  f" of {a['checks']['gates_presented']}, failed checks: {[k for k, v in a['checks'].items() if v is False]}")
    else:
        text = table(out, args.model, bool(args.control_install))
        (out / 'comment-table.md').write_text(text + '\n')
        print(text)
    print(f'\nFull table: {out / "summary.md"}')


if __name__ == '__main__':
    main()
