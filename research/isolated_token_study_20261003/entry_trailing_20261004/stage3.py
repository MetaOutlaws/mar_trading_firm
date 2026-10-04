"""Stage 3 exit comparison on frozen entries only.

Paired mode resimulates every signal under each exit, even when holds overlap.
That comparison is not a portfolio. Chronological mode keeps one position and
is the trade list the screen would use. An empty freeze scores nothing.
"""

from __future__ import annotations

import pandas as pd

from entry_trailing_20261004.budget import TOKENS, slippage_rate
from entry_trailing_20261004.execution import exit_specs, run_entries, score_trades

PARTITIONS = {
    'discovery': (pd.Timestamp('2022-01-01', tz='UTC'), pd.Timestamp('2025-01-01', tz='UTC')),
    'validation': (pd.Timestamp('2025-01-01', tz='UTC'), pd.Timestamp('2026-01-01', tz='UTC')),
}


def _signals_for(bundle: dict, partition: str):
    key = 'discovery' if partition == 'discovery' else 'validation'
    return bundle[key]


def compare_exits(candles: pd.DataFrame, funding_book, token: str, entry_id: str, bundle: dict):
    """Four exits, three cost modes, two samplings. No extra exit parameters."""
    rows = []
    trades = {}
    side = bundle['side']
    atr = bundle['atr']
    for exit_name, spec in exit_specs().items():
        for partition, (start, end) in PARTITIONS.items():
            times = _signals_for(bundle, partition)
            for mode in ('comparable', 'stress', 'desk'):
                slip = slippage_rate(token, mode)
                for one_position, sampling in ((False, 'paired'), (True, 'chronological')):
                    frame = run_entries(
                        candles, funding_book, times, side, slip, spec, start, end,
                        atr_at=atr, one_position=one_position,
                    )
                    stats = score_trades(frame)
                    experiment_id = f's3_{token}_{entry_id}_{exit_name}'
                    rows.append({
                        'experiment_id': experiment_id,
                        'token': token,
                        'entry_id': entry_id,
                        'exit': exit_name,
                        'partition': partition,
                        'cost': mode,
                        'sampling': sampling,
                        'paired_signal_count': int(len(times)),
                        **{k: v for k, v in stats.items() if k != 'exit_reasons'},
                        'exit_reasons': stats['exit_reasons'],
                    })
                    trades[(experiment_id, partition, mode, sampling)] = frame
    return rows, trades


def run_stage3(tapes, funding_books, research: dict[str, dict], out) -> pd.DataFrame:
    """Score exits only for tokens whose Stage 2 freeze is non-null."""
    frozen = research['frozen']
    frames = []
    any_scored = False
    for token in TOKENS:
        entry_id = frozen.get(token)
        if not entry_id:
            continue
        any_scored = True
        rows, trades = compare_exits(
            tapes[token], funding_books[token], token, entry_id, research['signals'][token][entry_id],
        )
        frames.extend(rows)
        for key, frame in trades.items():
            experiment_id, partition, mode, sampling = key
            if frame.empty:
                continue
            export = frame.drop(columns=['exit_i'], errors='ignore').copy()
            export.insert(0, 'experiment_id', experiment_id)
            export.to_csv(
                out / f'{experiment_id}_{partition}_{mode}_{sampling}_trades.csv.gz', index=False,
            )
        print(f'stage3 {token} {entry_id}', flush=True)
    summary = pd.DataFrame(frames)
    summary.to_csv(out / 'stage3_summary.csv', index=False)
    if not any_scored:
        (out / 'stage3_NOT_SCORED.txt').write_text(
            'No Stage 2 config passed the pre-registered screen. '
            'The four exit specs were not applied to market entries.\n'
        )
    return summary
