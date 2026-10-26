"""Clone / do-not-replicate screen for the 3R short.

Entry-timestamp Jaccard uses feature rows only: the set of (symbol, entry_ms)
pairs. Weekly P&L Spearman rho uses 2022-01-01..2025-12-31 outcomes and is
labelled SEEN. Rho is a disqualifier only. A value above 0.50 is FAIL. Rho is
not supporting evidence, not part of the case for the edge, and not an input
to promotion.

Any bar timestamp on or after 2026-01-01 UTC is refused. The screen does not
fetch market data.
"""
from __future__ import annotations

from datetime import datetime, timezone
import math
from pathlib import Path

# Inclusive start. The first refused instant is 2026-01-01 00:00:00 UTC.
WINDOW_START = datetime(2022, 1, 1, tzinfo=timezone.utc)
REFUSAL_AT = datetime(2026, 1, 1, tzinfo=timezone.utc)
WINDOW_START_MS = int(WINDOW_START.timestamp() * 1000)
REFUSAL_MS = int(REFUSAL_AT.timestamp() * 1000)

JACCARD_FAIL_ABOVE = 0.50
RHO_FAIL_ABOVE = 0.50
RHO_LABEL = 'SEEN'
RHO_ROLE = 'disqualifier_only'

# Display name is what the filing quotes. The key is the file prefix.
COMPARATORS = (
    ('r_target_shorts', 'R-target shorts'),
    ('breakout_fail_shorts', 'breakout-fail shorts'),
    ('outside_bar_fail', 'outside_bar_fail'),
    ('F111', 'F111'),
    ('BL8', 'BL8'),
)

# Private archives named by the cipher README. They are not in this checkout.
DEFAULT_ARCHIVE_ROOTS = (
    Path('/PRIVATE/mar_cipher_test_20261022'),
    Path('/PRIVATE/mar_3r_allocation_20261023'),
)

_TIME_KEYS = ('t', 'ts', 'time_ms', 'open_ms', 'close_ms', 'entry_ms', 'exit_ms')


class BarsOnOrAfter2026(ValueError):
    """A bar, entry, or outcome is on or after 2026-01-01 UTC."""


def assert_no_2026_bars(bars) -> None:
    """Refuse every bar whose timestamp is on or after 2026-01-01 UTC."""
    for bar in bars or ():
        stamps = _timestamps(bar)
        for stamp in stamps:
            if stamp >= REFUSAL_MS:
                raise BarsOnOrAfter2026(
                    f'bar timestamp {stamp} is on or after 2026-01-01 UTC')


def _timestamps(row) -> list[int]:
    if isinstance(row, bool):
        raise ValueError('timestamp is not a bool')
    if isinstance(row, (int, float)):
        return [int(row)]
    if isinstance(row, dict):
        found = [int(row[key]) for key in _TIME_KEYS if row.get(key) is not None]
        if not found:
            raise ValueError('row has no timestamp')
        return found
    raise ValueError('row is not a timestamp')


def _require_window(stamp: int, kind: str) -> None:
    """Keep rows inside 2022-01-01 inclusive through 2025-12-31 inclusive."""
    if stamp >= REFUSAL_MS:
        raise BarsOnOrAfter2026(f'{kind} timestamp {stamp} is on or after 2026-01-01 UTC')
    if stamp < WINDOW_START_MS:
        raise ValueError(f'{kind} timestamp {stamp} is before 2022-01-01 UTC')


def _entry_identity(row: dict) -> tuple:
    if 'symbol' not in row or row.get('entry_ms') is None:
        raise ValueError('entry row needs symbol and entry_ms')
    stamp = int(row['entry_ms'])
    _require_window(stamp, 'entry')
    return (str(row['symbol']), stamp)


def entry_timestamp_jaccard(left, right) -> float | None:
    """Jaccard of (symbol, entry_ms) sets. None when both sets are empty."""
    # Touching the rows also enforces the date bound before the sets are built.
    a = {_entry_identity(row) for row in left}
    b = {_entry_identity(row) for row in right}
    union = a | b
    if not union:
        return None
    return len(a & b) / len(union)


def _iso_week(ms: int) -> str:
    moment = datetime.fromtimestamp(ms / 1000, timezone.utc)
    year, week, _day = moment.isocalendar()
    return f'{year:04d}-W{week:02d}'


def _weekly_pnl(trades) -> dict[str, float]:
    """Sum net_pnl by the ISO week of exit_ms. Open rows are not outcomes."""
    totals: dict[str, float] = {}
    for row in trades:
        if row.get('exit_ms') is None or row.get('net_pnl') is None:
            raise ValueError('outcome row needs exit_ms and net_pnl')
        stamp = int(row['exit_ms'])
        _require_window(stamp, 'outcome')
        week = _iso_week(stamp)
        totals[week] = totals.get(week, 0.0) + float(row['net_pnl'])
    return totals


def _ranks(values: list[float]) -> list[float]:
    """Average ranks, 1-based, so ties do not depend on input order."""
    order = sorted(range(len(values)), key=lambda i: values[i])
    ranks = [0.0] * len(values)
    start = 0
    while start < len(values):
        stop = start
        while stop + 1 < len(values) and values[order[stop + 1]] == values[order[start]]:
            stop += 1
        # Rank positions start at 1. A tie takes the mean of those positions.
        average = (start + 1 + stop + 1) / 2
        for cursor in range(start, stop + 1):
            ranks[order[cursor]] = average
        start = stop + 1
    return ranks


def _pearson(xs: list[float], ys: list[float]) -> float | None:
    count = len(xs)
    mean_x = sum(xs) / count
    mean_y = sum(ys) / count
    numer = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys))
    spread_x = math.sqrt(sum((x - mean_x) ** 2 for x in xs))
    spread_y = math.sqrt(sum((y - mean_y) ** 2 for y in ys))
    if spread_x == 0 or spread_y == 0:
        return None
    return numer / (spread_x * spread_y)


def weekly_pnl_rho(left, right) -> float | None:
    """Spearman rho of paired weekly P&L. None when the rank correlation is undefined.

    Weeks present on only one side are paired with 0. Fewer than 3 weeks, or a
    constant series, has no rho. This number is SEEN and is only a disqualifier.
    """
    left_weeks = _weekly_pnl(left)
    right_weeks = _weekly_pnl(right)
    weeks = sorted(set(left_weeks) | set(right_weeks))
    if len(weeks) < 3:
        return None
    xs = [left_weeks.get(week, 0.0) for week in weeks]
    ys = [right_weeks.get(week, 0.0) for week in weeks]
    return _pearson(_ranks(xs), _ranks(ys))


def _threshold_verdict(value: float | None, limit: float) -> str:
    """PASS at or below the limit. Above the limit is FAIL. Missing is not a pass."""
    if value is None:
        return 'UNAVAILABLE'
    if value > limit:
        return 'FAIL'
    return 'PASS'


def _combine(jaccard_verdict: str, rho_verdict: str) -> str:
    if 'FAIL' in (jaccard_verdict, rho_verdict):
        return 'FAIL'
    if 'UNAVAILABLE' in (jaccard_verdict, rho_verdict):
        return 'UNAVAILABLE'
    return 'PASS'


def score_comparator(candidate_entries, comparator_entries, candidate_trades, comparator_trades, bars=()) -> dict:
    """One comparator. Bars are checked first so a 2026 bar never becomes a score."""
    assert_no_2026_bars(bars)
    jaccard = entry_timestamp_jaccard(candidate_entries, comparator_entries)
    rho = weekly_pnl_rho(candidate_trades, comparator_trades)
    jaccard_verdict = _threshold_verdict(jaccard, JACCARD_FAIL_ABOVE)
    rho_verdict = _threshold_verdict(rho, RHO_FAIL_ABOVE)
    return dict(
        jaccard=jaccard,
        jaccard_verdict=jaccard_verdict,
        jaccard_definition='Jaccard of (symbol, entry_ms) sets on 2022-01-01..2025-12-31',
        jaccard_fail_above=JACCARD_FAIL_ABOVE,
        rho=rho,
        rho_verdict=rho_verdict,
        rho_label=RHO_LABEL,
        rho_role=RHO_ROLE,
        rho_fail_above=RHO_FAIL_ABOVE,
        rho_used_as_supporting_evidence=False,
        rho_used_in_case_for_the_edge=False,
        rho_used_for_promotion=False,
        verdict=_combine(jaccard_verdict, rho_verdict),
    )


def _read_rows(path: Path):
    import json
    value = json.loads(path.read_text())
    if not isinstance(value, list):
        raise ValueError(f'{path.name} is not a list')
    return value


def score_archive(root: Path) -> dict:
    """Score a directory of JSON lists. Missing files stay UNAVAILABLE, not PASS."""
    root = Path(root)
    bars_path = root / 'bars.json'
    bars = _read_rows(bars_path) if bars_path.is_file() else []
    assert_no_2026_bars(bars)
    candidate_entries_path = root / 'candidate_entries.json'
    candidate_trades_path = root / 'candidate_trades.json'
    rows = {}
    for key, label in COMPARATORS:
        entries_path = root / f'{key}_entries.json'
        trades_path = root / f'{key}_trades.json'
        missing = [
            str(path.name) for path in (
                candidate_entries_path, candidate_trades_path, entries_path, trades_path)
            if not path.is_file()]
        if missing:
            rows[key] = dict(
                label=label, jaccard=None, rho=None, verdict='UNAVAILABLE',
                rho_label=RHO_LABEL, rho_role=RHO_ROLE,
                rho_used_as_supporting_evidence=False,
                rho_used_in_case_for_the_edge=False,
                rho_used_for_promotion=False,
                reason='missing ' + ', '.join(missing))
            continue
        scored = score_comparator(
            _read_rows(candidate_entries_path), _read_rows(entries_path),
            _read_rows(candidate_trades_path), _read_rows(trades_path), bars)
        scored['label'] = label
        rows[key] = scored
    return dict(
        window='2022-01-01..2025-12-31',
        refusal='bars on or after 2026-01-01 UTC',
        rho_label=RHO_LABEL,
        rho_role=RHO_ROLE,
        rho_statement=(
            'Weekly P&L rho is SEEN, already-seen in-sample. It is a disqualifier '
            'only: rho above 0.50 is FAIL. It is not supporting evidence, it is not '
            'part of the case for the edge, and it is not used for promotion.'
        ),
        comparators=rows,
    )


def unavailable_report(reason: str) -> dict:
    """No archive was scored. Do not invent a Jaccard, a rho, or a PASS."""
    rows = {
        key: dict(
            label=label, jaccard=None, rho=None, verdict='UNAVAILABLE',
            rho_label=RHO_LABEL, rho_role=RHO_ROLE,
            rho_used_as_supporting_evidence=False,
            rho_used_in_case_for_the_edge=False,
            rho_used_for_promotion=False,
            reason=reason,
        )
        for key, label in COMPARATORS
    }
    return dict(
        window='2022-01-01..2025-12-31',
        refusal='bars on or after 2026-01-01 UTC',
        rho_label=RHO_LABEL,
        rho_role=RHO_ROLE,
        rho_statement=(
            'Weekly P&L rho is SEEN, already-seen in-sample. It is a disqualifier '
            'only: rho above 0.50 is FAIL. It is not supporting evidence, it is not '
            'part of the case for the edge, and it is not used for promotion.'
        ),
        status='UNAVAILABLE',
        reason=reason,
        comparators=rows,
        no_2026_bars_read=True,
    )


def default_archive_root() -> Path | None:
    for root in DEFAULT_ARCHIVE_ROOTS:
        if root.is_dir():
            return root
    return None


def run_default() -> dict:
    """Score the private archive when it is mounted. Otherwise report UNAVAILABLE."""
    root = default_archive_root()
    if root is None:
        return unavailable_report(
            '2022-2025 feature and outcome archives are not in this checkout. '
            'The cipher README points at /PRIVATE paths that are not mounted. '
            'No Jaccard or rho was computed. No 2026 bars were read.')
    report = score_archive(root)
    report['archive'] = str(root)
    report['status'] = 'SCORED'
    return report
