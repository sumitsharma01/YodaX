"""Bounded retries for idempotent scheduled workers; validation still fails closed."""
import subprocess
import sys
import time


def run(command, attempts=3, delay=30):
    for attempt in range(1, attempts + 1):
        result = subprocess.run(command, check=False)
        if result.returncode == 0:
            return 0
        if attempt < attempts:
            print(f'Worker failed (attempt {attempt}/{attempts}); retrying in {delay}s. '
                  'Previously saved forecasts remain unchanged.', flush=True)
            time.sleep(delay)
    return result.returncode


if __name__ == '__main__':
    if len(sys.argv) < 2:
        raise SystemExit('Usage: python -m backend.retry_job module [arguments]')
    raise SystemExit(run([sys.executable, '-m', *sys.argv[1:]]))
