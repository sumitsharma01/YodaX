"""Resumable source snapshots. No secrets or application database access."""
from datetime import datetime, timezone
from hashlib import sha256
from io import BytesIO
import json
from pathlib import Path
import zipfile
import pandas as pd
import requests


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')
    temporary.replace(path)


def collect_prices(symbols, start, end, root):
    """End is exclusive. Cache immutable raw responses by content digest."""
    import yfinance as yf
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    yf.set_tz_cache_location(str(root / 'yf-cache'))
    frames, coverage = [], []
    fetched = datetime.now(timezone.utc).isoformat()
    for symbol in symbols:
        try:
            raw = yf.Ticker(symbol).history(start=start, end=end, auto_adjust=False,
                                            actions=True, raise_errors=True, timeout=30)
            if raw.empty:
                raise ValueError('Empty response')
            raw.index = raw.index.tz_localize(None).normalize()
            payload = raw.to_csv().encode()
            digest = sha256(payload).hexdigest()
            folder = root / 'raw' / 'prices'
            folder.mkdir(parents=True, exist_ok=True)
            file = folder / f'{symbol.replace("=", "_")}-{digest[:16]}.csv'
            file.write_bytes(payload)
            frame = pd.DataFrame({'date': raw.index, 'symbol': symbol,
                'close': raw['Close'].to_numpy(), 'volume': raw['Volume'].to_numpy(),
                'split': raw.get('Stock Splits', pd.Series(0, index=raw.index)).to_numpy()})
            frames.append(frame)
            coverage.append(dict(symbol=symbol, status='collected', first=str(frame.date.min().date()),
                last=str(frame.date.max().date()), rows=len(frame), sha256=digest,
                raw_path=str(file), fetched_at=fetched, source='Yahoo Finance via yfinance',
                caveat='Retrospective vendor snapshot, not an archived point-in-time price feed.'))
        except Exception as exc:
            coverage.append(dict(symbol=symbol, status='failed', error=type(exc).__name__, message=str(exc)))
        print(symbol, coverage[-1]['status'], flush=True)
    write_json(root / 'price_coverage.json', coverage)
    if not frames:
        raise RuntimeError('No prices collected; see price_coverage.json')
    prices = pd.concat(frames, ignore_index=True)
    prices.to_parquet(root / 'prices.parquet', index=False)
    return prices, coverage


GDELT_COLUMNS = [0, 1, 7, 17, 26, 28, 29, 56, 57]
GDELT_NAMES = ['event_id', 'event_date', 'actor1_country', 'actor2_country',
               'event_code', 'root_code', 'quad_class', 'date_added', 'source_url']


def parse_gdelt(payload, archive_day, lag_days=2):
    """Use original daily v1 records consistently from Jan 2015.

    Archive date + conservative delay is a backtest availability assumption,
    not proof of original publication time. Never use event occurrence as availability.
    """
    with zipfile.ZipFile(BytesIO(payload)) as archive:
        names = archive.namelist()
        if len(names) != 1 or archive.getinfo(names[0]).file_size > 300_000_000:
            raise ValueError('Unexpected GDELT archive')
        with archive.open(names[0]) as stream:
            frame = pd.read_csv(stream, sep='\t', header=None, usecols=GDELT_COLUMNS,
                                names=None, dtype=str, keep_default_na=False)
    frame.columns = GDELT_NAMES
    frame = frame.drop_duplicates('event_id')
    frame['archive_day'] = pd.Timestamp(archive_day).normalize()
    frame['available_at'] = pd.Timestamp(archive_day, tz='UTC') + pd.Timedelta(days=lag_days)
    return frame


def collect_events(start, end, root, lag_days=2):
    """Explicit bounded date range; cached daily ZIPs make long backfills resumable."""
    if lag_days < 1:
        raise ValueError('Historical daily archives require at least one day availability lag')
    root = Path(root)
    folder = root / 'raw' / 'gdelt'
    folder.mkdir(parents=True, exist_ok=True)
    days, coverage = [], []
    for day in pd.date_range(start, end, inclusive='left'):
        stamp = day.strftime('%Y%m%d')
        file = folder / f'{stamp}.export.CSV.zip'
        url = f'https://data.gdeltproject.org/events/{stamp}.export.CSV.zip'
        try:
            if file.exists():
                payload = file.read_bytes()
            else:
                response = requests.get(url, timeout=(15, 120))
                response.raise_for_status()
                payload = response.content
            frame = parse_gdelt(payload, day.strftime('%Y-%m-%d'), lag_days)
            if not file.exists():
                temp = file.with_suffix('.tmp')
                temp.write_bytes(payload)
                temp.replace(file)
            normalized = root / 'events_daily'
            normalized.mkdir(exist_ok=True)
            frame.to_parquet(normalized / f'{stamp}.parquet', index=False)
            # Retain all normalized records on disk; model uses broad global context only.
            counts = frame.quad_class.value_counts()
            days.append(dict(archive_day=day, available_at=frame.available_at.iloc[0],
                verbal_cooperation=int(counts.get('1', 0)), material_cooperation=int(counts.get('2', 0)),
                verbal_conflict=int(counts.get('3', 0)), material_conflict=int(counts.get('4', 0)),
                event_total=len(frame)))
            coverage.append(dict(day=str(day.date()), status='collected', records=len(frame),
                source=url, sha256=sha256(payload).hexdigest(),
                fetched_at=datetime.now(timezone.utc).isoformat(), availability='archive day + configured lag'))
        except Exception as exc:
            coverage.append(dict(day=str(day.date()), status='failed', error=type(exc).__name__))
        print(stamp, coverage[-1]['status'], flush=True)
    for entry in coverage:
        write_json(root / 'coverage' / 'gdelt' / f"{entry['day']}.json", entry)
    write_json(root / 'event_coverage.json', coverage)
    if not days:
        raise RuntimeError('No GDELT days collected; see event_coverage.json')
    daily = pd.DataFrame(days).sort_values('available_at')
    if (root / 'events.parquet').exists():
        previous = pd.read_parquet(root / 'events.parquet')
        daily = pd.concat([previous, daily]).drop_duplicates('archive_day', keep='last').sort_values('available_at')
    daily.to_parquet(root / 'events.parquet.tmp', index=False)
    (root / 'events.parquet.tmp').replace(root / 'events.parquet')
    return daily, coverage
