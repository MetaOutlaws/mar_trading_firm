"""SEEN 2022–2025 IC and I planning inputs at desk031.

These numbers are planning inputs only. They are not evidence and they are
not for promotion. Garwe's rule is applied as written and is not tuned: an
effect under 2x breakeven is REJECT at LOCK. Exactly 2x is not a reject.

The effect in that rule is the mean weekly gross IC-minus-I P&L. Breakeven
gross per week is the mean weekly cost drag of that same difference. Weekly
SD, MDE, and power describe the net IC-minus-I stream, which is the binding
statistic. N for MDE and power is 30. Alpha is one-sided 0.05 and the power
target inside the MDE is 80%. Those constants are the planning rule, not a
search.

No fetch. A missing tape is NOT_STAGED and is not a REJECT.
"""
from __future__ import annotations

import math
import statistics

from .allocation import membership, planned_notional
from .config import frozen_config
from .families import admit_prices, bar_hit
from .strategy import COSTS, FEE
from .tape import HOUR_MS, TapeNotStaged, iso_week, load_tape, tape_dir

N = 30
ALPHA = 0.05
POWER_TARGET = 0.80
# Inverse normal of 0.95 and 0.80. Checked against the normal cdf in tests.
Z_ALPHA = 1.6448536269514722
Z_BETA = 0.8416212335729143
REJECT_MULTIPLE = 2.0
DAY_MS = 24 * HOUR_MS
_SOURCE_RANK = {'H': 0, 'B': 1, 'C3': 2}

_LABELS = dict(
    label='SEEN',
    role='planning_inputs_only',
    not_evidence=True,
    not_for_promotion=True,
    scored_as_promotion=False,
    rules_tuned=False,
    promotion_authorized=False,
    window='2022-01-01T00:00:00Z..2025-12-31T23:00:00Z',
    cost='desk031',
    books=('I', 'IC'),
    n=N,
    alpha_one_sided=ALPHA,
    power_target=POWER_TARGET,
    reject_if_effect_under_multiple_of_breakeven=REJECT_MULTIPLE,
    reject_is_strict=True,
    reject_rule='An effect under 2x breakeven means REJECT at LOCK.',
    effect_definition='mean weekly gross IC-minus-I P&L, USDT',
    breakeven_definition='mean weekly cost drag of IC-minus-I, USDT',
    weekly_sd_definition='sample SD (n-1) of weekly net IC-minus-I, missing weeks 0',
    execution_basis='next_bar_open_plus_frozen_desk031_slip',
    h_path='hourly F111 gate filled at the next hour open; minute retest is not on the tape',
    funding='omitted_not_on_tape',
    same_bar_stop_and_target='stop',
    per_leg_cost=FEE + COSTS['desk031'][0],
)


def norm_cdf(z: float) -> float:
    return 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))


def mde(sd: float, *, scale: float = 1.0) -> float:
    """Minimum detectable mean at N=30, one-sided 5%, 80% power."""
    if sd < 0 or not math.isfinite(sd):
        raise ValueError('SD is not a finite non-negative number')
    return (Z_ALPHA + Z_BETA) * sd * scale / math.sqrt(N)


def power_at(effect: float, sd: float) -> float | None:
    """One-sided power of a normal test of mean > 0. The effect is not folded."""
    if sd <= 0 or not math.isfinite(sd) or not math.isfinite(effect):
        return None
    return norm_cdf(-Z_ALPHA + effect * math.sqrt(N) / sd)


def lock_verdict(multiple: float | None) -> str:
    """REJECT only when the multiple is strictly under 2. Missing is not a reject."""
    if multiple is None or not math.isfinite(multiple):
        return 'UNAVAILABLE'
    if multiple < REJECT_MULTIPLE:
        return 'REJECT'
    return 'NOT_REJECT'


def _weeks_between(first_ms: int, last_ms: int) -> list[str]:
    weeks = []
    cursor = first_ms
    seen = set()
    while cursor <= last_ms:
        label = iso_week(cursor)
        if label not in seen:
            seen.add(label)
            weeks.append(label)
        cursor += DAY_MS
    last = iso_week(last_ms)
    if last not in seen:
        weeks.append(last)
    return weeks


def summarise(weekly_net: list[float], weekly_gross: list[float], weekly_cost: list[float],
              *, c3_stop_notional: float, c3_stop_exits: int, mean_equity: float) -> dict:
    """Planning metrics. The 2x rule reads gross effect over cost drag."""
    count = len(weekly_net)
    if count != len(weekly_gross) or count != len(weekly_cost) or count < 2:
        sd = None
    else:
        sd = statistics.stdev(weekly_net)
    mean_net = statistics.fmean(weekly_net) if count else None
    mean_gross = statistics.fmean(weekly_gross) if count else None
    breakeven = statistics.fmean(weekly_cost) if count else None
    if mean_gross is None or breakeven is None or breakeven <= 0:
        multiple = None
    else:
        multiple = mean_gross / breakeven
    if mean_equity <= 0 or count < 1:
        turnover = None
    else:
        turnover = c3_stop_notional / mean_equity / count
    sd_value = sd if sd is not None and math.isfinite(sd) else None
    return dict(
        **_LABELS,
        weeks=count,
        mean_weekly_net=mean_net,
        mean_weekly_gross=mean_gross,
        weekly_sd=sd_value,
        mde=None if sd_value is None else mde(sd_value),
        mde_at_2x_sd=None if sd_value is None else mde(sd_value, scale=2.0),
        power=None if sd_value is None or mean_net is None else power_at(mean_net, sd_value),
        power_at_2x_sd=(
            None if sd_value is None or mean_net is None else power_at(mean_net, 2.0 * sd_value)),
        stop_churn_turnover=turnover,
        stop_churn_exits_per_week=c3_stop_exits / count if count else None,
        c3_stop_exits=c3_stop_exits,
        cost_drag_per_week=breakeven,
        breakeven_gross_per_week=breakeven,
        effect_multiple_of_breakeven=multiple,
        verdict=lock_verdict(multiple),
    )


def _limits() -> dict:
    cfg = frozen_config()
    return dict(
        starting=float(cfg['starting_equity_usdt']),
        daily_loss=float(cfg['daily_realised_loss']),
        daily_entries=int(cfg['daily_entries']),
        max_positions=int(cfg['max_open_positions']),
        per_sector=int(cfg['per_sector']),
    )


def _bars(tape: dict) -> dict[str, dict[int, dict]]:
    out = {}
    for symbol, frames in tape.items():
        frame = frames['1h']
        out[symbol] = {
            int(row.open_time_ms): dict(
                open=float(row.open), high=float(row.high), low=float(row.low),
                close=float(row.close),
            )
            for row in frame.itertuples(index=False)
        }
    return out


def _settle(pos: dict, raw_exit: float, reason: str, exit_ms: int) -> dict:
    from .families import _pnl
    money = _pnl(pos['side'], pos['qty'], pos['entry_fill'], pos['raw_entry'], raw_exit, reason)
    return dict(
        symbol=pos['symbol'], source=pos['source'], side=pos['side'],
        entry_ms=pos['entry_ms'], exit_ms=exit_ms, reason=reason,
        net_usdt=money['net_usdt'], gross_usdt=money['gross_usdt'],
        cost_usdt=money['cost_usdt'], notional=money['notional'],
    )


def walk_book(name: str, intents: list[dict], bars: dict, limits: dict, sector_of) -> dict:
    """One book. Caps are the frozen desk counts. The six-loss timer is not on this bar clock."""
    times = sorted({stamp for frame in bars.values() for stamp in frame})
    if not times:
        raise ValueError('tape has no hourly bars')
    last_bar = {symbol: max(frame) for symbol, frame in bars.items() if frame}
    waiting = sorted(
        intents,
        key=lambda row: (row['entry_ms'], _SOURCE_RANK[row['source']], row['symbol'], row['uid']),
    )
    cursor = 0
    open_positions = []
    closed = []
    equity = limits['starting']
    week_equity = {}
    day = None
    entries_today = 0
    realised_today = 0.0

    def gross() -> float:
        return sum(pos['qty'] * pos['mark'] for pos in open_positions)

    def drop_closed(stamp: int, selected) -> None:
        nonlocal equity, realised_today
        kept = []
        for pos in open_positions:
            if not selected(pos):
                kept.append(pos)
                continue
            bar = bars[pos['symbol']].get(stamp)
            hit = None if bar is None else bar_hit(
                pos['side'], bar['open'], bar['high'], bar['low'], pos['stop'], pos['target'])
            if hit is None:
                if bar is not None:
                    pos['mark'] = bar['close']
                kept.append(pos)
                continue
            trade = _settle(pos, hit[1], hit[0], stamp)
            closed.append(trade)
            equity += trade['net_usdt']
            realised_today += trade['net_usdt']
        open_positions[:] = kept

    for stamp in times:
        this_day = stamp // DAY_MS
        if this_day != day:
            day = this_day
            entries_today = 0
            realised_today = 0.0
        # Positions opened on an earlier bar can exit on this one.
        drop_closed(
            stamp,
            lambda pos, stamp=stamp: pos['entry_ms'] != stamp and stamp in bars[pos['symbol']],
        )
        while cursor < len(waiting) and waiting[cursor]['entry_ms'] < stamp:
            cursor += 1
        batch = []
        while cursor < len(waiting) and waiting[cursor]['entry_ms'] == stamp:
            batch.append(waiting[cursor])
            cursor += 1
        held = {pos['symbol'] for pos in open_positions}
        for intent in batch:
            if not membership(name, intent['source'], filter_pass=False):
                continue
            if intent['symbol'] in held or intent['symbol'] not in bars or stamp not in bars[intent['symbol']]:
                continue
            if equity <= 0 or realised_today <= -limits['daily_loss'] * equity:
                continue
            if entries_today >= limits['daily_entries'] or len(open_positions) >= limits['max_positions']:
                continue
            sector = sector_of(intent['symbol'])
            if sum(pos['sector'] == sector for pos in open_positions) >= limits['per_sector']:
                continue
            prices = admit_prices(intent, bars[intent['symbol']][stamp]['open'])
            if prices is None:
                continue
            notional = planned_notional(
                name, intent['source'], equity, gross(), prices['loss_fraction'])
            if notional <= 0:
                continue
            qty = notional / prices['entry_fill']
            bar = bars[intent['symbol']][stamp]
            open_positions.append(dict(
                intent, **prices, qty=qty, sector=sector, mark=bar['close'],
            ))
            held.add(intent['symbol'])
            entries_today += 1
        drop_closed(stamp, lambda pos, stamp=stamp: pos['entry_ms'] == stamp)
        # A symbol's last bar ends a trade the stop and target did not.
        ending = [pos for pos in open_positions if last_bar.get(pos['symbol']) == stamp]
        for pos in ending:
            bar = bars[pos['symbol']][stamp]
            trade = _settle(pos, bar['close'], 'end', stamp)
            closed.append(trade)
            equity += trade['net_usdt']
            realised_today += trade['net_usdt']
        if ending:
            open_positions = [pos for pos in open_positions if last_bar.get(pos['symbol']) != stamp]
        week_equity[iso_week(stamp)] = equity
    return dict(closed=closed, equity=equity, week_equity=week_equity)


def _series(closed: list[dict], weeks: list[str]) -> dict[str, dict[str, float]]:
    buckets = {week: dict(net=0.0, gross=0.0, cost=0.0) for week in weeks}
    for trade in closed:
        week = iso_week(trade['exit_ms'])
        if week not in buckets:
            continue
        buckets[week]['net'] += trade['net_usdt']
        buckets[week]['gross'] += trade['gross_usdt']
        buckets[week]['cost'] += trade['cost_usdt']
    return buckets


def simulate(tape: dict, intents: list[dict], *, sector_of=None) -> dict:
    """IC and I at desk031. Intents come from the family modules unless a test injects them."""
    if sector_of is None:
        from .feed import sector as sector_of
    limits = _limits()
    bars = _bars(tape)
    times = sorted({stamp for frame in bars.values() for stamp in frame})
    weeks = _weeks_between(times[0], times[-1])
    ic = walk_book('IC', intents, bars, limits, sector_of)
    base = walk_book('I', intents, bars, limits, sector_of)
    ic_weeks = _series(ic['closed'], weeks)
    i_weeks = _series(base['closed'], weeks)
    net, gross, cost = [], [], []
    for week in weeks:
        net.append(ic_weeks[week]['net'] - i_weeks[week]['net'])
        gross.append(ic_weeks[week]['gross'] - i_weeks[week]['gross'])
        cost.append(ic_weeks[week]['cost'] - i_weeks[week]['cost'])
    stops = [trade for trade in ic['closed'] if trade['source'] == 'C3' and trade['reason'] == 'stop']
    equities = [ic['week_equity'][week] for week in weeks if week in ic['week_equity']]
    mean_equity = statistics.fmean(equities) if equities else limits['starting']
    report = summarise(
        net, gross, cost,
        c3_stop_notional=sum(trade['notional'] for trade in stops),
        c3_stop_exits=len(stops),
        mean_equity=mean_equity,
    )
    report['status'] = 'SIMULATED'
    report['no_2026_bars_read'] = True
    report['ran_on_real_bars'] = True
    return report


def not_staged_report(reason: str) -> dict:
    """No tape, so there is no effect and no REJECT."""
    return dict(
        **_LABELS,
        status='NOT_STAGED',
        reason=reason,
        verdict='NOT_STAGED',
        weeks=None,
        mean_weekly_net=None,
        mean_weekly_gross=None,
        weekly_sd=None,
        mde=None,
        mde_at_2x_sd=None,
        power=None,
        power_at_2x_sd=None,
        stop_churn_turnover=None,
        stop_churn_exits_per_week=None,
        c3_stop_exits=None,
        cost_drag_per_week=None,
        breakeven_gross_per_week=None,
        effect_multiple_of_breakeven=None,
        no_2026_bars_read=True,
        ran_on_real_bars=False,
    )


def run_default() -> dict:
    """Simulate only when CIPHER_FORWARD_TAPE_DIR points at a directory."""
    root = tape_dir()
    if root is None or not root.is_dir():
        return not_staged_report(
            'CIPHER_FORWARD_TAPE_DIR is not set to a parquet or CSV directory. '
            'No IC or I simulation was run. Nothing was fetched. No 2026 bars were read.')
    try:
        tape = load_tape(root)
    except TapeNotStaged as exc:
        return not_staged_report(str(exc))
    from .families import screen_inputs
    return simulate(tape, screen_inputs(tape)['book_intents'])


def evaluate_directory(root) -> dict:
    """One tape read and one signal pass for the clone screen and the planning sim."""
    from .clone_screen import score_prepared, unavailable_report
    from .families import screen_inputs
    try:
        tape = load_tape(root)
    except TapeNotStaged as exc:
        reason = str(exc)
        return dict(
            clone_screen=unavailable_report(reason),
            planning=not_staged_report(reason),
        )
    prepared = screen_inputs(tape)
    screen = score_prepared(prepared)
    screen['tape'] = str(root)
    plan = simulate(tape, prepared['book_intents'])
    plan['tape'] = str(root)
    return dict(clone_screen=screen, planning=plan)
