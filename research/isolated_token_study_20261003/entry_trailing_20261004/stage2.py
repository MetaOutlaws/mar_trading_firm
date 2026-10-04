"""Stage 2 entry discovery. Eighteen configs, then a freeze. No exits here.

Rules have no fitted weights. The logistic model is fit only inside each
training fold, scored only on that fold's test rows, and never shuffled.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from entry_trailing_20261004.budget import (
    FEATURE_COLUMNS, FOLDS, LABEL_HORIZON, MODEL_C, MODEL_MIN_CLASS,
    MODEL_PROBABILITY, PURGE_HOURS, TOKENS, hurdle, side_name, slippage_rate,
)
from entry_trailing_20261004.execution import (
    FundingBook, decluster_times, fixed_horizon_trade, passes_screen, score_trades,
)
from entry_trailing_20261004.features import atr_price, bars_15m, compute_features, rule_mask

DISCOVERY_START = pd.Timestamp('2022-01-01', tz='UTC')
DISCOVERY_END = pd.Timestamp('2025-01-01', tz='UTC')
VALIDATION_END = pd.Timestamp('2026-01-01', tz='UTC')
PURGE = pd.Timedelta(hours=PURGE_HOURS)
LABEL = pd.Timedelta(hours=4)


def stamp(text: str) -> pd.Timestamp:
    return pd.Timestamp(text, tz='UTC')


def train_mask(times: pd.DatetimeIndex, train_start: str, train_end: str) -> np.ndarray:
    """T is trainable only when its 24-hour purge ends at or before train_end."""
    start = stamp(train_start)
    end = stamp(train_end)
    values = pd.DatetimeIndex(times)
    return np.asarray((values >= start) & (values + PURGE <= end))


def test_mask(times: pd.DatetimeIndex, test_start: str, test_end: str) -> np.ndarray:
    """Test rows need a full 4-hour label inside the fold."""
    start = stamp(test_start)
    end = stamp(test_end)
    values = pd.DatetimeIndex(times)
    return np.asarray((values >= start) & (values + LABEL <= end))


def rule_discovery_mask(times: pd.DatetimeIndex) -> np.ndarray:
    values = pd.DatetimeIndex(times)
    return np.asarray((values >= DISCOVERY_START) & (values + LABEL <= DISCOVERY_END))


def rule_validation_mask(times: pd.DatetimeIndex) -> np.ndarray:
    values = pd.DatetimeIndex(times)
    return np.asarray((values >= DISCOVERY_END) & (values + LABEL <= VALIDATION_END))


def fit_scaler(features: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Training-fold mean and sample standard deviation. A zero scale becomes 1."""
    mu = features.mean(axis=0)
    sd = features.std(axis=0, ddof=1)
    sd = np.where(~np.isfinite(sd) | (sd < 1e-12), 1.0, sd)
    return mu, sd


def apply_scaler(features: np.ndarray, mu: np.ndarray, sd: np.ndarray) -> np.ndarray:
    return (features - mu) / sd


def fit_l2_logistic(features: np.ndarray, labels: np.ndarray, C: float = MODEL_C):
    """Newton / IRLS. Intercept is the last coefficient and is not penalized.

    Returns (coef, status). coef is None when the fold is refused.
    """
    labels = labels.astype(float)
    n_pos = int((labels == 1).sum())
    n_neg = int((labels == 0).sum())
    if n_pos < MODEL_MIN_CLASS or n_neg < MODEL_MIN_CLASS:
        return None, 'failed_class_count'
    n, p = features.shape
    weights = np.where(labels == 1, n / (2 * n_pos), n / (2 * n_neg))
    design = np.column_stack([features, np.ones(n)])
    coef = np.zeros(p + 1)
    penalty = np.ones(p + 1)
    penalty[-1] = 0.0
    status = 'ok_max_iter'
    for _ in range(50):
        eta = np.clip(design @ coef, -40, 40)
        prob = np.clip(1 / (1 + np.exp(-eta)), 1e-12, 1 - 1e-12)
        grad = C * (design.T @ (weights * (prob - labels)))
        grad[:-1] += coef[:-1]
        curvature = weights * prob * (1 - prob)
        hess = C * (design.T @ (design * curvature[:, None]))
        hess.flat[::p + 2] += penalty
        try:
            step = np.linalg.solve(hess, grad)
        except np.linalg.LinAlgError:
            hess.flat[::p + 2] += 1e-8
            try:
                step = np.linalg.solve(hess, grad)
            except np.linalg.LinAlgError:
                return None, 'failed_fit'
        coef = coef - step
        if float(np.max(np.abs(step))) < 1e-8:
            status = 'ok'
            break
    return coef, status


def predict_proba(coef: np.ndarray, features: np.ndarray) -> np.ndarray:
    design = np.column_stack([features, np.ones(len(features))])
    eta = np.clip(design @ coef, -40, 40)
    return 1 / (1 + np.exp(-eta))


def _cost_times(pack, times, side: int, slip: float) -> pd.DataFrame:
    if len(times) == 0:
        return pd.DataFrame()
    rows = []
    pos = pack['position']
    for ts in times:
        i = pos[ts]
        row = fixed_horizon_trade(
            pack['index'], pack['open'], pack['high'], pack['low'], pack['close'],
            int(i), side, slip, pack['funding'], LABEL_HORIZON,
        )
        if row is not None:
            rows.append(row)
    return pd.DataFrame(rows)


def _prepare(candles: pd.DataFrame, funding: pd.DataFrame) -> dict:
    bars = bars_15m(candles)
    features = compute_features(bars)
    usable = features.dropna()
    times = usable.index.intersection(candles.index)
    usable = usable.loc[times]
    position_all = candles.index.get_indexer(times)
    ok = (position_all >= 0) & (position_all + LABEL_HORIZON <= len(candles.index))
    times = pd.DatetimeIndex(times[ok])
    usable = usable.loc[times]
    position = dict(zip(times, position_all[ok]))
    return {
        'features': usable,
        'times': times,
        'position': position,
        'index': candles.index,
        'open': candles['open'].to_numpy(dtype=float),
        'high': candles['high'].to_numpy(dtype=float),
        'low': candles['low'].to_numpy(dtype=float),
        'close': candles['close'].to_numpy(dtype=float),
        'funding': FundingBook(candles, funding),
        'atr': atr_price(bars, usable),
        'matrix': usable[list(FEATURE_COLUMNS)].to_numpy(dtype=float),
    }


def _quoted_label(pack, side: int, token: str) -> np.ndarray:
    pos = np.array([pack['position'][ts] for ts in pack['times']], dtype=int)
    entry = pack['open'][pos]
    exit_close = pack['close'][pos + LABEL_HORIZON - 1]
    signed = side * (exit_close / entry - 1)
    return (signed > hurdle(token)).astype(float)


def _summarize_config(experiment_id, token, side, family, spec, discovery_sets, validation_sets, notes: str) -> dict:
    """discovery_sets / validation_sets map cost mode -> trade frame on the declustered sample."""
    base_d = score_trades(discovery_sets['comparable'])
    base_v = score_trades(validation_sets['comparable'])
    stress_d = score_trades(discovery_sets['stress'])
    stress_v = score_trades(validation_sets['stress'])
    desk_d = score_trades(discovery_sets['desk'])
    desk_v = score_trades(validation_sets['desk'])
    return {
        'experiment_id': experiment_id,
        'token': token,
        'side': side_name(side),
        'family': family,
        'spec': spec,
        'trades_discovery': base_d['trades'],
        'mean_discovery': base_d['mean'],
        'pf_discovery': base_d['pf'],
        'trades_validation': base_v['trades'],
        'mean_validation': base_v['mean'],
        'pf_validation': base_v['pf'],
        'stress_mean_discovery': stress_d['mean'],
        'stress_mean_validation': stress_v['mean'],
        'desk_mean_discovery': desk_d['mean'],
        'desk_mean_validation': desk_v['mean'],
        'passes_screen': passes_screen(base_d, base_v, stress_d, stress_v),
        'notes': notes,
        '_discovery_score': base_d,
        '_validation_score': base_v,
    }


def _modes(token: str):
    return ('comparable', 'stress', 'desk')


def _evaluate_signal_set(pack, token, side, discovery_times, validation_times) -> tuple[dict, dict]:
    discovery = {}
    validation = {}
    for mode in _modes(token):
        slip = slippage_rate(token, mode)
        d_kept = decluster_times(discovery_times, LABEL_HORIZON)
        v_kept = decluster_times(validation_times, LABEL_HORIZON)
        discovery[mode] = _cost_times(pack, d_kept, side, slip)
        validation[mode] = _cost_times(pack, v_kept, side, slip)
    return discovery, validation


def choose_frozen(rows: list[dict]) -> dict[str, str | None]:
    """At most one id per token. Rank is discovery mean, then identifier."""
    chosen = {token: None for token in TOKENS}
    for token in TOKENS:
        pool = [row for row in rows if row['token'] == token and row['passes_screen']]
        if not pool:
            continue
        pool.sort(key=lambda row: (-row['mean_discovery'], row['experiment_id']))
        chosen[token] = pool[0]['experiment_id']
    return chosen


def _model_signals(pack, token, side):
    """Out-of-fold fires. 2022 is not scored. Each fold fits its own scaler and weights."""
    labels = _quoted_label(pack, side, token)
    times = pack['times']
    matrix = pack['matrix']
    fires = {'discovery': [], 'validation': [], 'status': []}
    for name, train_start, train_end, test_start, test_end in FOLDS:
        tr = train_mask(times, train_start, train_end)
        te = test_mask(times, test_start, test_end)
        if int(tr.sum()) == 0 or int(te.sum()) == 0:
            fires['status'].append(f'{name}:empty')
            continue
        mu, sd = fit_scaler(matrix[tr])
        coef, status = fit_l2_logistic(apply_scaler(matrix[tr], mu, sd), labels[tr])
        fires['status'].append(f'{name}:{status}')
        if coef is None:
            continue
        proba = predict_proba(coef, apply_scaler(matrix[te], mu, sd))
        chosen = times[te][proba >= MODEL_PROBABILITY]
        if name == 'fold_2025':
            fires['validation'].extend(list(chosen))
        else:
            fires['discovery'].extend(list(chosen))
    return fires


def research_entries(candles: pd.DataFrame, funding: pd.DataFrame, token: str) -> dict:
    """Fit and score every pre-registered entry for one token. No 2026 path."""
    pack = _prepare(candles, funding)
    rows = []
    signals = {}
    frames = {}
    for side_label, side in (('long', 1), ('short', -1)):
        for family in ('compression', 'fade'):
            mask = rule_mask(pack['features'], family, side).to_numpy()
            fired = pack['times'][mask]
            discovery_times = fired[rule_discovery_mask(fired)]
            validation_times = fired[rule_validation_mask(fired)]
            discovery, validation = _evaluate_signal_set(
                pack, token, side, discovery_times, validation_times,
            )
            experiment_id = f'rule_{family}_{token}_{side_label}'
            rows.append(_summarize_config(
                experiment_id, token, side, f'rule_{family}', family,
                discovery, validation, 'gate uses declustered 4h fixed-horizon net',
            ))
            signals[experiment_id] = {
                'side': side,
                'discovery': pd.DatetimeIndex(discovery_times),
                'validation': pd.DatetimeIndex(validation_times),
                'atr': pack['atr'],
            }
            frames[experiment_id] = {'discovery': discovery, 'validation': validation}
        model = _model_signals(pack, token, side)
        discovery, validation = _evaluate_signal_set(
            pack, token, side, pd.DatetimeIndex(model['discovery']), pd.DatetimeIndex(model['validation']),
        )
        experiment_id = f'model_l2_{token}_{side_label}'
        rows.append(_summarize_config(
            experiment_id, token, side, 'model_l2', 'l2_C1_p60',
            discovery, validation, 'folds ' + ','.join(model['status']),
        ))
        signals[experiment_id] = {
            'side': side,
            'discovery': pd.DatetimeIndex(model['discovery']),
            'validation': pd.DatetimeIndex(model['validation']),
            'atr': pack['atr'],
        }
        frames[experiment_id] = {'discovery': discovery, 'validation': validation}
    return {'rows': rows, 'signals': signals, 'frames': frames}
