"""Stage 1 descriptive barrier races. Not a trading system.

Same-minute races count as adverse. Failures stay in the sample.
Dense 15-minute decisions overlap; the horizon grid is the declustered count.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from entry_trailing_20261004.budget import (
    BARRIERS, BOOTSTRAP_REPS, FEATURE_COLUMNS, HORIZONS, MATCH_SEED, TOKENS,
)
from entry_trailing_20261004.features import bars_15m, compute_features


def barrier_table(open_, high, low, positions: np.ndarray, horizon: int, side: int) -> dict[float, dict]:
    """Race every barrier for one side. positions are minute indexes of T."""
    out = {
        p: {
            'race': np.empty(len(positions), dtype=object),
            'minutes_to_favourable': np.empty(len(positions), dtype=float),
            'mfe': np.empty(len(positions), dtype=float),
            'mae': np.empty(len(positions), dtype=float),
        }
        for p in BARRIERS
    }
    if len(positions) == 0:
        return out
    chunk = 1024
    for start in range(0, len(positions), chunk):
        pos = positions[start:start + chunk]
        offs = pos[:, None] + np.arange(horizon)[None, :]
        highs = high[offs]
        lows = low[offs]
        entry = open_[pos]
        mfe_long = highs.max(axis=1) / entry - 1
        mae_long = 1 - lows.min(axis=1) / entry
        for barrier in BARRIERS:
            if side == 1:
                fav_hit = highs >= (entry * (1 + barrier))[:, None]
                adv_hit = lows <= (entry * (1 - barrier))[:, None]
                mfe = mfe_long
                mae = mae_long
            else:
                fav_hit = lows <= (entry * (1 - barrier))[:, None]
                adv_hit = highs >= (entry * (1 + barrier))[:, None]
                mfe = mae_long
                mae = mfe_long
            fav_any = fav_hit.any(axis=1)
            adv_any = adv_hit.any(axis=1)
            first_fav = np.where(fav_any, fav_hit.argmax(axis=1), horizon)
            first_adv = np.where(adv_any, adv_hit.argmax(axis=1), horizon)
            race = np.full(len(pos), 'neither', dtype=object)
            favourable = (first_fav < first_adv) & (first_fav < horizon)
            # Equal offsets are the same minute: adverse is first.
            adverse = (first_adv <= first_fav) & (first_adv < horizon)
            race[favourable] = 'favourable_first'
            race[adverse] = 'adverse_first'
            sl = slice(start, start + len(pos))
            out[barrier]['race'][sl] = race
            out[barrier]['minutes_to_favourable'][sl] = np.where(favourable, first_fav, horizon)
            out[barrier]['mfe'][sl] = mfe
            out[barrier]['mae'][sl] = mae
    return out


def on_horizon_grid(times: pd.DatetimeIndex, horizon: int) -> np.ndarray:
    """True when T is on the UTC grid anchored at 2022-01-01 every `horizon` minutes."""
    anchor = pd.Timestamp('2022-01-01', tz='UTC')
    ns = times.as_unit('ns').asi8 - np.int64(anchor.value)
    minutes = ns // 60_000_000_000
    return (minutes % horizon) == 0


def weekly_hit_interval(times, hits, start, end, reps: int = BOOTSTRAP_REPS, seed: int = MATCH_SEED):
    """2.5/97.5 percent weekly-block interval for a hit rate. Empty weeks stay in."""
    if len(times) == 0:
        return None, None
    # Monday 00:00 UTC starts the block. Empty Mondays inside the partition stay in the resample.
    stamps = pd.DatetimeIndex(times).tz_convert('UTC')
    week = stamps.normalize() - pd.to_timedelta(stamps.dayofweek, unit='D')
    start_u = pd.Timestamp(start).tz_convert('UTC')
    end_u = pd.Timestamp(end).tz_convert('UTC') - pd.Timedelta(nanoseconds=1)
    first = start_u.normalize() - pd.Timedelta(days=int(start_u.dayofweek))
    last = end_u.normalize() - pd.Timedelta(days=int(end_u.dayofweek))
    weeks = pd.date_range(first, last, freq='7D', tz='UTC')
    if len(weeks) == 0:
        return None, None
    frame = pd.DataFrame({'hit': np.asarray(hits, dtype=float), 'week': week})
    grouped = frame.groupby('week', sort=False).agg(s=('hit', 'sum'), n=('hit', 'size'))
    grouped = grouped.reindex(weeks, fill_value=0.0)
    arr = grouped[['s', 'n']].to_numpy(dtype=float)
    rng = np.random.default_rng(seed)
    draws = rng.integers(0, len(arr), size=(reps, len(arr)))
    picked = arr[draws]
    totals = picked[:, :, 1].sum(axis=1)
    rates = np.divide(
        picked[:, :, 0].sum(axis=1), totals, out=np.full(reps, np.nan), where=totals > 0,
    )
    rates = rates[np.isfinite(rates)]
    if len(rates) == 0:
        return None, None
    low, high = np.quantile(rates, [0.025, 0.975])
    return float(low), float(high)


def assign_volatility_quartile(rv: pd.Series) -> pd.Series:
    """Descriptive quartiles inside one token and partition. Not a Stage 2 input."""
    valid = rv.dropna()
    if valid.nunique() < 2:
        return pd.Series(0, index=rv.index, dtype=float)
    bins = pd.qcut(valid, 4, labels=False, duplicates='drop')
    return bins.reindex(rv.index)


def match_effects(frame: pd.DataFrame, feature_columns, rng: np.random.Generator) -> dict:
    """1:1 match inside hour x volatility quartile. Event minus control means.

    Groups are walked in sorted (hour, quartile) order so the seed is stable.
    """
    if 'quartile' not in frame or frame.empty:
        return {'matched': 0, 'unmatched': int(frame['event'].sum()) if len(frame) else 0, 'effects': {}}
    known = frame.dropna(subset=['quartile'])
    unmatched = int(frame['event'].sum() - known['event'].sum())
    pairs_e = []
    pairs_c = []
    grouped = known.groupby(['hour', 'quartile'], sort=True)
    for _key, group in grouped:
        ev = group.loc[group['event']]
        ct = group.loc[~group['event']]
        n = min(len(ev), len(ct))
        if n == 0:
            unmatched += len(ev)
            continue
        if len(ev) > n:
            take = np.sort(rng.choice(len(ev), n, replace=False))
            unmatched += len(ev) - n
            ev = ev.iloc[take]
        if len(ct) > n:
            take = np.sort(rng.choice(len(ct), n, replace=False))
            ct = ct.iloc[take]
        pairs_e.append(ev)
        pairs_c.append(ct)
    if not pairs_e:
        return {'matched': 0, 'unmatched': int(unmatched), 'effects': {}}
    left = pd.concat(pairs_e)
    right = pd.concat(pairs_c)
    effects = {col: float(left[col].mean() - right[col].mean()) for col in feature_columns}
    return {'matched': int(len(left)), 'unmatched': int(unmatched), 'effects': effects}


def _eligible_positions(minute_index, decision_times, start, end, horizon: int):
    keep_t = []
    for ts in decision_times:
        if ts >= start and ts + pd.Timedelta(minutes=horizon) <= end:
            keep_t.append(ts)
    if not keep_t:
        return pd.DatetimeIndex([]), np.array([], dtype=int)
    times = pd.DatetimeIndex(keep_t)
    pos = minute_index.get_indexer(times)
    ok = (pos >= 0) & (pos + horizon <= len(minute_index))
    return times[ok], pos[ok]


def characterize(candles: pd.DataFrame, token: str, partitions: dict) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Summary rows and matched-effect rows for one token. No costs."""
    minute = candles
    features = compute_features(bars_15m(minute)).dropna()
    # Decision clock is the 15-minute close, which must exist as a minute open.
    decisions = features.index.intersection(minute.index)
    features = features.loc[decisions]
    open_ = minute['open'].to_numpy(dtype=float)
    high = minute['high'].to_numpy(dtype=float)
    low = minute['low'].to_numpy(dtype=float)
    summary_rows = []
    effect_rows = []
    # One RNG for the token, groups consumed in sorted cell order.
    rng = np.random.default_rng(MATCH_SEED)
    for part_name, (start, end) in partitions.items():
        # Quartiles describe the partition, including decisions a long horizon would drop.
        in_part = features.loc[(features.index >= start) & (features.index < end), 'rv_24h']
        quartiles = assign_volatility_quartile(in_part)
        for horizon in HORIZONS:
            times, pos = _eligible_positions(minute.index, decisions, start, end, horizon)
            if len(times) == 0:
                continue
            grid = on_horizon_grid(times, horizon)
            feat = features.loc[times]
            q = quartiles.reindex(times)
            for side_name, side in (('long', 1), ('short', -1)):
                races = barrier_table(open_, high, low, pos, horizon, side)
                for barrier, table in races.items():
                    pct = int(round(barrier * 100))
                    event = table['race'] == 'favourable_first'
                    cell_id = f's1_{token}_{side_name}_{horizon}m_{pct}pct'
                    hit_low, hit_high = weekly_hit_interval(times, event, start, end)
                    dense_rate = float(event.mean()) if len(event) else None
                    decl_rate = float(event[grid].mean()) if grid.any() else None
                    summary_rows.append({
                        'experiment_id': cell_id,
                        'token': token,
                        'partition': part_name,
                        'side': side_name,
                        'horizon_minutes': horizon,
                        'barrier': barrier,
                        'decisions': int(len(times)),
                        'favourable_first': int(event.sum()),
                        'adverse_first': int((table['race'] == 'adverse_first').sum()),
                        'neither': int((table['race'] == 'neither').sum()),
                        'dense_favourable_rate': dense_rate,
                        'dense_rate_week_p2_5': hit_low,
                        'dense_rate_week_p97_5': hit_high,
                        'declustered_decisions': int(grid.sum()),
                        'declustered_favourable_rate': decl_rate,
                        'median_mfe': float(np.median(table['mfe'])),
                        'median_mae': float(np.median(table['mae'])),
                    })
                    cell = feat.copy()
                    cell['event'] = event
                    cell['hour'] = np.asarray(times.hour)
                    cell['quartile'] = q.to_numpy()
                    matched = match_effects(cell, FEATURE_COLUMNS, rng)
                    effect = {
                        'experiment_id': cell_id,
                        'token': token,
                        'partition': part_name,
                        'matched': matched['matched'],
                        'unmatched_events': matched['unmatched'],
                    }
                    for col in FEATURE_COLUMNS:
                        effect[f'delta_{col}'] = matched['effects'].get(col)
                    effect_rows.append(effect)
    return pd.DataFrame(summary_rows), pd.DataFrame(effect_rows)


def run_stage1(tapes: dict[str, pd.DataFrame], partitions: dict, out) -> None:
    summaries = []
    effects = []
    for token in TOKENS:
        summary, effect = characterize(tapes[token], token, partitions)
        summaries.append(summary)
        effects.append(effect)
        print(f'stage1 {token} cells {len(summary)}', flush=True)
    pd.concat(summaries, ignore_index=True).to_csv(out / 'stage1_summary.csv', index=False)
    pd.concat(effects, ignore_index=True).to_csv(out / 'stage1_effects.csv', index=False)
