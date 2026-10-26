"""Hard window for the shared Bybit tape loader."""
import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import pytest

from research.cipher_forward.families import CANDIDATE_SPEC, COMPARATOR_SPECS
from research.cipher_forward.freeze import current_identity
from research.cipher_forward.tape import (
    HARD_END_MS, HOUR_MS, FOUR_HOUR_MS, TAPE_ENV, WINDOW_START_MS,
    BarAfterHardCap, BarBeforeWindow, BarsOnOrAfter2026, TapeRejected,
    assert_bar_timestamp, read_bar_file, required_symbols, tape_contract,
)

ROOT = Path(__file__).resolve().parents[1]
PRIMARY = 'f8894f0389cb844603e5d991290759d68f6be869a48f4081e1761805128149a2'


def _ms(year, month, day, hour=0):
    return int(datetime(year, month, day, hour, tzinfo=timezone.utc).timestamp() * 1000)


def _rows(start, step, count, *, price=100.0):
    rows = []
    for index in range(count):
        stamp = start + index * step
        rows.append(dict(
            open_time_ms=stamp, open=price, high=price + 1, low=price - 1,
            close=price, volume=2.0, turnover=3.0,
        ))
    return rows


def test_boundary_allows_the_last_hour_and_raises_after_it():
    assert_bar_timestamp(WINDOW_START_MS)
    assert_bar_timestamp(HARD_END_MS)
    assert HARD_END_MS == _ms(2025, 12, 31, 23)
    with pytest.raises(BarAfterHardCap, match='23:00:00'):
        assert_bar_timestamp(HARD_END_MS + 1)
    with pytest.raises(BarsOnOrAfter2026, match='2026-01-01'):
        assert_bar_timestamp(_ms(2026, 1, 1))
    with pytest.raises(BarBeforeWindow, match='2022-01-01'):
        assert_bar_timestamp(WINDOW_START_MS - 1)


def test_csv_and_parquet_use_the_same_cap(tmp_path):
    end = pd.DataFrame(_rows(HARD_END_MS - HOUR_MS, HOUR_MS, 2))
    csv_path = tmp_path / 'end.csv'
    end.to_csv(csv_path, index=False)
    loaded = read_bar_file(csv_path, '1h')
    assert int(loaded['open_time_ms'].iloc[-1]) == HARD_END_MS

    late = end.copy()
    late.loc[late.index[-1], 'open_time_ms'] = HARD_END_MS + 1
    late_path = tmp_path / 'late.csv'
    late.to_csv(late_path, index=False)
    with pytest.raises(BarAfterHardCap, match='23:00:00'):
        read_bar_file(late_path, '1h')

    parquet_path = tmp_path / 'end.parquet'
    end.to_parquet(parquet_path, index=False)
    assert int(read_bar_file(parquet_path, '1h')['open_time_ms'].iloc[-1]) == HARD_END_MS


def test_turnover_is_required_and_not_synthesised(tmp_path):
    rows = _rows(_ms(2024, 6, 1), FOUR_HOUR_MS, 2)
    frame = pd.DataFrame(rows).drop(columns=['turnover'])
    path = tmp_path / 'missing.csv'
    frame.to_csv(path, index=False)
    with pytest.raises(TapeRejected, match='turnover'):
        read_bar_file(path, '4h')


def test_contract_names_the_universe_and_the_modules():
    protocol = json.loads((ROOT / 'docs/cipher-forward/protocol.json').read_text())
    contract = tape_contract()
    assert contract['env'] == TAPE_ENV
    assert contract['symbols'] == protocol['universe']
    assert required_symbols() == tuple(protocol['universe'])
    assert contract['timeframes'] == ['1h', '4h']
    assert contract['columns'] == [
        'open_time_ms', 'open', 'high', 'low', 'close', 'volume', 'turnover']
    assert contract['fetches'] is False
    assert protocol['clone_screen']['comparator_modules']['R-target shorts'] == (
        'core/strategy/measured_move_break.py')
    assert protocol['clone_screen']['candidate_module'] == CANDIDATE_SPEC['path']
    for spec in COMPARATOR_SPECS:
        path = ROOT / spec['path']
        assert path.is_file(), spec['path']
        assert protocol['clone_screen']['comparator_modules'][spec['label']] == spec['path']
    assert current_identity()['primary_config_sha256'] == PRIMARY
    filing = (ROOT / 'docs/cipher-forward/v2.2_filing_pr172.md').read_text()
    assert 'measured_move_break.py' in filing
    assert 'donchian_n_fail_reversion.py' in filing
    assert 'NOT_STAGED' in filing
    assert 'under 2×' in filing and 'means REJECT at LOCK' in filing
