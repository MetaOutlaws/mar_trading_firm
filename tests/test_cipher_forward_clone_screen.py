"""Clone screen: Jaccard, SEEN weekly rho, and the 2026 bar refusal."""
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from research.cipher_forward.clone_screen import (
    COMPARATORS, REFUSAL_MS, BarsOnOrAfter2026, assert_no_2026_bars,
    entry_timestamp_jaccard, run_default, score_archive, score_comparator,
    weekly_pnl_rho,
)
from research.cipher_forward.tape import HARD_END_MS, BarAfterHardCap

ROOT = Path(__file__).resolve().parents[1]


def _ms(year, month, day):
    return int(datetime(year, month, day, tzinfo=timezone.utc).timestamp() * 1000)


def test_screen_refuses_bars_after_the_hard_cap_and_on_2026():
    # Exactly 23:00 UTC on the last day is inside the window.
    assert_no_2026_bars([{'t': HARD_END_MS}])
    with pytest.raises(BarAfterHardCap, match='23:00:00'):
        assert_no_2026_bars([{'t': HARD_END_MS + 1}])
    with pytest.raises(BarsOnOrAfter2026, match='2026-01-01'):
        assert_no_2026_bars([{'t': REFUSAL_MS}])
    with pytest.raises(BarsOnOrAfter2026):
        score_comparator(
            [{'symbol': 'BTCUSDT', 'entry_ms': _ms(2024, 1, 2)}],
            [{'symbol': 'BTCUSDT', 'entry_ms': _ms(2024, 1, 2)}],
            [{'exit_ms': _ms(2024, 1, 8), 'net_pnl': 1.}],
            [{'exit_ms': _ms(2024, 1, 8), 'net_pnl': 1.}],
            bars=[{'open_ms': _ms(2025, 12, 31), 'close_ms': REFUSAL_MS}])
    with pytest.raises(BarsOnOrAfter2026):
        entry_timestamp_jaccard(
            [{'symbol': 'BTCUSDT', 'entry_ms': REFUSAL_MS}], [])
    with pytest.raises(BarAfterHardCap):
        weekly_pnl_rho([{'exit_ms': HARD_END_MS + 1, 'net_pnl': 1.}], [])


def test_jaccard_and_rho_thresholds_are_disqualifiers():
    left = [
        {'symbol': 'BTCUSDT', 'entry_ms': _ms(2024, 1, 2)},
        {'symbol': 'ETHUSDT', 'entry_ms': _ms(2024, 1, 3)},
    ]
    same = list(left)
    half = [left[0]]
    wider = same + [{'symbol': 'SOLUSDT', 'entry_ms': _ms(2024, 1, 4)}]
    assert entry_timestamp_jaccard(left, same) == pytest.approx(1.0)
    assert entry_timestamp_jaccard(left, half) == pytest.approx(0.5)
    assert entry_timestamp_jaccard(left, wider) == pytest.approx(2 / 3)

    def trades(pnls, start):
        return [{'exit_ms': _ms(2024, 1, start + 7 * i), 'net_pnl': pnl} for i, pnl in enumerate(pnls)]

    matched = trades([1., 2., 3., 4.], 8)
    flipped = trades([4., 3., 2., 1.], 8)
    assert weekly_pnl_rho(matched, matched) == pytest.approx(1.0)
    assert weekly_pnl_rho(matched, flipped) == pytest.approx(-1.0)

    clone = score_comparator(left, same, matched, matched)
    assert clone['jaccard_verdict'] == 'FAIL'
    assert clone['rho_verdict'] == 'FAIL'
    assert clone['verdict'] == 'FAIL'
    assert clone['rho_label'] == 'SEEN'
    assert clone['rho_used_as_supporting_evidence'] is False
    assert clone['rho_used_in_case_for_the_edge'] is False
    assert clone['rho_used_for_promotion'] is False

    # 0.50 is the last passing Jaccard. Negative rho is not a clone.
    clear = score_comparator(left, half, matched, flipped)
    assert clear['jaccard_verdict'] == 'PASS'
    assert clear['rho_verdict'] == 'PASS'
    assert clear['verdict'] == 'PASS'


def test_missing_tape_is_not_staged_and_not_a_pass(monkeypatch):
    monkeypatch.delenv('CIPHER_FORWARD_TAPE_DIR', raising=False)
    report = run_default()
    assert report['status'] == 'NOT_STAGED'
    assert report['no_2026_bars_read'] is True
    assert 'No Jaccard or rho was computed' in report['reason']
    assert report['candidate_module'] == 'research/cipher_forward/strategy.py'
    assert list(report['comparators']) == [key for key, _label in COMPARATORS]
    for row in report['comparators'].values():
        assert row['verdict'] == 'UNAVAILABLE'
        assert row['jaccard'] is None and row['rho'] is None
        assert row['rho_label'] == 'SEEN'
        assert row['rho_used_for_promotion'] is False
    filing = (ROOT / 'docs/cipher-forward/v2.2_filing_pr172.md').read_text()
    assert 'not supporting evidence' in filing
    assert 'not used for promotion' in filing
    assert 'UNAVAILABLE' in filing


def test_archive_directory_scores_each_comparator(tmp_path):
    def dump(name, rows):
        (tmp_path / name).write_text(json.dumps(rows))

    entries = [{'symbol': 'BTCUSDT', 'entry_ms': _ms(2023, 6, 1)}]
    other = [{'symbol': 'ETHUSDT', 'entry_ms': _ms(2023, 6, 2)}]
    trades = [
        {'exit_ms': _ms(2023, 6, 5), 'net_pnl': 1.},
        {'exit_ms': _ms(2023, 6, 12), 'net_pnl': 2.},
        {'exit_ms': _ms(2023, 6, 19), 'net_pnl': 3.},
    ]
    dump('candidate_entries.json', entries)
    dump('candidate_trades.json', trades)
    dump('bars.json', [{'t': _ms(2025, 12, 31)}])
    for key, _label in COMPARATORS:
        dump(f'{key}_entries.json', other)
        dump(f'{key}_trades.json', trades)
    report = score_archive(tmp_path)
    assert report['status'] if 'status' in report else True
    for key, _label in COMPARATORS:
        row = report['comparators'][key]
        assert row['jaccard'] == pytest.approx(0.0)
        assert row['jaccard_verdict'] == 'PASS'
        assert row['rho'] == pytest.approx(1.0)
        assert row['rho_verdict'] == 'FAIL'
        assert row['verdict'] == 'FAIL'
        assert row['rho_label'] == 'SEEN'
