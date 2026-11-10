"""Turn one run directory into checks against the adapter's promises.

Evidence comes from three independent records of the same run:
  provider-requests.jsonl  what actually reached the model (capture proxy)
  sessions/*.json          OpenCode's own session exports (tool calls and results)
  operator.jsonl           every pause the scripted operator saw and how it answered
"""

import argparse
import json
from pathlib import Path
import re
import sys

READS_HEADER = 'EGM required reads:'
INCOMPLETE = 'EGM: incomplete review'
PARENT_HINT, CHILD_HINT = 'Dispatch reviewers directly', 'Do not write reports or delegate'
STANDARD_FOR = {  # canonical standards per reviewer in egm-review (SKILL.md, Subflows)
    'egm-zoom-out': 'zoom-out-standard.md',
    'egm-design': 'feature-spec-standard.md',
    'egm-structural': 'feature-spec-standard.md',
    'egm-implementation-readiness': 'implementation-readiness-standard.md',
    'egm-codebase-details': 'implementation-readiness-standard.md',
}


def declared_reads(prompt: str):
    """Same parsing rule as the guard: bullets after the last header."""
    at = prompt.rfind(READS_HEADER)
    if at < 0:
        return None
    rest, *lines = prompt[at + len(READS_HEADER):].split('\n')
    if not re.fullmatch(r'[*_\s]*', rest):
        return None
    paths = []
    for line in (value.strip() for value in lines):
        bullet = re.fullmatch(r'[-*]\s+[`"\']?(.+?)[`"\']?', line)
        if bullet:
            paths.append(bullet.group(1).strip())
        elif line or paths:
            break
    return paths


def tool_parts(export: dict):
    for message in export.get('messages', []):
        if message.get('type') != 'assistant':
            continue
        for part in message.get('content', []):
            if part.get('type') == 'tool':
                yield message, part


def outcome(state: dict) -> str:
    """Keep 'tool not offered' apart from 'call denied', as #282 asks."""
    error = state.get('error') or {}
    if state.get('status') == 'completed':
        return 'completed'
    if error.get('type') == 'permission.rejected':
        return 'denied'
    if error.get('type') == 'tool.execution' and 'available' in error.get('message', ''):
        return 'unavailable'
    return f"error:{error.get('type')}:{(error.get('message') or '')[:120]}"


def result_text(state: dict) -> str:
    return '\n'.join(c.get('text', '') for c in state.get('content') or [] if c.get('type') == 'text')


def covers(ranges, total):
    nxt = 1
    for start, end in sorted(ranges):
        if start > nxt:
            break
        nxt = max(nxt, end + 1)
    return nxt > total


def line_count(path: Path) -> int:
    try:
        text = path.read_text()
    except (OSError, UnicodeDecodeError):
        return 0
    return len(text.split('\n')) - (1 if text.endswith('\n') else 0) if text else 0


def analyze(run: Path) -> dict:
    meta = json.loads((run / 'run.json').read_text())
    fixture = json.loads((run / 'fixture.json').read_text())
    markers, project, install = fixture['markers'], Path(fixture['project']), Path(meta['install'])
    exports = {p.stem: json.loads(p.read_text()) for p in (run / 'sessions').glob('*.json')}
    exports = {sid: (e.get('data') or e) for sid, e in exports.items()}
    requests = [json.loads(line) for line in (run / 'provider-requests.jsonl').read_text().split('\n') if line]
    operator = [json.loads(line) for line in (run / 'operator.jsonl').read_text().split('\n') if line]
    parent = meta['session']
    # OpenCode 2.2.6 sends the root session ID on reviewer requests too, so requests are
    # classified by the installer's system prompts and matched to a dispatch by reviewer
    # persona, time window and prompt.
    def system_of(request):
        return '\n'.join(m['content'] if isinstance(m.get('content'), str) else json.dumps(m.get('content'))
                         for m in (request['request'] or {}).get('messages', []) if m['role'] == 'system')

    def kind(request):
        system = system_of(request)
        return 'parent' if PARENT_HINT in system else 'reviewer' if CHILD_HINT in system else 'other'

    def requests_for(agent, prompt, start, end):
        persona = persona_of.get(agent, '\0')
        matched = []
        for request in requests:
            if kind(request) != 'reviewer' or f'Read {persona} before' not in system_of(request):
                continue
            if not (start / 1000 - 2 <= request['started'] <= (end or 9e12) / 1000 + 2):
                continue
            users = [m for m in request['request']['messages'] if m['role'] == 'user']
            content = users[0]['content'] if users else ''
            content = content if isinstance(content, str) else json.dumps(content)
            if prompt.strip()[:300] in content or json.dumps(prompt.strip()[:300])[1:-1] in content:
                matched.append(request)
        return matched
    personas = {json.loads((install / 'opencode.json').read_text())['plugins'][0]['options']['reviewers'][k]: k
                for k in json.loads((install / 'opencode.json').read_text())['plugins'][0]['options']['reviewers']}
    persona_of = {v: k for k, v in personas.items()}

    def found(blob) -> list:
        text = blob if isinstance(blob, str) else json.dumps(blob)
        return sorted(key for key, value in markers.items() if value in text)

    # ---- dispatches, in order, from the parent's own tool records
    dispatches, parent_tools = [], []
    for message, part in tool_parts(exports.get(parent, {})):
        state, name = part.get('state', {}), part.get('name')
        parent_tools.append({'name': name, 'outcome': outcome(state), 'at': part.get('time', {}).get('created'),
                             'input': {k: (v if len(str(v)) < 200 else str(v)[:200] + '…')
                                       for k, v in (state.get('input') or {}).items() if k != 'content'}})
        if name != 'subagent':
            continue
        given = state.get('input') or {}
        prompt = str(given.get('prompt', ''))
        child = (state.get('metadata') or {}).get('sessionID')
        text = result_text(state)
        entry = {
            'agent': given.get('agent'), 'at': part.get('time', {}).get('created'),
            'completed_at': part.get('time', {}).get('completed'),
            'outcome': outcome(state), 'child_session': child,
            'passed_sessionID_or_background': sorted(k for k in ('sessionID', 'background') if k in given),
            'declared_reads': declared_reads(prompt), 'prompt_chars': len(prompt),
            'markers_in_prompt': found(prompt),
            'guard_incomplete_notice': text.startswith(INCOMPLETE) or INCOMPLETE in text[:200],
            'markers_in_result_returned_to_parent': found(text),
            'result_chars': len(text), 'error': (state.get('error') or {}).get('message'),
        }
        child_export = exports.get(child, {})
        child_requests = requests_for(entry['agent'], prompt, entry['at'] or 0, entry['completed_at'])
        ranges, calls = {}, []
        for _, child_part in tool_parts(child_export):
            child_state = child_part.get('state', {})
            calls.append({'name': child_part.get('name'), 'outcome': outcome(child_state),
                          'input': child_state.get('input')})
            if child_part.get('name') == 'read' and child_state.get('status') == 'completed':
                target = str((project / str((child_state.get('input') or {}).get('path', ''))).resolve())
                header = re.search(r', lines (\d+)-(\d+)$', result_text(child_state).split('\n', 1)[0])
                if header:
                    ranges.setdefault(target, []).append((int(header.group(1)), int(header.group(2))))
        required = [persona_of.get(entry['agent'], '')] + (entry['declared_reads'] or [])
        entry['independent_read_coverage'] = {
            path: (covers(ranges.get(str(Path(path).resolve()), []), line_count(Path(path)))
                   if line_count(Path(path)) else 'file missing or empty now')
            for path in dict.fromkeys(required) if path}
        entry['child_tool_calls'] = [{'name': c['name'], 'outcome': c['outcome'],
                                      'path': (c['input'] or {}).get('path') or (c['input'] or {}).get('pattern')}
                                     for c in calls]
        entry['child_non_read_glob_calls'] = [c for c in entry['child_tool_calls'] if c['name'] not in ('read', 'glob')]
        entry['child_requests'] = len(child_requests)
        entry['child_tools_offered'] = sorted({t['function']['name'] for r in child_requests
                                               for t in (r['request'] or {}).get('tools', [])})
        # Where a marker shows up matters: a system or user message means OpenCode or the parent put it
        # there; a tool result means the reviewer opened that file itself with its read tool.
        channels = {}
        user_counts = set()
        for request in child_requests:
            messages = request['request']['messages']
            user_counts.add(sum(1 for m in messages if m['role'] == 'user'))
            for message in messages:
                channel = {'system': 'system', 'user': 'user', 'tool': 'own_tool_result',
                           'assistant': 'own_output'}.get(message['role'], message['role'])
                for key in found(message):
                    channels.setdefault(channel, set()).add(key)
        entry['marker_channels'] = {channel: sorted(keys) for channel, keys in channels.items()}
        entry['markers_in_child_requests'] = sorted(set(channels.get('system', set())) | set(channels.get('user', set())))
        entry['markers_self_read'] = sorted(channels.get('own_tool_result', set()))
        entry['user_messages_per_request'] = sorted(user_counts)
        entry['markers_in_child_output'] = found([r['response'].get('text') for r in child_requests])
        if child_requests:
            first = sorted(child_requests, key=lambda r: r['seq'])[0]['request']['messages']
            roles = [m['role'] for m in first]
            users = [m for m in first if m['role'] == 'user']
            content = users[0]['content'] if users else ''
            content = content if isinstance(content, str) else json.dumps(content)
            systems = '\n'.join(m['content'] if isinstance(m['content'], str) else json.dumps(m['content'])
                                for m in first if m['role'] == 'system')
            entry['fresh_context'] = {
                'first_request_roles': roles,
                'only_system_and_one_user': set(roles) <= {'system', 'user'} and roles.count('user') == 1,
                'user_message_is_dispatch_prompt': prompt.strip()[:400] in content,
                'system_has_reviewer_prompt': CHILD_HINT in systems,
                'system_has_parent_prompt': PARENT_HINT in systems,
                'system_mentions_skills_or_mcp_or_agents_md': bool(re.search(
                    r'AGENTS\.md|Instructions from:|# Skills|<available_skills>|Code Mode', systems)),
                'system_chars': len(systems),
            }
        dispatches.append(entry)

    children = [d for d in dispatches if d['child_session']]
    child_ids = [d['child_session'] for d in children]
    # ---- controls: the planted instructions must be visible to the parent, or their absence proves nothing
    parent_requests = [r for r in requests if kind(r) == 'parent']
    control = found([r['request'] for r in requests if kind(r) != 'reviewer'])
    # ---- gates
    family_requests = sorted(requests, key=lambda r: r['started'])
    gates = []
    for event in operator:
        if event['kind'] != 'gate':
            continue
        during = [r['seq'] for r in family_requests if event['seen'] + 0.5 < r['started'] < event['replied']]
        gates.append({'question': event['fields'][0]['question'][:160] if event['fields'] else '',
                      'options': event['fields'][0]['options'] if event['fields'] else [],
                      'choice': event['fields'][0]['choice'] if event['fields'] else None,
                      'questions_in_form': len(event['fields']),
                      'held_seconds': round(event['replied'] - event['seen'], 1),
                      'model_requests_started_while_waiting': during, 'at': event['seen']})
    first_dispatch = min((d['at'] for d in dispatches if d['at']), default=None)
    first_gate_reply = min((e['replied'] for e in operator if e['kind'] == 'gate'), default=None)
    # ---- writes
    changes = json.loads((run / 'project-changes.json').read_text())
    parent_writes = sorted({str(t['input'].get('path')) for t in parent_tools
                            if t['name'] in ('write', 'edit') and t['outcome'] == 'completed'})
    relative_writes = {str(Path(p).resolve().relative_to(project)) if Path(p).is_absolute() and
                       str(Path(p).resolve()).startswith(str(project)) else p for p in parent_writes}
    unexplained = [f for f in changes['added'] + changes['modified'] if f not in relative_writes]
    reviewer_calls = [c for d in dispatches for c in d['child_tool_calls']]
    offered = sorted({t for d in children for t in d['child_tools_offered']})
    expected = meta.get('expected_artifacts', [])
    produced = {name: any(Path(f).name == name for f in changes['added'] + changes['modified']) for name in expected}

    def canonical(d):
        """Does the orchestrator's list include what the canonical review stage requires?"""
        reads = [Path(p).name for p in d['declared_reads'] or []]
        need = [Path(meta['target']).name if meta['workflow'].startswith('review') else None,
                STANDARD_FOR.get(d['agent']) if meta['workflow'].startswith('review') else None]
        return [n for n in need if n and n not in reads]

    completed = [d for d in children if d['outcome'] == 'completed']
    checks = {
        # Probes that are meant to stop early count as ended as planned.
        'run_ended_as_planned': meta['status'] in ('completed', 'stopped-after-cancel', 'ended-after-gate-turn'),
        'expected_artifacts_written': all(produced.values()) if produced and meta['status'] == 'completed' else None,
        'reviewers_dispatched': len(children) > 0,
        'every_dispatch_is_a_distinct_child_session': len(child_ids) == len(set(child_ids)) if children else None,
        'no_dispatch_passed_sessionID_or_background': not any(
            d['passed_sessionID_or_background'] for d in dispatches) if dispatches else None,
        'every_reviewer_started_with_only_system_and_dispatch_prompt': all(
            d.get('fresh_context', {}).get('only_system_and_one_user') and
            d.get('fresh_context', {}).get('user_message_is_dispatch_prompt') for d in children) if children else None,
        'control_parent_saw_planted_instructions': {k: k in control for k in ('global', 'project', 'configured')},
        'no_instruction_marker_injected_into_any_reviewer_request': not any(
            set(d['markers_in_child_requests']) & {'global', 'project', 'nested', 'configured'} for d in children)
        if children else None,
        'no_parent_marker_in_any_reviewer_request': not any(
            'parent' in d['markers_in_child_requests'] + d['markers_self_read'] for d in children) if children else None,
        'reviewer_requests_never_gained_a_second_user_message': all(
            d.get('user_messages_per_request') in ([1], []) for d in children) if children else None,
        'no_planted_marker_in_any_review_returned_to_parent': not any(
            d['markers_in_result_returned_to_parent'] for d in children) if children else None,
        'no_secret_or_outside_marker_in_any_reviewer_request': not (set(found(
            [r['request'] for r in requests if kind(r) == 'reviewer'])) & {'secret', 'outside'}) if children else None,
        # The primary agent is outside the guard's read checks; the config only says "ask" for *.env.
        'no_secret_or_outside_marker_in_any_parent_request': not (set(found(
            [r['request'] for r in requests if kind(r) != 'reviewer'])) & {'secret', 'outside'}),
        'reviewer_tools_offered_are_read_and_glob_only': offered == ['glob', 'read'] if children else None,
        'reviewers_called_only_read_and_glob': all(
            c['name'] in ('read', 'glob') for c in reviewer_calls) if children else None,
        'every_project_change_matches_a_parent_write': not unexplained,
        'no_reviewer_permission_request_or_form': not any(
            (e['kind'] == 'permission' and e['session'] != parent) or e['kind'] == 'form-from-reviewer' for e in operator)
        if children else None,
        'every_completed_review_passed_the_guard_read_check': all(
            not d['guard_incomplete_notice'] for d in completed) if completed else None,
        'independent_recount_agrees_with_guard': all(
            (all(v is True for v in d['independent_read_coverage'].values()) != d['guard_incomplete_notice'])
            or any(v not in (True, False) for v in d['independent_read_coverage'].values()) for d in completed)
        if completed else None,
        'declared_reads_include_canonical_target_and_standard': all(not canonical(d) for d in children)
        if meta['workflow'].startswith('review') else None,
        'gates_presented': len(gates) + sum(1 for e in operator if e['kind'] == 'gate-cancelled'),
        'every_gate_had_exactly_one_question': all(g['questions_in_form'] == 1 for g in gates) if gates else None,
        'no_model_request_started_while_a_gate_waited': all(
            not g['model_requests_started_while_waiting'] for g in gates) if gates else None,
        'no_reviewer_before_first_gate_was_answered': (first_dispatch is None or first_gate_reply is None or
                                                       first_dispatch / 1000 > first_gate_reply)
        if meta['workflow'] == 'brainstorm' else None,
    }
    return {
        'run': run.name, 'workflow': meta['workflow'], 'status': meta['status'], 'model': meta['model'],
        'opencode': meta['opencode'], 'duration_seconds': round(meta['finished'] - meta['started']),
        'model_requests': {'total': len(requests), 'parent': len(parent_requests),
                           'reviewers': sum(1 for r in requests if kind(r) == 'reviewer'),
                           'reviewer_requests_matched_to_a_dispatch': sum(d['child_requests'] for d in dispatches),
                           'other': sum(1 for r in requests if kind(r) == 'other'),
                           'http_errors': [r['seq'] for r in requests if r.get('status') != 200],
                           'served_models': sorted({str(r['response'].get('model')) for r in requests if r.get('status') == 200})},
        'checks': checks,
        'counts': {
            'dispatch_calls': len(dispatches), 'child_sessions': len(set(child_ids)),
            'completed': len(completed),
            # A dispatch the guard or the configuration refused, as opposed to a model stream that broke
            # while the call was still being written (no agent, nothing for the guard to judge).
            'rejected_before_start': [{'agent': d['agent'], 'error': d['error']} for d in dispatches
                                      if not d['child_session'] and 'provider.transport' not in d['outcome']],
            'dispatch_calls_lost_to_transport_errors': sum(
                1 for d in dispatches if not d['child_session'] and 'provider.transport' in d['outcome']),
            'guard_incomplete_notices': [{'agent': d['agent'], 'coverage': d['independent_read_coverage']}
                                         for d in completed if d['guard_incomplete_notice']],
            'by_agent': {a: sum(1 for d in children if d['agent'] == a) for a in sorted({d['agent'] for d in children})},
            'reviewer_tool_calls': {o: sum(1 for c in reviewer_calls if c['outcome'].split(':')[0] == o)
                                    for o in sorted({c['outcome'].split(':')[0] for c in reviewer_calls})},
            'reviewer_non_read_glob_calls': [c for d in dispatches for c in d['child_non_read_glob_calls']],
            'reviewer_denied_or_failed_calls': [c for c in reviewer_calls if c['outcome'] != 'completed'],
            'missing_canonical_reads': [{'agent': d['agent'], 'missing': canonical(d)} for d in children if canonical(d)],
            'reviewers_that_opened_an_AGENTS_md_themselves': sum(
                1 for d in children if set(d['markers_self_read']) & {'project', 'nested'}),
            'reviews_that_obeyed_a_self_read_AGENTS_md_rule': [
                {'agent': d['agent'], 'markers': d['markers_in_result_returned_to_parent']}
                for d in children if d['markers_in_result_returned_to_parent']],
            'parent_marker_passed_in_prompt_by_orchestrator': sum(1 for d in dispatches if 'parent' in d['markers_in_prompt']),
        },
        'parent': {
            'reads_through_symlinks_without_a_prompt': [
                t['input'].get('path') for t in parent_tools if t['name'] == 'read' and t['outcome'] == 'completed'
                and Path(str(t['input'].get('path'))).name in ('env-link.md', 'outside-link.md')],
            'tool_calls': {n: sum(1 for t in parent_tools if t['name'] == n) for n in sorted({t['name'] for t in parent_tools})},
            'not_completed': [t for t in parent_tools if t['outcome'] != 'completed'],
            'read_review_loop_skill': any(
                'egm-review-loop' in json.dumps(t['input']) for t in parent_tools if t['name'] in ('read', 'skill')),
            'skills_loaded': [t['input'].get('id') for t in parent_tools if t['name'] == 'skill'],
            'writes': sorted(relative_writes),
        },
        'operator': {
            'permissions': [{k: e[k] for k in ('action', 'resources', 'decision', 'why')} for e in operator if e['kind'] == 'permission'],
            'chat_replies': sum(1 for e in operator if e['kind'] == 'chat-reply'),
            'cancelled_gates': [e['fields'] for e in operator if e['kind'] == 'gate-cancelled'],
        },
        'gates': gates, 'artifacts': produced, 'project_changes': changes, 'unexplained_changes': unexplained,
        'dispatches': dispatches,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('run', nargs='+')
    args = parser.parse_args()
    for run in args.run:
        result = analyze(Path(run))
        (Path(run) / 'analysis.json').write_text(json.dumps(result, indent=2) + '\n')
        brief = {k: v for k, v in result.items() if k not in ('dispatches', 'gates', 'project_changes')}
        print(json.dumps(brief, indent=2))


if __name__ == '__main__':
    main()
