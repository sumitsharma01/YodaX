"""Give the scheduler an explicit outcome for a provisional source bar."""
import os
from pathlib import Path
import runpy
import sys
from .price_feed import PendingDailyClose


def main():
    module = sys.argv[1]
    sys.argv = sys.argv[1:]
    try:
        runpy.run_module(module, run_name='__main__')
    except PendingDailyClose as exc:
        print(str(exc), flush=True)
        summary = os.environ.get('GITHUB_STEP_SUMMARY')
        if summary:
            with Path(summary).open('a') as out:
                out.write(f'\n### Awaiting closing prices\n\n{exc}\n')
        return 75
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
