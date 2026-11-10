"""Show the question a --human run is waiting on, or answer it.

  answer.py <run-dir>              print the pending question
  answer.py <run-dir> 1            choose option 1
  answer.py <run-dir> "my words"   answer in your own words (gates accept write-ins)
"""

import json
from pathlib import Path
import sys


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    run = Path(sys.argv[1])
    try:
        pending = json.loads((run / 'pending.json').read_text())
    except OSError:
        sys.exit('Nothing is waiting for an answer.')
    if len(sys.argv) == 2:
        print(json.dumps(pending, indent=2, ensure_ascii=False))
        return
    (run / 'answer.json').write_text(json.dumps({'id': pending['id'], 'answer': ' '.join(sys.argv[2:])}) + '\n')
    print(f'answered {pending["kind"]} #{pending["id"]}')


if __name__ == '__main__':
    main()
