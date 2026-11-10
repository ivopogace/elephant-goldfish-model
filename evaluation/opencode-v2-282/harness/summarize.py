"""Aggregate analysis.json files from several runs into one table (JSON and Markdown)."""

import argparse
import json
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('runs', nargs='+', help='run directories that contain analysis.json')
    parser.add_argument('--json', required=True)
    parser.add_argument('--markdown', required=True)
    args = parser.parse_args()
    rows, totals = [], {}
    for run in args.runs:
        a = json.loads((Path(run) / 'analysis.json').read_text())
        c, checks = a['counts'], a['checks']
        row = {
            'run': a['run'], 'workflow': a['workflow'], 'status': a['status'],
            'minutes': round(a['duration_seconds'] / 60, 1),
            'model_requests': a['model_requests']['total'],
            'gates': checks['gates_presented'],
            'dispatches': c['dispatch_calls'], 'reviews_completed': c['completed'],
            'rejected_before_start': len(c['rejected_before_start']),
            'transport_errors': c.get('dispatch_calls_lost_to_transport_errors', 0),
            'guard_incomplete_notices': len(c['guard_incomplete_notices']),
            'reviewer_reads_and_globs_ok': c['reviewer_tool_calls'].get('completed', 0),
            'reviewer_calls_denied': sum(v for k, v in c['reviewer_tool_calls'].items() if k != 'completed'),
            'reviewer_calls_other_tools': len(c['reviewer_non_read_glob_calls']),
            'reviewers_that_opened_agents_md': c['reviewers_that_opened_an_AGENTS_md_themselves'],
            'reviews_carrying_agents_md_code': len(c['reviews_that_obeyed_a_self_read_AGENTS_md_rule']),
            'parent_symlink_reads': len(a['parent']['reads_through_symlinks_without_a_prompt']),
            'failed_checks': sorted(k for k, v in checks.items() if v is False),
        }
        rows.append(row)
        for key, value in row.items():
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                totals[key] = round(totals.get(key, 0) + value, 1)
    names = sorted({k for r in rows for k in json.loads((Path(args.runs[0]) / 'analysis.json').read_text())['checks']})
    matrix = {}
    for run in args.runs:
        a = json.loads((Path(run) / 'analysis.json').read_text())
        for name, value in a['checks'].items():
            matrix.setdefault(name, {})[a['run']] = value
    Path(args.json).write_text(json.dumps({'runs': rows, 'totals': totals, 'checks': matrix}, indent=2) + '\n')
    columns = ['run', 'workflow', 'status', 'minutes', 'model_requests', 'gates', 'dispatches', 'reviews_completed',
               'rejected_before_start', 'guard_incomplete_notices', 'reviewer_calls_denied',
               'reviewer_calls_other_tools', 'reviews_carrying_agents_md_code', 'parent_symlink_reads']
    lines = ['| ' + ' | '.join(c.replace('_', ' ') for c in columns) + ' |', '|' + ' --- |' * len(columns)]
    lines += ['| ' + ' | '.join(str(r[c]) for c in columns) + ' |' for r in rows]
    lines += ['| ' + ' | '.join(['**total**', '', ''] + [str(totals.get(c, '')) for c in columns[3:]]) + ' |', '']
    lines += ['| check | ' + ' | '.join(r['run'] for r in rows) + ' |', '|' + ' --- |' * (len(rows) + 1)]
    mark = lambda v: '–' if v is None else ('yes' if v is True else 'NO' if v is False else str(v) if not isinstance(v, dict)
                                              else ('yes' if all(v.values()) else 'NO'))
    for name in matrix:
        lines.append(f'| {name.replace("_", " ")} | ' + ' | '.join(mark(matrix[name].get(r['run'])) for r in rows) + ' |')
    Path(args.markdown).write_text('\n'.join(lines) + '\n')
    print('\n'.join(lines))


if __name__ == '__main__':
    main()
