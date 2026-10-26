"""W11S/C3 and the five comparator families, on one pre-2026 Bybit tape.

Each comparator is one module that already exists in this repo. Grids are not
searched: a sleeve runs at its own default parameters, with the side set to
SHORT where the module has a side. BL8 is the long rebound in bl8.py. There
is no module named r_target_shorts or breakout_fail_shorts.

R-target shorts is core/strategy/measured_move_break.py. That family is a
finished 0/12 skip-list code, and its target is the locked 1.0 measured-move
of the impulse. It is not the 2R price inside strategy.py, which is the same
C3 entry.

Breakout-fail shorts is core/strategy/donchian_n_fail_reversion.py. The module
header is a Garwe stamp lock. Defaults are n=10 and pierce_tol_atr=0.0, which
are the module's own endpoints, not a picked interior.

The minute F111 retest is not on a 1h/4h tape. F111 entries are the hourly
gate filled at the next hour's open.
"""
from __future__ import annotations

from dataclasses import replace
import math

import pandas as pd

from core.strategy.base import SignalSide
from core.strategy.donchian_n_fail_reversion import DonchianNFailReversionStrategy
from core.strategy.donchian_n_fail_reversion_params import DonchianNFailReversionParams
from core.strategy.f111_semantics import initial_brackets
from core.strategy.mar_f111_r12_extension_latefloor_v1 import (
    MarF111R12ExtensionLatefloorV1Strategy,
)
from core.strategy.measured_move_break import MeasuredMoveBreakParams, MeasuredMoveBreakStrategy
from core.strategy.outside_bar_fail_reversion import (
    OutsideBarFailReversionParams,
    OutsideBarFailReversionStrategy,
)

from .bl8 import decision as bl8_decision
from .bl8 import fill_gate as bl8_fill_gate
from .features import compute
from .strategy import FEE, HOUR, COSTS, fill_gate as c3_fill_gate, from_feature
from .tape import FOUR_HOUR_MS, HARD_END_MS, HOUR_MS, WINDOW_START_MS, iso_week

SLIP, STOP_SLIP = COSTS['desk031']

# Display name, key, import path, timeframe the family is run on.
COMPARATOR_SPECS = (
    dict(
        key='r_target_shorts',
        label='R-target shorts',
        module='core.strategy.measured_move_break',
        path='core/strategy/measured_move_break.py',
        timeframe='4h',
        side='SHORT',
    ),
    dict(
        key='breakout_fail_shorts',
        label='breakout-fail shorts',
        module='core.strategy.donchian_n_fail_reversion',
        path='core/strategy/donchian_n_fail_reversion.py',
        timeframe='4h',
        side='SHORT',
    ),
    dict(
        key='outside_bar_fail',
        label='outside_bar_fail',
        module='core.strategy.outside_bar_fail_reversion',
        path='core/strategy/outside_bar_fail_reversion.py',
        timeframe='4h',
        side='SHORT',
    ),
    dict(
        key='F111',
        label='F111',
        module='core.strategy.mar_f111_r12_extension_latefloor_v1',
        path='core/strategy/mar_f111_r12_extension_latefloor_v1.py',
        timeframe='1h',
        side='SHORT',
    ),
    dict(
        key='BL8',
        label='BL8',
        module='research.cipher_forward.bl8',
        path='research/cipher_forward/bl8.py',
        timeframe='1h+4h',
        side='LONG',
    ),
)

CANDIDATE_SPEC = dict(
    key='C3',
    label='W11S/C3',
    module='research.cipher_forward.strategy',
    path='research/cipher_forward/strategy.py',
    timeframe='1h',
    side='SHORT',
)

_SLEEVES = {
    'r_target_shorts': (MeasuredMoveBreakStrategy, MeasuredMoveBreakParams),
    'breakout_fail_shorts': (DonchianNFailReversionStrategy, DonchianNFailReversionParams),
    'outside_bar_fail': (OutsideBarFailReversionStrategy, OutsideBarFailReversionParams),
}


def _frame_index(frame: pd.DataFrame) -> pd.DataFrame:
    """Sleeve input. The index is the bar open, which is the file timestamp."""
    index = pd.to_datetime(frame['open_time_ms'], unit='ms', utc=True)
    out = pd.DataFrame(
        {
            'open': frame['open'].to_numpy(),
            'high': frame['high'].to_numpy(),
            'low': frame['low'].to_numpy(),
            'close': frame['close'].to_numpy(),
            'volume': frame['volume'].to_numpy(),
        },
        index=index,
    )
    out.index.name = 'timestamp'
    return out


def _next_open(opens: list[int], signal_open: int, step: int) -> int | None:
    """Fill at the next bar's open. That open has to be inside the hard cap."""
    entry_ms = signal_open + step
    if entry_ms > HARD_END_MS or entry_ms < WINDOW_START_MS:
        return None
    if entry_ms not in opens:
        return None
    return entry_ms


def sleeve_short_intents(symbol: str, frame: pd.DataFrame, key: str) -> list[dict]:
    """Default-parameter SHORT signals. The searched grid is not walked."""
    strategy_cls, params_cls = _SLEEVES[key]
    strategy = strategy_cls(params_cls(side=SignalSide.SHORT))
    candles = _frame_index(frame)
    signals = strategy.generate_signals(candles)
    opens = [int(value) for value in frame['open_time_ms']]
    present = set(opens)
    step = FOUR_HOUR_MS
    intents = []
    for open_ms, signal in zip(opens, signals['signal'].tolist()):
        if int(signal) != -1:
            continue
        entry_ms = _next_open(present, open_ms, step)
        if entry_ms is None:
            continue
        intents.append(dict(
            symbol=symbol, source=key, kind='pct', side=-1, entry_ms=entry_ms,
            stop_pct=float(strategy.params.stop_loss_pct),
            target_pct=float(strategy.params.take_profit_pct),
            uid=f'{key}|{symbol}|{entry_ms}',
        ))
    return intents


def _f111_rule(side: SignalSide) -> MarF111R12ExtensionLatefloorV1Strategy:
    """Default F111 parameters. Only the side changes. The stop and target stay."""
    base = MarF111R12ExtensionLatefloorV1Strategy()
    return MarF111R12ExtensionLatefloorV1Strategy(replace(base.params, side=side))


def f111_short_intents(symbol: str, frame: pd.DataFrame, btc: pd.DataFrame) -> list[dict]:
    """Hourly F111 SHORT gate. The minute retest is not on this tape."""
    rule = _f111_rule(SignalSide.SHORT)
    candles = _frame_index(frame)
    btc_candles = _frame_index(btc)
    prepared = rule.prepare_market_context(symbol, candles, btc_candles)
    signals = rule.generate_signals(prepared)
    opens = [int(value) for value in frame['open_time_ms']]
    present = set(opens)
    if 'prior_atr' not in signals.columns:
        raise ValueError('F111 frame has no prior_atr')
    intents = []
    for open_ms, signal, prior in zip(opens, signals['signal'].tolist(), signals['prior_atr'].tolist()):
        if int(signal) != -1:
            continue
        entry_ms = _next_open(present, open_ms, HOUR_MS)
        if entry_ms is None or not math.isfinite(float(prior)) or float(prior) <= 0:
            continue
        intents.append(dict(
            symbol=symbol, source='H', kind='atr', side=-1, entry_ms=entry_ms,
            prior_atr=float(prior), uid=f'F111|{symbol}|{entry_ms}',
        ))
    return intents


def _close_labelled(frame: pd.DataFrame, step: int) -> list[dict]:
    """BL8 bars use the close timestamp. A close after the cap is left out."""
    rows = []
    for record in frame.itertuples(index=False):
        close_ms = int(record.open_time_ms) + step
        if close_ms > HARD_END_MS:
            continue
        rows.append(dict(
            t=close_ms, o=float(record.open), h=float(record.high),
            l=float(record.low), c=float(record.close),
        ))
    return rows


def bl8_intents(symbol: str, hours: pd.DataFrame, four_hours: pd.DataFrame) -> list[dict]:
    """BL8 long rebound. The tail is the window the function reads."""
    hourly = _close_labelled(hours, HOUR_MS)
    four = _close_labelled(four_hours, FOUR_HOUR_MS)
    opens = {int(value) for value in hours['open_time_ms']}
    intents = []
    for index in range(len(hourly)):
        asof = hourly[index]['t']
        if asof > HARD_END_MS:
            continue
        hour_tail = hourly[max(0, index - 24): index + 1]
        four_tail = [bar for bar in four if bar['t'] <= asof][-18:]
        signal = bl8_decision(symbol, hour_tail, four_tail, asof)
        if not signal.get('eligible_signal'):
            continue
        entry_ms = asof
        if entry_ms not in opens or entry_ms > HARD_END_MS:
            continue
        intents.append(dict(
            symbol=symbol, source='B', kind='price', side=1, entry_ms=entry_ms,
            stop=float(signal['stop']), target=float(signal['target']),
            bl8=signal, uid=signal.get('uid') or f'BL8|{symbol}|{entry_ms}',
        ))
    return intents


def _c3_array(frame: pd.DataFrame):
    """Empty seed row, then one row per hourly bar. seed_start is 4h-aligned."""
    import numpy as np
    first = int(frame['open_time_ms'].iloc[0])
    if first % HOUR_MS:
        raise ValueError('hourly open is not aligned')
    seed_start = first - (first % (4 * HOUR_MS))
    last_open = int(frame['open_time_ms'].iloc[-1])
    last_close = last_open + HOUR_MS
    count = (last_close - seed_start) // HOUR_MS + 1
    array = np.full((count, 6), np.nan, dtype=np.float64)
    by_open = {int(row.open_time_ms): row for row in frame.itertuples(index=False)}
    for open_ms, row in by_open.items():
        close_ms = open_ms + HOUR_MS
        index = (close_ms - seed_start) // HOUR_MS
        array[index] = (row.open, row.high, row.low, row.close, row.volume, row.turnover)
    return array, seed_start, by_open


def c3_intents(symbol: str, frame: pd.DataFrame) -> list[dict]:
    """Unfiltered 3R short. The IF turnover filter is not this candidate."""
    array, seed_start, by_open = _c3_array(frame)
    if seed_start % (4 * HOUR) or seed_start < 0:
        raise ValueError('C3 seed is not a 4h boundary')
    # decision() returns warmup below 801 rows. The feature kernel is not
    # called on a shorter array; that is the same gate, not a new threshold.
    if len(array) < 801:
        return []
    features = compute(array)
    intents = []
    for record in features.itertuples(index=False):
        if not bool(record.ready) or int(record.side) != -1:
            continue
        close_ms = seed_start + int(record.hour) * HOUR
        if close_ms > HARD_END_MS or close_ms < WINDOW_START_MS:
            continue
        if close_ms not in by_open:
            continue
        signal = from_feature(symbol, record._asdict(), seed_start)
        if signal.get('eligible_signal') is not True:
            continue
        intents.append(dict(
            symbol=symbol, source='C3', kind='price', side=-1, entry_ms=close_ms,
            stop=float(signal['stop']), target=float(signal['target']),
            c3=signal, uid=signal['uid'],
        ))
    return intents


def f111_long_intents(symbol: str, frame: pd.DataFrame, btc: pd.DataFrame) -> list[dict]:
    """Hourly F111 LONG gate for the I and IC books. Not a clone-screen row."""
    rule = _f111_rule(SignalSide.LONG)
    candles = _frame_index(frame)
    prepared = rule.prepare_market_context(symbol, candles, _frame_index(btc))
    signals = rule.generate_signals(prepared)
    opens = [int(value) for value in frame['open_time_ms']]
    present = set(opens)
    longs = []
    for open_ms, signal, prior in zip(opens, signals['signal'].tolist(), signals['prior_atr'].tolist()):
        if int(signal) != 1:
            continue
        entry_ms = _next_open(present, open_ms, HOUR_MS)
        if entry_ms is None or not math.isfinite(float(prior)) or float(prior) <= 0:
            continue
        longs.append(dict(
            symbol=symbol, source='H', kind='atr', side=1, entry_ms=entry_ms,
            prior_atr=float(prior), uid=f'F111|{symbol}|LONG|{entry_ms}',
        ))
    return longs


def collect_intents(tape: dict) -> dict:
    """Intents for the candidate and each comparator. No book caps here."""
    symbols = list(tape)
    if 'BTCUSDT' not in tape:
        raise ValueError('the tape has no BTCUSDT hourly context')
    btc = tape['BTCUSDT']['1h']
    candidate = []
    comparators = {spec['key']: [] for spec in COMPARATOR_SPECS}
    longs = []
    for symbol, bars in tape.items():
        hours, four = bars['1h'], bars['4h']
        candidate.extend(c3_intents(symbol, hours))
        comparators['r_target_shorts'].extend(sleeve_short_intents(symbol, four, 'r_target_shorts'))
        comparators['breakout_fail_shorts'].extend(
            sleeve_short_intents(symbol, four, 'breakout_fail_shorts'))
        comparators['outside_bar_fail'].extend(sleeve_short_intents(symbol, four, 'outside_bar_fail'))
        comparators['F111'].extend(f111_short_intents(symbol, hours, btc))
        comparators['BL8'].extend(bl8_intents(symbol, hours, four))
        longs.extend(f111_long_intents(symbol, hours, btc))
    book = (
        list(candidate)
        + list(comparators['BL8'])
        + list(comparators['F111'])
        + longs
    )
    return dict(candidate=candidate, comparators=comparators, book=book, symbols=symbols)


def bar_hit(side: int, open_: float, high: float, low: float, stop: float, target: float):
    """Stop wins when the same bar touches the stop and the target."""
    if side == -1:
        stop_hit = high >= stop
        target_hit = low <= target
        if stop_hit:
            return 'stop', open_ if open_ >= stop else stop
        if target_hit:
            return 'target', open_ if open_ <= target else target
        return None
    if side != 1:
        raise ValueError('side is not long or short')
    stop_hit = low <= stop
    target_hit = high >= target
    if stop_hit:
        return 'stop', open_ if open_ <= stop else stop
    if target_hit:
        return 'target', open_ if open_ >= target else target
    return None


def _bars_by_open(frame: pd.DataFrame) -> dict[int, dict]:
    return {
        int(row.open_time_ms): dict(
            open_ms=int(row.open_time_ms), open=float(row.open), high=float(row.high),
            low=float(row.low), close=float(row.close),
        )
        for row in frame.itertuples(index=False)
    }


def admit_prices(intent: dict, open_: float) -> dict | None:
    """Desk031 slip on the next open, then the family's own gate. None skips it."""
    side = int(intent['side'])
    entry_fill = open_ * (1 + side * SLIP)
    if entry_fill <= 0 or not math.isfinite(entry_fill):
        return None
    kind = intent['kind']
    if kind == 'pct':
        stop = entry_fill * (1 - side * float(intent['stop_pct']))
        target = entry_fill * (1 + side * float(intent['target_pct']))
    elif kind == 'atr':
        brackets = initial_brackets(entry_fill, side, float(intent['prior_atr']))
        stop, target = brackets['initial_stop'], brackets['target']
    elif kind == 'price':
        stop, target = float(intent['stop']), float(intent['target'])
        if intent['source'] == 'C3':
            gate = c3_fill_gate(
                intent['c3'], entry_fill, fee=FEE, market_slip=SLIP, total_stop_slip=STOP_SLIP)
            if not gate['eligible']:
                return None
        elif intent['source'] == 'B':
            if not bl8_fill_gate(intent['bl8'], entry_fill):
                return None
    else:
        raise ValueError('unknown intent kind')
    distance = side * (entry_fill - stop) / entry_fill
    floor = 0.08 if intent['source'] == 'B' else 0.005
    if not all(math.isfinite(x) for x in (stop, target, distance)):
        return None
    if min(stop, target) <= 0 or distance <= 0 or side * (target - entry_fill) <= 0:
        return None
    if intent['source'] in ('H', 'B', 'C3') and not floor <= distance <= 0.15:
        return None
    if intent['source'] not in ('H', 'B', 'C3') and not 0 < distance:
        return None
    planned_stop = stop * (1 - side * STOP_SLIP)
    loss_fraction = (side * (entry_fill - planned_stop) + FEE * (entry_fill + planned_stop)) / entry_fill
    if loss_fraction <= 0:
        return None
    return dict(
        entry_fill=entry_fill, raw_entry=open_, stop=stop, target=target,
        loss_fraction=loss_fraction, distance=distance,
    )


def _pnl(side: int, qty: float, entry_fill: float, raw_entry: float, raw_exit: float, reason: str) -> dict:
    slip = STOP_SLIP if reason == 'stop' else SLIP
    exit_fill = raw_exit * (1 - side * slip)
    gross = side * (raw_exit - raw_entry) * qty
    net = side * (exit_fill - entry_fill) * qty - FEE * qty * (entry_fill + exit_fill)
    return dict(
        exit_fill=exit_fill, gross_usdt=gross, net_usdt=net, cost_usdt=gross - net,
        notional=qty * entry_fill,
    )


def unit_trades(intents: list[dict], bars_for) -> tuple[list[dict], list[dict]]:
    """One position per symbol, notional 1. Entries are the admitted fills."""
    by_symbol: dict[str, list[dict]] = {}
    for intent in intents:
        by_symbol.setdefault(intent['symbol'], []).append(intent)
    entries, trades = [], []
    for symbol, rows in by_symbol.items():
        bars = bars_for(symbol)
        opens = sorted(bars)
        pending = sorted(rows, key=lambda row: (row['entry_ms'], row['uid']))
        cursor = 0
        open_trade = None

        def close(reason: str, raw_exit: float, exit_ms: int) -> None:
            nonlocal open_trade
            money = _pnl(
                open_trade['side'], open_trade['qty'], open_trade['entry_fill'],
                open_trade['raw_entry'], raw_exit, reason)
            trades.append(dict(
                symbol=symbol, entry_ms=open_trade['entry_ms'], exit_ms=exit_ms,
                net_pnl=money['net_usdt'], gross_pnl=money['gross_usdt'],
                cost=money['cost_usdt'], reason=reason, source=open_trade['source'],
            ))
            open_trade = None

        for index, open_ms in enumerate(opens):
            bar = bars[open_ms]
            last = index == len(opens) - 1
            if open_trade is not None and open_trade['entry_ms'] != open_ms:
                hit = bar_hit(
                    open_trade['side'], bar['open'], bar['high'], bar['low'],
                    open_trade['stop'], open_trade['target'])
                if hit is not None:
                    close(hit[0], hit[1], open_ms)
            while cursor < len(pending) and pending[cursor]['entry_ms'] < open_ms:
                cursor += 1
            if open_trade is None and cursor < len(pending) and pending[cursor]['entry_ms'] == open_ms:
                intent = pending[cursor]
                cursor += 1
                prices = admit_prices(intent, bar['open'])
                if prices is not None:
                    qty = 1.0 / prices['entry_fill']
                    open_trade = dict(intent, **prices, qty=qty)
                    entries.append(dict(symbol=symbol, entry_ms=open_ms))
            if open_trade is not None and open_trade['entry_ms'] == open_ms:
                hit = bar_hit(
                    open_trade['side'], bar['open'], bar['high'], bar['low'],
                    open_trade['stop'], open_trade['target'])
                if hit is not None:
                    close(hit[0], hit[1], open_ms)
            if open_trade is not None and last:
                close('end', bar['close'], open_ms)
    return entries, trades


def screen_inputs(tape: dict) -> dict:
    """Candidate and comparator entry lists plus unit-notional trades."""
    collected = collect_intents(tape)

    def bars_for(timeframe_of: str):
        def fetch(symbol: str) -> dict[int, dict]:
            frame = tape[symbol]['4h' if timeframe_of == '4h' else '1h']
            return _bars_by_open(frame)
        return fetch

    candidate_entries, candidate_trades = unit_trades(collected['candidate'], bars_for('1h'))
    comparators = {}
    for spec in COMPARATOR_SPECS:
        timeframe = '4h' if spec['timeframe'] == '4h' else '1h'
        entries, trades = unit_trades(collected['comparators'][spec['key']], bars_for(timeframe))
        comparators[spec['key']] = dict(entries=entries, trades=trades, spec=spec)
    return dict(
        candidate_entries=candidate_entries,
        candidate_trades=candidate_trades,
        comparators=comparators,
        book_intents=collected['book'],
    )
