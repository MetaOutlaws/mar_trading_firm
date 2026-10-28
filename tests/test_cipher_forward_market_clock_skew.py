"""Market clock window and closed-bar clock for the cipher-forward paper worker.

No network: time.time_ns and the public client are replaced before any GET.

skew_ms = now_ms - bybit_time, where negative means the local clock is behind Bybit.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path

import pytest

import scripts.run_cipher_forward_paper as paper
from scripts.run_cipher_forward_paper import (
    MAX_NEGATIVE_SKEW_MS, MAX_STALE_MS, Market, bar_is_closed, closed_bar_asof, scan,
)

# Fixed Bybit millisecond timestamp. Local time is this plus the skew under test.
BYBIT_MS = 1_700_000_000_000
LOGGER = 'scripts.run_cipher_forward_paper'


def test_window_constants_and_sign_convention_are_named():
    """skew_ms = now_ms - bybit_time, where negative means the local clock is behind Bybit."""
    assert MAX_NEGATIVE_SKEW_MS == 2000
    assert MAX_STALE_MS == 5000
    source = Path(paper.__file__).read_text()
    assert 'skew_ms = now_ms - bybit_time, where negative means the local clock is behind Bybit.' in source
    assert 'MAX_NEGATIVE_SKEW_MS' in source and 'MAX_STALE_MS' in source
    assert "0<=now_ms()-int(body['time'])<=5000" not in source


def _market(monkeypatch, skew_ms: int, *, bybit_ms: int = BYBIT_MS):
    """Return a Market whose clock and Bybit body yield exactly skew_ms.

    skew_ms = now_ms - bybit_time. A negative value means the local clock is
    behind Bybit.
    """
    local_ms = bybit_ms + skew_ms
    monkeypatch.setattr(paper.time, 'time_ns', lambda: local_ms * 1_000_000)
    market = Market()
    calls = []

    def fake_get(url, headers=None):
        calls.append((url, headers))
        symbol = 'BTCUSDT'
        for name in ('GOODUSDT', 'EARLYUSDT', 'STALEUSDT', 'BTCUSDT'):
            if f'symbol={name}' in url:
                symbol = name
                break
        return {'time': bybit_ms, 'result': {'symbol': symbol, 'list': []}}

    monkeypatch.setattr(market.client, 'get', fake_get)
    return market, calls


@pytest.mark.parametrize('skew_ms', [-47, -45, -2000, 0, 250, 5000])
def test_skew_inside_window_is_accepted(monkeypatch, skew_ms):
    market, calls = _market(monkeypatch, skew_ms)
    body = market.get('orderbook', symbol='BTCUSDT', limit=200)
    assert body['time'] == BYBIT_MS
    assert market.bybit_time_ms == BYBIT_MS
    assert calls and calls[0][0].startswith('https://api.bybit.com/v5/market/orderbook?')
    assert 'category=linear' in calls[0][0]
    # skew_ms = now_ms - bybit_time, where negative means the local clock is behind Bybit.
    assert paper.now_ms() - BYBIT_MS == skew_ms


def test_sign_convention_negative_means_local_clock_is_behind_bybit(monkeypatch, caplog):
    """skew_ms = now_ms - bybit_time, where negative means the local clock is behind Bybit."""
    market, _calls = _market(monkeypatch, -45)
    assert paper.now_ms() < BYBIT_MS
    assert paper.now_ms() - int(BYBIT_MS) == -45
    with caplog.at_level(logging.INFO, logger=LOGGER):
        market.get('orderbook', symbol='BTCUSDT')
    assert any(r.getMessage() == 'bybit response symbol=BTCUSDT skew_ms=-45' for r in caplog.records)


def test_negative_skew_probes_and_boundary_are_accepted(monkeypatch):
    """SGP1 probes were about -47/-46/-33 ms. -45 and -2000 stay inside the window."""
    for skew_ms in (-47, -46, -45, -33, -MAX_NEGATIVE_SKEW_MS):
        market, _calls = _market(monkeypatch, skew_ms)
        assert market.get('kline', symbol='BTCUSDT', interval='1')['time'] == BYBIT_MS


def test_skew_below_negative_bound_is_rejected(monkeypatch, caplog):
    market, _calls = _market(monkeypatch, -2001)
    returned = None
    with caplog.at_level(logging.DEBUG, logger=LOGGER):
        with pytest.raises(ValueError, match='stale response or clock mismatch'):
            returned = market.get('orderbook', symbol='EARLYUSDT')
    assert returned is None
    assert market.bybit_time_ms is None
    warnings = [r for r in caplog.records if r.levelno >= logging.WARNING]
    assert len(warnings) == 1
    message = warnings[0].getMessage()
    assert 'symbol=EARLYUSDT' in message
    assert 'skew_ms=-2001' in message
    assert 'failed_bound=MAX_NEGATIVE_SKEW_MS' in message
    assert 'limit=-2000' in message


def test_stale_above_positive_bound_is_rejected(monkeypatch, caplog):
    market, _calls = _market(monkeypatch, 5001)
    returned = None
    with caplog.at_level(logging.DEBUG, logger=LOGGER):
        with pytest.raises(ValueError, match='stale response or clock mismatch'):
            returned = market.get('funding/history', symbol='STALEUSDT')
    assert returned is None
    assert market.bybit_time_ms is None
    warnings = [r for r in caplog.records if r.levelno >= logging.WARNING]
    assert len(warnings) == 1
    message = warnings[0].getMessage()
    assert 'symbol=STALEUSDT' in message
    assert 'skew_ms=5001' in message
    assert 'failed_bound=MAX_STALE_MS' in message
    assert 'limit=5000' in message


def test_skew_is_logged_on_accept(monkeypatch, caplog):
    market, _calls = _market(monkeypatch, -47)
    with caplog.at_level(logging.INFO, logger=LOGGER):
        market.get('instruments-info', symbol='BTCUSDT')
    infos = [r for r in caplog.records if r.levelno == logging.INFO]
    assert len(infos) == 1
    assert infos[0].getMessage() == 'bybit response symbol=BTCUSDT skew_ms=-47'
    assert infos[0].name == LOGGER


def _feed(monkeypatch, symbols):
    """Feed whose histories go through Market.get. Each symbol has its own skew."""
    local_ms = BYBIT_MS
    monkeypatch.setattr(paper.time, 'time_ns', lambda: local_ms * 1_000_000)
    market = Market()
    secrets = {
        'GOODUSDT': ('GOOD-OK', -45),
        'EARLYUSDT': ('EARLY-SECRET', -2001),
        'STALEUSDT': ('STALE-SECRET', 5001),
    }

    def fake_get(url, headers=None):
        symbol = next(name for name in secrets if f'symbol={name}' in url)
        _marker, skew_ms = secrets[symbol]
        # skew_ms = local now - bybit time.
        return {
            'time': local_ms - skew_ms,
            'result': {'symbol': symbol, 'marker': secrets[symbol][0], 'list': [{'t': 1}]},
        }

    monkeypatch.setattr(market.client, 'get', fake_get)

    class Feed:
        universe = list(symbols)
        consumed = []
        returned = []

        def histories(self, symbol, asof):
            body = market.get('kline', symbol=symbol, interval='60')
            self.returned.append(body)
            return dict(
                symbol=symbol,
                instrument={'symbol': symbol, 'marker': body['result']['marker']},
                hours=body['result']['list'],
                four=[],
            )

        def evaluate(self, history, btc, asof):
            self.consumed.append(history)
            marker = history['instrument']['marker']
            return (
                [dict(uid=symbol_uid(history, 'p'), symbol=history['symbol'], marker=marker)],
                [dict(uid=symbol_uid(history, 'r'), symbol=history['symbol'], marker=marker)],
                [],
            )

    return Feed()


def symbol_uid(history, kind):
    return f"{history['symbol']}|{kind}"


def test_out_of_bound_symbol_is_skipped_logged_and_not_consumed(monkeypatch, caplog):
    """A symbol outside the skew window is not returned and is not a signal."""
    feed = _feed(monkeypatch, ['GOODUSDT', 'EARLYUSDT', 'STALEUSDT'])
    with caplog.at_level(logging.INFO, logger=LOGGER):
        result = scan(feed, BYBIT_MS // paper.HOUR * paper.HOUR)
    assert set(result['histories']) == {'GOODUSDT'}
    assert [row['symbol'] for row in feed.consumed] == ['GOODUSDT']
    assert [row['symbol'] for row in result['pending']] == ['GOODUSDT']
    assert [row['symbol'] for row in result['ready']] == ['GOODUSDT']
    assert set(result['instruments']) == {'GOODUSDT'}
    blob = json.dumps(result)
    assert 'EARLY-SECRET' not in blob and 'STALE-SECRET' not in blob
    assert 'GOOD-OK' in blob
    assert all(body['result']['marker'] == 'GOOD-OK' for body in feed.returned)
    errors = {row['symbol']: row['error'] for row in result['observations'] if 'error' in row}
    assert 'clock mismatch' in errors['EARLYUSDT']
    assert 'clock mismatch' in errors['STALEUSDT']
    messages = [r.getMessage() for r in caplog.records]
    assert any('symbol=EARLYUSDT' in text and 'skew_ms=-2001' in text
               and 'failed_bound=MAX_NEGATIVE_SKEW_MS' in text for text in messages)
    assert any('symbol=STALEUSDT' in text and 'skew_ms=5001' in text
               and 'failed_bound=MAX_STALE_MS' in text for text in messages)


def test_scan_logs_skew_on_every_scan(monkeypatch, caplog):
    """At least one skew line is emitted for a scan that reads the market."""
    feed = _feed(monkeypatch, ['GOODUSDT'])
    with caplog.at_level(logging.INFO, logger=LOGGER):
        scan(feed, BYBIT_MS // paper.HOUR * paper.HOUR)
    skew_lines = [r.getMessage() for r in caplog.records if 'skew_ms=' in r.getMessage()]
    assert skew_lines
    assert any('skew_ms=-45' in text for text in skew_lines)


@pytest.mark.parametrize('local_lead_ms', [1, 45, 2500, 5000])
def test_bar_closing_after_bybit_time_is_rejected_when_local_clock_is_ahead(
        monkeypatch, local_lead_ms):
    """A bar whose close is after Bybit server time stays unused.

    The local clock is ahead of Bybit, and already at or past the close.
    Closed-bar decisions still follow Bybit server time.
    """
    close_ms = (BYBIT_MS // paper.MINUTE + 1) * paper.MINUTE
    bybit_time = close_ms - 1
    local_ms = bybit_time + local_lead_ms
    monkeypatch.setattr(paper.time, 'time_ns', lambda: local_ms * 1_000_000)
    assert paper.now_ms() == local_ms
    # The local clock has reached the close. That must not make the bar usable.
    assert paper.now_ms() >= close_ms
    assert bar_is_closed(close_ms, bybit_time) is False
    asof = closed_bar_asof(bybit_time, paper.MINUTE)
    assert close_ms > asof
    assert bar_is_closed(asof, bybit_time) is True
    # The decision reads neither the local clock nor the skew.
    assert 'now_ms' not in bar_is_closed.__code__.co_names
    assert 'time' not in bar_is_closed.__code__.co_names


def test_closed_bar_helpers_do_not_read_the_local_clock():
    for fn in (bar_is_closed, closed_bar_asof):
        assert 'now_ms' not in fn.__code__.co_names
    worker = Path(paper.__file__).read_text()
    assert 'scan_asof=closed_bar_asof(bybit_server_time(market), HOUR)' in worker
    assert 'retest_asof=closed_bar_asof(bybit_server_time(market), MINUTE)' in worker
    assert 'submit(scan,feed,hour)' not in worker
    assert 'submit(retests,feed,dict(pending),minute)' not in worker
