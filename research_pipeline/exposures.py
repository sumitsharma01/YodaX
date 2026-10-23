"""Source-backed, as-of country presence; never an estimate of causal impact."""
from hashlib import sha256
import json
from pathlib import Path
import numpy as np
import pandas as pd
from .collect import write_json

EXPOSURE_FEATURES = ['exposed_event_log_count_7d', 'exposed_conflict_share_7d',
    'exposed_sanctions_share_7d', 'exposed_incoming_sanctions_share_7d',
    'exposed_cooperation_share_7d', 'exposed_negotiation_halt_share_7d',
    'exposure_age_days']


def snapshot_for(symbol, cutoff, registry):
    available = [row for row in registry['snapshots'] if row['symbol'] == symbol
                 and pd.Timestamp(row['available_at']) <= cutoff
                 and (cutoff-pd.Timestamp(row['available_at'])).total_seconds()/86400 <= row['max_age_days']]
    return max(available, key=lambda row: pd.Timestamp(row['available_at'])) if available else None


def snapshot_key(snapshot):
    return sha256(json.dumps(snapshot, sort_keys=True).encode()).hexdigest()[:16]


def summarize_exposed(frame, countries):
    """Count each event once even when both actors belong to exposed countries."""
    selected = frame[frame.actor1_country.isin(countries) | frame.actor2_country.isin(countries)].drop_duplicates('event_id')
    code = selected.event_code.astype(str)
    return dict(total=len(selected), conflict=int(selected.quad_class.eq('4').sum()),
        sanctions=int(code.str.startswith('163').sum()),
        incoming_sanctions=int((code.str.startswith('163') & selected.actor2_country.isin(countries)).sum()),
        cooperation=int(selected.quad_class.eq('2').sum()),
        negotiation_halt=int(code.str.startswith('164').sum()))


def enrich_events(root, registry):
    """Reuse cached source records; save a wide daily table and a source audit."""
    root = Path(root)
    daily = pd.read_parquet(root/'events.parquet').copy()
    daily['archive_day'] = pd.to_datetime(daily.archive_day)
    audit, outputs = [], []
    # Build snapshot-specific aggregates so later disclosures never rewrite earlier features.
    for row in daily.itertuples():
        file = root/'events_daily'/f'{row.archive_day:%Y%m%d}.parquet'
        record = {'archive_day': row.archive_day}
        if not file.exists():
            outputs.append(record)
            continue
        frame = pd.read_parquet(file)
        for snapshot in registry['snapshots']:
            key = snapshot_key(snapshot)
            counts = summarize_exposed(frame, snapshot['countries'])
            record.update({f'{key}_{name}': value for name, value in counts.items()})
        audit.append(dict(archive_day=str(row.archive_day.date()), rows=len(frame),
            missing_actor_countries=int((frame.actor1_country.eq('') & frame.actor2_country.eq('')).sum()),
            missing_source_urls=int(frame.source_url.eq('').sum()),
            unique_source_urls=int(frame.source_url.nunique()), normalized_sha256=sha256(file.read_bytes()).hexdigest()))
        outputs.append(record)
    enriched = daily.merge(pd.DataFrame(outputs), on='archive_day', validate='one_to_one')
    enriched.to_parquet(root/'events-enriched.parquet', index=False)
    write_json(root/'exposure-audit.json', dict(registry=registry, archive_quality=audit,
        caveats=['Country actor match is not a company mention or proof of economic impact.',
                 'Source URL counts do not establish independent corroboration.',
                 'CAMEO 163 includes boycotts and embargoes as well as sanctions.',
                 'CAMEO 164 is halted negotiations, not an FTA status classifier.']))
    return enriched


def add_exposure_features(features, events, registry):
    result = []
    for row in features.itertuples():
        record = dict(symbol=row.symbol, date=row.date, exposure_known=0., exposure_coverage_7d=0.)
        record.update({column: np.nan for column in EXPOSURE_FEATURES})
        snapshot = snapshot_for(row.symbol, row.cutoff_at, registry)
        if snapshot is not None:
            key = snapshot_key(snapshot)
            fields = [f'{key}_{name}' for name in ['total','conflict','sanctions','incoming_sanctions','cooperation','negotiation_halt']]
            record['exposure_known'] = 1.
            record['exposure_age_days'] = (row.cutoff_at-pd.Timestamp(snapshot['available_at'])).total_seconds()/86400
            if events is not None and all(name in events for name in fields):
                subset = events[(events.available_at <= row.cutoff_at) & (events.available_at > row.cutoff_at-pd.Timedelta(days=7))]
                subset = subset.dropna(subset=fields)
                record['exposure_coverage_7d'] = len(subset)/7
                if len(subset) == 7:
                    sums = subset[fields].sum()
                    total = sums[f'{key}_total']
                    record['exposed_event_log_count_7d'] = np.log1p(total)
                    for category, column in [('conflict','exposed_conflict_share_7d'),('sanctions','exposed_sanctions_share_7d'),
                        ('incoming_sanctions','exposed_incoming_sanctions_share_7d'),('cooperation','exposed_cooperation_share_7d'),
                        ('negotiation_halt','exposed_negotiation_halt_share_7d')]:
                        record[column] = sums[f'{key}_{category}']/total if total else 0.
        result.append(record)
    return features.merge(pd.DataFrame(result), on=['symbol','date'],validate='one_to_one')


def export_review_examples(root, registry, limit_per_symbol=25):
    """Recent convenience sample for source review, NOT a precision estimate."""
    root = Path(root)
    daily = pd.read_parquet(root/'events.parquet').sort_values('archive_day', ascending=False)
    examples, seen = [], set()
    symbols = sorted({r['symbol'] for r in registry['snapshots']})
    for day in daily.itertuples():
        if all(sum(r['symbol'] == symbol for r in examples) >= limit_per_symbol for symbol in symbols):
            break
        path = root/'events_daily'/f'{day.archive_day:%Y%m%d}.parquet'
        if not path.exists():
            continue
        frame = pd.read_parquet(path)
        for symbol in symbols:
            remaining = limit_per_symbol-sum(r['symbol'] == symbol for r in examples)
            snapshot = snapshot_for(symbol, pd.Timestamp(day.available_at), registry)
            if remaining <= 0 or snapshot is None:
                continue
            countries = snapshot['countries']
            matched = frame[frame.actor1_country.isin(countries) | frame.actor2_country.isin(countries)]
            matched = matched[matched.event_code.str.startswith(('163','164')) | matched.quad_class.eq('4')]
            matched = matched[matched.source_url.str.startswith(('https://','http://'))].sort_values('event_id')
            selected = 0
            for event in matched.itertuples():
                identity = (symbol,event.event_id)
                if identity in seen:
                    continue
                seen.add(identity)
                examples.append(dict(symbol=symbol,archive_day=str(day.archive_day.date()),event_id=event.event_id,
                    actor1_country=event.actor1_country,actor2_country=event.actor2_country,event_code=event.event_code,
                    source_url=event.source_url,exposure_source=snapshot['source_url'],review_status='not_reviewed',
                    company_relevance='unknown',review_notes=''))
                selected += 1
                if selected >= min(remaining,3):
                    break
    result = pd.DataFrame(examples)
    result.to_csv(root/'event-relevance-review.csv',index=False)
    return result
