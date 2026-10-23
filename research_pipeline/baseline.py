"""Historical TimesFM inference with context-only windows and resumable cache."""
from hashlib import sha256
from pathlib import Path
import numpy as np
import pandas as pd
from .features import stock_windows


def timesfm_baselines(prices, config, root, only_latest=False):
    import timesfm
    import torch
    from huggingface_hub import snapshot_download
    from backend.core import MODEL_ID, MODEL_REVISION, DATA
    root = Path(root)
    cache = root / 'baseline_cache'
    cache.mkdir(parents=True, exist_ok=True)
    model = None
    rows = []
    horizon, context = config['horizon'], config['context']
    for symbol, frame, _ in stock_windows(prices, config):
        values = frame.close.to_numpy(float)
        pending = []
        indices = [len(frame)-1] if only_latest else range(context-1,len(frame))
        for index in indices:
            if index < context-1:
                continue
            window = values[index-context+1:index+1]
            splits = frame.split.iloc[index-context+1:index+1]
            if not np.isfinite(window).all() or (window <= 0).any() or splits.ne(0).any():
                continue
            date = frame.index[index]
            digest = sha256(window.astype('<f8').tobytes() + f'{MODEL_REVISION}:{horizon}:{context}'.encode()).hexdigest()
            file = cache / f'{digest}.npy'
            if file.exists():
                result = float(np.load(file, allow_pickle=False))
                rows.append(dict(symbol=symbol, date=date, baseline_return=result, model_revision=MODEL_REVISION, context_sha=digest, horizon_sessions=horizon, context_sessions=context))
            else:
                pending.append((date, window.copy(), digest, file))
        if pending and model is None:
            torch.set_num_threads(4)
            model_dir = snapshot_download(MODEL_ID, revision=MODEL_REVISION,
                local_dir=DATA/'model', allow_patterns=['*.json', '*.safetensors'])
            model = timesfm.TimesFM_2p5_200M_torch.from_pretrained(model_dir, torch_compile=False, local_files_only=True)
            model.compile(timesfm.ForecastConfig(max_context=context, max_horizon=max(32, horizon),
                per_core_batch_size=4, normalize_inputs=True, use_continuous_quantile_head=True,
                force_flip_invariance=True, infer_is_positive=True, fix_quantile_crossing=True))
        for offset in range(0, len(pending), 4):
            batch = pending[offset:offset+4]
            prediction, _ = model.forecast(horizon=horizon, inputs=[item[1] for item in batch])
            for item, predicted in zip(batch, prediction[:, horizon-1]):
                date, window, digest, file = item
                if not np.isfinite(predicted) or predicted <= 0:
                    raise ValueError('Invalid TimesFM prediction')
                result = float(predicted/window[-1]-1)
                with file.with_suffix('.tmp').open('wb') as stream:
                    np.save(stream, result, allow_pickle=False)
                file.with_suffix('.tmp').replace(file)
                rows.append(dict(symbol=symbol, date=date, baseline_return=result, model_revision=MODEL_REVISION, context_sha=digest, horizon_sessions=horizon, context_sessions=context))
            if offset % 100 == 0:
                print(f'{symbol}: {offset + len(batch)}/{len(pending)} new TimesFM forecasts', flush=True)
    if not rows:
        raise ValueError('No valid TimesFM contexts')
    result = pd.DataFrame(rows).sort_values(['date', 'symbol'])
    result.to_parquet(root / 'baselines.parquet', index=False)
    return result
