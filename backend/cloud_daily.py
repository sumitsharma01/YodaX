"""Calendar-gated cloud run with a database lock and post-run verification."""
import json
import pandas as pd
import exchange_calendars as xcals
from .core import connect, MODEL_REVISION, COMPANIES
from .storage import setting

def main():
    if setting('YODAX_STORAGE') != 'postgres':
        raise RuntimeError('Cloud job requires PostgreSQL storage')
    with connect() as guard:
        if not guard.execute('SELECT pg_try_advisory_lock(782942)').fetchone()[0]:
            print('Another forecast job is active; skipping.')
            return
        now = pd.Timestamp.now(tz='UTC')
        cal = xcals.get_calendar('XNYS')
        sessions = cal.sessions_in_range((now-pd.Timedelta(days=20)).date(),now.date())
        cutoff = [s for s in sessions if cal.session_close(s)+pd.Timedelta(hours=1)<=now][-1]
        target = str(cal.next_session(cutoff).date())
        saved = guard.execute('SELECT payload FROM dashboard WHERE id=1').fetchone()
        if saved and json.loads(saved['payload'])['cutoff'] >= str(cutoff.date()):
            print('Latest completed session already processed; skipping.')
            return
        if now >= cal.session_open(cal.next_session(cutoff)):
            print('Next session has already opened; skipping stale issuance.')
            return
        from .run import run
        run()
        with connect() as db:
            payload = json.loads(db.execute('SELECT payload FROM dashboard WHERE id=1').fetchone()[0])
            assert payload['cutoff'] == str(cutoff.date()) and payload['target'] == target
            assert payload['model_revision'] == MODEL_REVISION
            rows = db.execute("SELECT symbol FROM forecasts WHERE kind='prospective' AND target=? AND model_revision=?", (target,MODEL_REVISION)).fetchall()
            assert {r['symbol'] for r in rows} == {c['symbol'] for c in COMPANIES}
        print('Six cloud forecasts and model revision verified.')

if __name__ == '__main__':
    main()
