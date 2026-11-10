"""Run one EGM workflow in OpenCode through its HTTP API and keep the evidence.

The driver starts a private server in a disposable profile, sends the opening
message, and then acts as the operator: it answers structured questions and plain
chat turns from workflows.py and answers permission requests from a fixed policy.
Every pause is logged with the time it appeared and the time it was answered.
"""

import argparse
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time
import urllib.error

sys.path.insert(0, str(Path(__file__).parent))
import capture_proxy  # noqa: E402
import fixture as fixture_module  # noqa: E402
import opencode_api  # noqa: E402
import workflows  # noqa: E402

SHELL_OK = re.compile(r'^(git config (--get )?user\.name|mkdir -p [\w./-]+|ls( -\w+)?( [\w./-]+)?|date( [+%\w-]+)?)$')


def permission_decision(request: dict, project: Path, parent: str) -> tuple[str, str]:
    """The operator's standing policy. Reviewers are never granted anything."""
    if request['sessionID'] != parent:
        return 'reject', 'operator never grants reviewer requests'
    action, resources = request.get('action'), request.get('resources') or []
    if action == 'edit':
        for resource in resources:
            target = (project / resource).resolve()
            relative = os.path.relpath(target, project)
            if relative.startswith('..') or '.env' in relative or relative.startswith('src'):
                return 'reject', f'write outside the allowed project documents: {resource}'
        return 'once', 'document write inside the project'
    if action == 'shell' and all(SHELL_OK.match(resource.strip()) for resource in resources):
        return 'once', 'harmless shell command on the allowlist'
    return 'reject', 'not on the operator allowlist'


def snapshot(project: Path) -> dict:
    files = {}
    for path in sorted(project.rglob('*')):
        if '.git' in path.relative_to(project).parts or not path.is_file() or path.is_symlink():
            continue
        files[str(path.relative_to(project))] = path.read_text(errors='replace')
    return files


def run(args) -> int:
    out = Path(args.output).resolve()
    out.mkdir(parents=True, exist_ok=False)
    if args.project_from:
        # Continue a chain (brainstorm -> draft -> review) in the same fixture.
        fixture = json.loads((Path(args.project_from) / 'fixture.json').read_text())
    else:
        fixture = fixture_module.build(out / 'fixture', Path(args.install), args.model, None,
                                       with_design=args.workflow.startswith('review'), inject=args.inject,
                                       long_design=args.long_design)
    if args.without_guard:
        # Negative control: the same configuration with the guard plugin removed.
        config = json.loads((Path(args.install) / 'opencode.json').read_text())
        config.pop('plugins')
        (out / 'opencode-without-guard.json').write_text(json.dumps(config, indent=2) + '\n')
        fixture['config'] = str(out / 'opencode-without-guard.json')
    else:
        fixture.pop('config', None)
    proxy = capture_proxy.serve(args.upstream, str(out / 'provider-requests.jsonl'))
    provider = args.model.split('/', 1)[0]
    config_path = Path(fixture['home']) / 'config' / 'opencode' / 'opencode.json'
    config = json.loads(config_path.read_text())
    config['providers'] = {provider: {'settings': {'baseURL': f'http://127.0.0.1:{proxy.server_port}/v1'}}}
    config_path.write_text(json.dumps(config, indent=2) + '\n')
    (out / 'fixture.json').write_text(json.dumps(fixture, indent=2) + '\n')
    project = Path(fixture['project'])
    before = snapshot(project)
    env = fixture_module.environment(fixture, args.data_home)
    server = opencode_api.Server(args.opencode, str(project), env, str(out / 'server-log.txt'))
    server.record_events(str(out / 'events.jsonl'))
    pauses = open(out / 'operator.jsonl', 'a')
    state = {'chat_turns': 0, 'answers': [], 'forms': 0}
    state['exists'] = lambda name: any(project.rglob(name))
    state['answered'] = lambda pattern: any(re.search(pattern, a, re.I) for a in state['answers'])
    state['new_design'] = lambda: any(
        str(p.relative_to(project)) not in before for p in (project / 'docs' / 'designs').glob('*.md'))
    spec = workflows.WORKFLOWS[args.workflow](state)
    target = args.target or fixture.get('design')
    if args.workflow.startswith('review') and not target:
        # Chained run: review whatever egm-draft saved under docs/designs.
        designs = sorted((project / 'docs' / 'designs').glob('*.md'))
        target = str(designs[0]) if designs else None
        assert target, 'No design document to review'
    values = {**fixture['markers'], 'design': target}
    started = time.time()
    status = 'timeout'
    tmux_name = f'egm-{os.getpid()}'

    def log(kind, **fields):
        record = {'kind': kind, 'at': time.time(), 'elapsed': round(time.time() - started, 1), **fields}
        pauses.write(json.dumps(record) + '\n')
        pauses.flush()
        shown = {k: (v if len(str(v)) < 300 else str(v)[:300] + '...') for k, v in fields.items()}
        print(f'[{record["elapsed"]:7.1f}s] {kind}: {json.dumps(shown, ensure_ascii=False)}', flush=True)

    try:
        provider_id, model_id = args.model.split('/', 1)
        create = {'agent': args.agent, 'model': {'providerID': provider_id, 'id': model_id},
                  'location': {'directory': str(project)}}
        if args.preapprove_writes:
            # For the recorded run only: the operator's write policy is granted up front as session
            # rules, and shell is refused outright, and everything else the
            # live policy would refuse is denied outright, so no permission dialog appears on screen.
            bundle = str(Path(args.install) / 'bundle' / '*')
            create['permissions'] = [
                {'action': 'edit', 'resource': '*', 'effect': 'allow'},
                {'action': 'shell', 'resource': '*', 'effect': 'deny'},
                {'action': 'read', 'resource': '*.env', 'effect': 'deny'},
                {'action': 'read', 'resource': '*.env.*', 'effect': 'deny'},
                {'action': 'read', 'resource': '*.env.example', 'effect': 'allow'},
                {'action': 'external_directory', 'resource': '*', 'effect': 'deny'},
                {'action': 'external_directory', 'resource': bundle, 'effect': 'allow'}]
        session = server.post('/api/session', create)['data']['id']
        if args.record_tui:
            tui_env = {**env, 'OPENCODE_PASSWORD': server.password, 'TERM': 'xterm-256color', 'COLORTERM': 'truecolor'}
            command = (f"asciinema rec --overwrite -q -c '{args.opencode} --server {server.url} "
                       f"--session {session}' {out / 'tui.cast'}")
            subprocess.run(['tmux', 'kill-session', '-t', tmux_name], capture_output=True)
            subprocess.run(['tmux', 'new-session', '-d', '-s', tmux_name, '-x', '120', '-y', '30', command],
                           env=tui_env, cwd=str(project), check=True)
            (out / 'tui-started.txt').write_text(f'{time.time()}\n')
            time.sleep(6)
        opening = spec['opening'].format(**values)
        server.post(f'/api/session/{session}/prompt', {'text': opening})
        log('opening', session=session, text=opening)
        (out / 'session-id.txt').write_text(session + '\n')
        idle_since = None
        cancelled = False
        while time.time() - started < args.timeout:
            time.sleep(1)
            if (out / 'STOP').exists():  # The operator walks away: keep the evidence gathered so far.
                status = 'operator-stopped'
                break
            try:
                forms = server.get('/api/form')['data'] or []
                permissions = server.get('/api/permission/request')['data'] or []
                active = server.get('/api/session/active')['data'] or {}
            except (urllib.error.URLError, TimeoutError, ConnectionError) as error:
                log('api-error', error=str(error))
                continue
            for request in permissions:
                decision, why = permission_decision(request, project, session)
                log('permission', session=request['sessionID'], action=request.get('action'),
                    resources=request.get('resources'), decision=decision, why=why)
                try:
                    server.post(f'/api/session/{request["sessionID"]}/permission/{request["id"]}/reply',
                                {'decision': decision, 'message': None if decision == 'once' else why})
                except urllib.error.HTTPError as error:
                    # One tool call can raise several requests; rejecting the first withdraws the rest.
                    log('permission-withdrawn', request=request['id'], status=error.code)
            for form in forms:
                seen = time.time()
                fields = form.get('fields') or []
                answer, described = {}, []
                for field in fields:
                    options = [o.get('label') or o.get('value') for o in field.get('options') or []]
                    question = ' '.join(filter(None, [field.get('title'), field.get('description')]))
                    choice = spec['form'](question, options, state)
                    value = next((o.get('value', o.get('label')) for o in field.get('options') or []
                                  if (o.get('label') or o.get('value')) == choice), choice)
                    answer[field['key']] = value
                    described.append({'question': question, 'options': options, 'choice': choice})
                if form['sessionID'] != session:
                    log('form-from-reviewer', session=form['sessionID'], fields=described)
                if args.cancel_first_gate and not cancelled:
                    # A dismissed question is not approval: cancel it and see what the agent does.
                    cancelled = True
                    time.sleep(args.gate_dwell)
                    server.call('DELETE', f'/api/session/{form["sessionID"]}/form/{form["id"]}')
                    log('gate-cancelled', session=form['sessionID'], fields=described, seen=seen)
                    continue
                # Hold the gate open so the trace can show that nothing runs while it waits.
                time.sleep(args.gate_dwell)
                try:
                    server.post(f'/api/session/{form["sessionID"]}/form/{form["id"]}/reply', {'answer': answer})
                except urllib.error.HTTPError as error:
                    log('form-withdrawn', form=form['id'], status=error.code)
                    continue
                state['forms'] += 1
                state['answers'] += [d['choice'] for d in described]
                log('gate', session=form['sessionID'], fields=described, seen=seen, replied=time.time(),
                    multi_question=len(fields) != 1)
            if forms or permissions or session in active:
                idle_since = None
                continue
            idle_since = idle_since or time.time()
            if time.time() - idle_since < 3:
                continue
            idle_since = None
            messages = server.get(f'/api/session/{session}/message')['data'] or []
            last = next((m for m in messages if m.get('type') == 'assistant'), {})
            text = '\n'.join(part.get('text', '') for part in last.get('content', []) if part.get('type') == 'text')
            log('agent-turn-ended', text=text, finish=last.get('finish'),
                outcome=next((m.get('outcome') for m in messages if m.get('type') == 'idle'), None))
            if spec['done'](state):
                status = 'completed'
                break
            if cancelled and args.cancel_first_gate:
                status = 'stopped-after-cancel'
                break
            if args.end_after_gate_turn and state['forms']:
                status = 'ended-after-gate-turn'
                break
            if state['chat_turns'] >= args.max_chat_turns:
                status = 'chat-turn-limit'
                break
            reply = spec['chat'](state)
            time.sleep(args.gate_dwell)
            server.post(f'/api/session/{session}/prompt', {'text': reply})
            state['chat_turns'] += 1
            log('chat-reply', text=reply)
        log('finished', status=status, chat_turns=state['chat_turns'], gates=state['forms'])
        sessions = {}
        try:
            listing = server.get('/api/session?limit=500')['data']
        except Exception:
            listing = server.get('/api/session')['data']
        family = {session}
        for _ in range(3):
            family |= {s['id'] for s in listing if s.get('parentID') in family}
        (out / 'sessions').mkdir()
        for sid in sorted(family):
            info = next((s for s in listing if s['id'] == sid), {})
            export = server.get(f'/api/experimental/session/{sid}/export')
            (out / 'sessions' / f'{sid}.json').write_text(json.dumps(export, indent=1) + '\n')
            sessions[sid] = {'agent': info.get('agent'), 'parentID': info.get('parentID'), 'title': info.get('title')}
        (out / 'sessions.json').write_text(json.dumps(sessions, indent=2) + '\n')
    finally:
        if args.record_tui:
            time.sleep(4)
            subprocess.run(['tmux', 'kill-session', '-t', tmux_name], capture_output=True)
            time.sleep(1)
        server.stop()
        proxy.shutdown()
        pauses.close()
    after = snapshot(project)
    (out / 'project-changes.json').write_text(json.dumps({
        'added': sorted(set(after) - set(before)), 'removed': sorted(set(before) - set(after)),
        'modified': sorted(k for k in after if k in before and after[k] != before[k])}, indent=2) + '\n')
    artifacts = out / 'artifacts'
    artifacts.mkdir()
    for name in sorted(set(after) - set(before)) + sorted(k for k in after if k in before and after[k] != before[k]):
        destination = artifacts / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(project / name, destination)
    version = subprocess.check_output([args.opencode, '--version'], text=True, env=env).strip()
    (out / 'run.json').write_text(json.dumps({
        'workflow': args.workflow, 'status': status, 'model': args.model, 'opencode': version,
        'started': started, 'finished': time.time(), 'session': session, 'gate_dwell': args.gate_dwell,
        'cancel_first_gate': args.cancel_first_gate, 'install': args.install,
        'agent': args.agent, 'inject': args.inject, 'long_design': args.long_design, 'without_guard': args.without_guard,
        'preapprove_writes': args.preapprove_writes, 'record_tui': args.record_tui,
        'expected_artifacts': spec['artifacts'], 'target': target,
    }, indent=2) + '\n')
    print('status:', status)
    return 0 if status in ('completed', 'stopped-after-cancel', 'ended-after-gate-turn') else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('workflow', choices=sorted(workflows.WORKFLOWS))
    parser.add_argument('--output', required=True, help='new directory for this run')
    parser.add_argument('--install', default='/opt/egm-v2')
    parser.add_argument('--opencode', default='/opt/opencode-2.2.6/node_modules/.bin/opencode')
    parser.add_argument('--model', default='opencode-go/longcat-2.5-free')
    parser.add_argument('--upstream', default='https://opencode.ai/inference/go/openai/v1')
    parser.add_argument('--data-home', default=os.path.expanduser('~/.local/share'),
                        help='XDG data directory that holds the OpenCode login; used in place, never copied')
    parser.add_argument('--project-from', help='reuse the fixture of an earlier run directory')
    parser.add_argument('--target', help='design document to review (default: the fixture design)')
    parser.add_argument('--timeout', type=int, default=3600)
    parser.add_argument('--gate-dwell', type=float, default=6)
    parser.add_argument('--max-chat-turns', type=int, default=12)
    parser.add_argument('--cancel-first-gate', action='store_true')
    parser.add_argument('--agent', default='egm', help='primary agent for the session')
    parser.add_argument('--inject', action='store_true', help='plant hostile instructions in the design document')
    parser.add_argument('--long-design', action='store_true', help='make the design longer than one read page (2,000 lines)')
    parser.add_argument('--without-guard', action='store_true', help='negative control: remove the guard plugin')
    parser.add_argument('--end-after-gate-turn', action='store_true',
                        help='end the run when the first agent turn after an answered gate finishes')
    parser.add_argument('--record-tui', action='store_true', help='record the attached terminal UI with asciinema')
    parser.add_argument('--preapprove-writes', action='store_true',
                        help='grant document writes and refuse shell as session rules instead of per request')
    sys.exit(run(parser.parse_args()))


if __name__ == '__main__':
    main()
