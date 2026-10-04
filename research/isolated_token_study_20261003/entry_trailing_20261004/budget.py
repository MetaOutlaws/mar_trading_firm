"""Frozen budgets for the 2026-10-04 entry and trailing study.

Numbers here repeat EXECUTION_ADDENDUM.md. They are not a search space.
Do not append a threshold after seeing a return.
"""

from __future__ import annotations

TOKENS = ('BTCUSDT', 'ETHUSDT', 'SOLUSDT')
SIDES = (('long', 1), ('short', -1))
HORIZONS = (60, 240, 480, 1440)
BARRIERS = (0.01, 0.02, 0.03, 0.05)

# Comparable taker fee. Slippage lives in slippage_rate().
FEE = 0.00055
LABEL_HORIZON = 240
PURGE_HOURS = 24
MAX_HOLD_MINUTES = 1440
MODEL_C = 1.0
MODEL_PROBABILITY = 0.60
MODEL_MIN_CLASS = 50
SCREEN_MIN_TRADES = 50
SCREEN_MIN_PF = 1.15
MATCH_SEED = 20261004
BOOTSTRAP_REPS = 1000

# Six cache fingerprints from the 2026-10-04 empirical manifest.
FILE_SHA256 = {
    'BTCUSDT_1m.parquet': 'a6d3cf242680123f4bc3ca16cf88009d0567d5db65ab770270d98d6d6a9c7aa0',
    'BTCUSDT_funding.parquet': '8f72152a9e8dab4723c58904dcdea059d1b4484ac63bb9c3c93db3d98136ed2a',
    'ETHUSDT_1m.parquet': 'd14e7fca972102acbb215afa7681863e93cada9be5d296b0dc2a746cfa72a2ab',
    'ETHUSDT_funding.parquet': '8b95a6e358acb7a0f70a502baa31aded1feb10b407678cc01e64335b152108ef',
    'SOLUSDT_1m.parquet': '55a4c6a06700cfb4d8b1ba219b94a07fb2daaf96e2c4588a4042ae2a8e84eca6',
    'SOLUSDT_funding.parquet': '5e43787de674452d41a852bba85eee904e272aac7d052d91b9997bce4d4bdc45',
}
ARCHIVE_SHA256 = '344ac29b5b2ee2fe9ba5966026914489dc22dfaed75374fbe86316052da863dc'

FEATURE_COLUMNS = (
    'rv_24h', 'atr_pct', 'rel_volume', 'range_compression', 'trend',
    'dist_high', 'dist_low', 'hour_sin', 'hour_cos',
)

# Train end is exclusive in the sense T+24h <= train_end. Test is [start, end).
FOLDS = (
    ('fold_2023', '2022-01-01', '2023-01-01', '2023-01-01', '2024-01-01'),
    ('fold_2024', '2022-01-01', '2024-01-01', '2024-01-01', '2025-01-01'),
    ('fold_2025', '2022-01-01', '2025-01-01', '2025-01-01', '2026-01-01'),
)

EXIT_NAMES = ('fixed', 'trail', 'trail_atr', 'partial_trail')

LEDGER_COLUMNS = (
    'experiment_id', 'stage', 'token', 'side', 'family', 'spec', 'status',
    'trades_discovery', 'mean_discovery', 'pf_discovery',
    'trades_validation', 'mean_validation', 'pf_validation',
    'stress_mean_discovery', 'stress_mean_validation',
    'desk_mean_discovery', 'desk_mean_validation', 'notes',
)
OUTCOME_COLUMNS = LEDGER_COLUMNS[7:-1]


def side_name(side: int) -> str:
    if side == 1:
        return 'long'
    if side == -1:
        return 'short'
    raise ValueError(side)


def hurdle(token: str) -> float:
    """Comparable fee-plus-slippage round trip, before funding."""
    return 0.0031 if token == 'SOLUSDT' else 0.0021


def slippage_rate(token: str, mode: str) -> float:
    """mode is comparable, stress, or desk. Desk is the 31 bp disclosure."""
    if mode == 'desk':
        return 0.001
    base = 0.001 if token == 'SOLUSDT' else 0.0005
    if mode == 'comparable':
        return base
    if mode == 'stress':
        return base * 2
    raise ValueError(mode)


def stage1_ids() -> list[dict]:
    rows = []
    for token in TOKENS:
        for name, _side in SIDES:
            for horizon in HORIZONS:
                for barrier in BARRIERS:
                    pct = int(round(barrier * 100))
                    rows.append({
                        'experiment_id': f's1_{token}_{name}_{horizon}m_{pct}pct',
                        'stage': '1',
                        'token': token,
                        'side': name,
                        'family': 'descriptive',
                        'spec': f'{horizon}m_{pct}pct',
                        'notes': 'not a trading candidate',
                    })
    return rows


def stage2_ids() -> list[dict]:
    rows = []
    for token in TOKENS:
        for name, _side in SIDES:
            rows.append({
                'experiment_id': f'rule_compression_{token}_{name}',
                'stage': '2',
                'token': token,
                'side': name,
                'family': 'rule_compression',
                'spec': 'compression',
                'notes': 'gate uses declustered 4h fixed-horizon net',
            })
            rows.append({
                'experiment_id': f'rule_fade_{token}_{name}',
                'stage': '2',
                'token': token,
                'side': name,
                'family': 'rule_fade',
                'spec': 'fade',
                'notes': 'gate uses declustered 4h fixed-horizon net',
            })
            rows.append({
                'experiment_id': f'model_l2_{token}_{name}',
                'stage': '2',
                'token': token,
                'side': name,
                'family': 'model_l2',
                'spec': 'l2_C1_p60',
                'notes': 'gate uses declustered 4h fixed-horizon net',
            })
    return rows


def exit_template_ids() -> list[dict]:
    """Four exit specs. They are not crossed with entries until a freeze."""
    notes = 'scored only after a per-token freeze; otherwise unused'
    return [
        {'experiment_id': 'exit_fixed', 'stage': '3', 'token': '', 'side': '',
         'family': 'exit', 'spec': 'fixed', 'notes': notes},
        {'experiment_id': 'exit_trail', 'stage': '3', 'token': '', 'side': '',
         'family': 'exit', 'spec': 'trail', 'notes': notes},
        {'experiment_id': 'exit_trail_atr', 'stage': '3', 'token': '', 'side': '',
         'family': 'exit', 'spec': 'trail_atr', 'notes': notes},
        {'experiment_id': 'exit_partial_trail', 'stage': '3', 'token': '', 'side': '',
         'family': 'exit', 'spec': 'partial_trail', 'notes': notes},
    ]


def ledger_template_rows() -> list[dict]:
    rows = []
    for source in (stage1_ids(), stage2_ids(), exit_template_ids()):
        for row in source:
            full = {col: '' for col in LEDGER_COLUMNS}
            full.update(row)
            full['status'] = 'pre-registered'
            rows.append(full)
    return rows
