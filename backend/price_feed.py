"""Retry missing daily closes with a separate daily query, never an estimated price."""
import numpy as np
import pandas as pd


def daily_history(ticker, *, start, end, **kwargs):
    frame = ticker.history(start=start, end=end, **kwargs)
    if frame.empty or 'Close' not in frame:
        return frame
    dates = frame.index.tz_localize(None).normalize()
    bad = ~np.isfinite(frame['Close'].to_numpy(dtype=float))
    if not bad.any():
        return frame
    # A short query uses a different provider response/cache from the long history.
    # Only replace the final requested daily bar, never older gaps or valid values.
    last = dates[-1]
    if bad[:-1].any() or not bad[-1] or last != pd.Timestamp(end) - pd.Timedelta(days=1):
        return frame
    fresh = ticker.history(start=str((last-pd.Timedelta(days=7)).date()), end=end, **kwargs)
    if fresh.empty:
        return frame
    fresh_dates = fresh.index.tz_localize(None).normalize()
    replacement = fresh.loc[fresh_dates == last]
    fields = ['Open', 'High', 'Low', 'Close', 'Volume', 'Stock Splits']
    if len(replacement) != 1 or not set(fields).issubset(replacement):
        return frame
    values = replacement.iloc[0][fields].astype(float)
    if not np.isfinite(values).all() or (values[['Open','High','Low','Close']] <= 0).any() or values['Volume'] < 0:
        return frame
    if values['Low'] > min(values['Open'], values['Close']) or values['High'] < max(values['Open'], values['Close']):
        return frame
    result = frame.copy()
    # Replace the whole bar so OHLC, volume and actions remain from one response.
    if not set(frame.columns).issubset(replacement.columns):
        return frame
    result.iloc[-1] = replacement.iloc[0][frame.columns]
    print(f'Recovered daily bar for {last.date()} from a separate seven-day query.', flush=True)
    return result


class PendingDailyClose(RuntimeError):
    """The latest session's source bar is provisional; a later schedule must retry."""


def require_ready_close(frame, end, now=None):
    """Defer only one missing latest close, with a hard pre-open freshness deadline."""
    import exchange_calendars as xcals
    if frame.empty or 'Close' not in frame:
        return
    dates = frame.index.tz_localize(None).normalize()
    bad = ~np.isfinite(frame['Close'].to_numpy(dtype=float))
    if bad.sum() != 1 or not pd.isna(frame['Close'].iloc[-1]) or dates[-1] != pd.Timestamp(end)-pd.Timedelta(days=1):
        return
    # Never defer older corruption or missing/invalid volume and corporate actions.
    other = frame[['Volume', 'Stock Splits']].to_numpy(dtype=float)
    if not np.isfinite(other).all() or (other < 0).any() or (frame['Close'].dropna() <= 0).any():
        return
    cal = xcals.get_calendar('XNYS')
    day = dates[-1]
    now = pd.Timestamp.now(tz='UTC') if now is None else pd.Timestamp(now)
    if cal.is_session(day) and cal.session_close(day) <= now < cal.session_open(cal.next_session(day))-pd.Timedelta(hours=1):
        raise PendingDailyClose(f'Awaiting provider closing price for {day.date()}; existing forecasts retained. The next scheduled run will retry.')
