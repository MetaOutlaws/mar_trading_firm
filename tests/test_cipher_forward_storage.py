"""Ledger retention and the disk guard that protects the main paper book."""
import json
import os
from pathlib import Path

import pytest

from research.cipher_forward.config import frozen_config
from research.cipher_forward.ledger import PaperTrial, DAY
from research.cipher_forward.storage import (
    CONTAINER_MAIN_PAPER_DB, DEFAULT_MAIN_PAPER_DB, LEDGER_MAX_AGE_MS,
    LEDGER_MAX_BYTES, MIN_FREE_BYTES, StorageWriteBlocked, assess_storage,
    disable_entries, existing_volume, storage_settings_from_env,
)
from tests.test_cipher_forward_runtime import T, cycle, signal

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def book(tmp_path):
    trial = PaperTrial(tmp_path / 'trial.db', frozen_config(), create=True)
    yield trial
    trial.db.close()


def test_documented_guard_thresholds():
    assert MIN_FREE_BYTES == 2 * 1024 ** 3
    assert LEDGER_MAX_BYTES == 1 * 1024 ** 3
    assert LEDGER_MAX_AGE_MS == 10 * 24 * 60 * 60 * 1000
    assert DEFAULT_MAIN_PAPER_DB == Path('/data/state/data/firm.db')
    assert CONTAINER_MAIN_PAPER_DB == Path('/main-paper/firm.db')


def test_env_overrides_and_rejects_nonpositive(monkeypatch, tmp_path):
    monkeypatch.setenv('CIPHER_FORWARD_MIN_FREE_BYTES', '100')
    monkeypatch.setenv('CIPHER_FORWARD_LEDGER_MAX_BYTES', '200')
    monkeypatch.setenv('CIPHER_FORWARD_LEDGER_MAX_AGE_MS', '300')
    monkeypatch.setenv('CIPHER_FORWARD_MAIN_PAPER_DB', str(tmp_path / 'firm.db'))
    settings = storage_settings_from_env()
    assert (settings.min_free_bytes, settings.ledger_max_bytes, settings.ledger_max_age_ms) == (100, 200, 300)
    assert settings.main_paper_db == tmp_path / 'firm.db'
    monkeypatch.setenv('CIPHER_FORWARD_MIN_FREE_BYTES', '0')
    with pytest.raises(ValueError):
        storage_settings_from_env()


def test_container_mount_is_the_default_when_present(monkeypatch):
    monkeypatch.delenv('CIPHER_FORWARD_MAIN_PAPER_DB', raising=False)

    def exists(self):
        # os.path.exists does not call Path.exists, so this does not recurse.
        if str(self) == '/main-paper':
            return True
        return os.path.exists(self)

    monkeypatch.setattr(Path, 'exists', exists)
    assert storage_settings_from_env().main_paper_db == CONTAINER_MAIN_PAPER_DB


def test_low_main_paper_volume_blocks_while_the_ledger_volume_has_space(tmp_path):
    ledger = tmp_path / 'svc' / 'trial.db'
    main = tmp_path / 'paper' / 'firm.db'
    ledger.parent.mkdir(); main.parent.mkdir()
    ledger.write_bytes(b'ledger'); main.write_bytes(b'paper')

    def free(path):
        if Path(path) == main:
            return 10
        if Path(path) == ledger:
            return 10 ** 12
        raise AssertionError(path)

    decision = assess_storage(ledger, main, min_free_bytes=MIN_FREE_BYTES,
                              ledger_max_bytes=LEDGER_MAX_BYTES, free_bytes=free)
    assert decision.blocked
    assert decision.main_free_bytes == 10
    assert decision.ledger_free_bytes == 10 ** 12
    assert 'main paper DB volume' in decision.reason
    assert str(main) in decision.reason


def test_low_ledger_volume_blocks_even_when_the_main_book_has_space(tmp_path):
    ledger = tmp_path / 'svc' / 'trial.db'
    main = tmp_path / 'paper' / 'firm.db'
    ledger.parent.mkdir(); main.parent.mkdir()
    ledger.write_bytes(b'ledger'); main.write_bytes(b'paper')

    def free(path):
        return 10 if Path(path) == ledger else 10 ** 12

    decision = assess_storage(ledger, main, min_free_bytes=MIN_FREE_BYTES,
                              ledger_max_bytes=LEDGER_MAX_BYTES, free_bytes=free)
    assert decision.blocked
    assert 'ledger volume' in decision.reason
    assert decision.main_free_bytes == 10 ** 12


def test_healthy_volumes_do_not_block(tmp_path):
    ledger = tmp_path / 'trial.db'
    main = tmp_path / 'firm.db'
    ledger.write_bytes(b'a'); main.write_bytes(b'b')
    decision = assess_storage(ledger, main, min_free_bytes=1, ledger_max_bytes=10 ** 12,
                              free_bytes=lambda path: 100)
    assert not decision.blocked
    assert decision.reason == ''
    assert decision.main_volume == str(main)


def test_missing_main_paper_volume_fails_closed(tmp_path):
    ledger = tmp_path / 'trial.db'
    ledger.write_bytes(b'ok')
    decision = assess_storage(
        ledger, Path('/no/such/mar-paper/firm.db'), min_free_bytes=1,
        ledger_max_bytes=10 ** 12, free_bytes=lambda path: 10 ** 12)
    assert decision.blocked
    assert decision.main_free_bytes is None
    assert 'cannot measure main paper DB volume' in decision.reason
    with pytest.raises(OSError):
        existing_volume(Path('/no/such/mar-paper/firm.db'))


def test_blocked_guard_does_not_append(book, tmp_path):
    before = book.db.execute('SELECT count(*) FROM events').fetchone()[0]
    book.block_writes('main paper volume is low')
    with pytest.raises(StorageWriteBlocked):
        cycle(book, signals=[signal()])
    assert book.db.execute('SELECT count(*) FROM events').fetchone()[0] == before
    assert not book.positions()
    disable_entries(tmp_path)
    assert (tmp_path / 'entries_disabled').is_file()
    disable_entries(tmp_path)


def test_age_retention_drops_history_and_keeps_the_book(book):
    cycle(book, signals=[signal()])
    positions = book.positions()
    event = book.db.execute('SELECT id, hash FROM events').fetchone()
    book.db.execute('UPDATE events SET at_ms=?, payload=? WHERE id=?', (T - 30 * DAY, b'z' * 1000, event[0]))
    book.observe(T - 30 * DAY, 'old', {'blob': 'x' * 1000})
    book.observe(T, 'recent', {'ok': True})
    book.history_snapshot(T - 30 * DAY, {'BTCUSDT': {'hours': [1]}})
    book.db.execute(
        'INSERT INTO equity_samples VALUES (?,?,?,?,?,?,?)',
        ('baseline:I', 1, T - 30 * DAY, 20000, 20000, 1, 1))
    still_over = book.enforce_retention(
        T, max_age_ms=14 * DAY, max_bytes=10 ** 15, min_free_bytes=MIN_FREE_BYTES,
        main_free_bytes=10 ** 15)
    assert not still_over
    kinds = {row[0] for row in book.db.execute('SELECT kind FROM observations')}
    assert kinds == {'recent'}
    kept = book.db.execute('SELECT hash, payload FROM events WHERE id=?', (event[0],)).fetchone()
    assert kept[0] == event[1] and kept[1] == b''
    assert book.db.execute(
        'SELECT payload FROM history_snapshots WHERE hour=?', (T - 30 * DAY,)).fetchone()[0] == b''
    assert book.db.execute(
        'SELECT count(*) FROM equity_samples WHERE at_ms=?', (T - 30 * DAY,)).fetchone()[0] == 0
    assert book.positions() == positions
    assert book.db.execute('SELECT count(*) FROM decisions').fetchone()[0] > 0
    assert book.reconcile()
    # The cleared payload must not let the same cycle trade again.
    assert cycle(book, signals=[signal()])['duplicate']


def test_size_cap_stops_writes_without_deleting_positions(book):
    cycle(book, signals=[signal()])
    positions = len(book.positions())
    decisions = book.db.execute('SELECT count(*) FROM decisions').fetchone()[0]
    book.observe(T, 'bulk', {'x': 'y' * 200000})
    still_over = book.enforce_retention(
        T, max_age_ms=14 * DAY, max_bytes=1024, min_free_bytes=10 ** 15,
        main_free_bytes=10 ** 15)
    assert still_over
    assert book.db.execute("SELECT count(*) FROM observations WHERE kind='bulk'").fetchone()[0] == 0
    assert len(book.positions()) == positions
    assert book.db.execute('SELECT count(*) FROM decisions').fetchone()[0] == decisions
    assert book.reconcile()
    book.block_writes('ledger remains above the size cap')
    with pytest.raises(StorageWriteBlocked):
        book.observe(T, 'more', {'x': 1})
    with pytest.raises(StorageWriteBlocked):
        cycle(book, T + 60_000, [signal('next', 'ETHUSDT', T + 60_000)])
    assert len(book.positions()) == positions


def _production_instrument(symbol):
    """Bybit v5 linear instrument shape. Values are synthetic. No network call."""
    return dict(
        symbol=symbol, contractType='LinearPerpetual', status='Trading',
        baseCoin=symbol[:-4], quoteCoin='USDT', launchTime='1584230400000',
        deliveryTime='0', deliveryFeeRate='', priceScale='2',
        leverageFilter=dict(minLeverage='1', maxLeverage='100.00', leverageStep='0.01'),
        priceFilter=dict(minPrice='0.10', maxPrice='1999999.80', tickSize='0.10'),
        lotSizeFilter=dict(
            maxOrderQty='100.000', minOrderQty='0.001', qtyStep='0.001',
            postOnlyMaxOrderQty='1000.000', maxMktOrderQty='100.000', minNotionalValue='5'),
        unifiedMarginTrade=True, fundingInterval=480, settleCoin='USDT',
        copyTrading='both', upperFundingRate='0.00375', lowerFundingRate='-0.00375',
        isPreListing=False, preListingInfo=None,
    )


def _parsed_bars(count, duration, end_ms, seed):
    """Same dicts parse_bars stores: close-labelled t and float OHLCV."""
    bars = []
    price = 10.0 + (seed % 50)
    start = end_ms - count * duration
    for i in range(count):
        price = max(0.01, price * (1 + (((i * 17 + seed) % 11) - 5) / 10000))
        opened = round(price, 6)
        closed = round(opened * (1 + (((i + seed) % 5) - 2) / 10000), 6)
        high = max(opened, closed) * 1.001
        low = min(opened, closed) * 0.999
        bars.append(dict(
            t=start + (i + 1) * duration, o=opened, h=high, l=low, c=closed,
            v=1000.0 + (i % 100) + seed / 100))
    return bars


def test_ten_day_projection_stays_under_the_cap():
    """Measure quote, history, and equity bytes on synthetic production-shaped inputs.

    96 universe symbols, 200-level books, the 15-second quote cadence, and one
    hourly history snapshot of 860 hourly bars plus 40 four-hour bars. The
    clock is the synthetic pre-2026 fixture T. Nothing is fetched.
    """
    import zlib
    from research.cipher_forward.ledger import (
        BOOKS, CYCLES_PER_DAY, HISTORY_FOUR_HOUR_BARS, HISTORY_HOURLY_BARS,
        HISTORY_SNAPSHOTS_PER_DAY, MINUTE, QUOTE_SNAPSHOTS_PER_DAY, STORED_LEVELS,
        canonical, compact_event_payload, project_quote_event_bytes_per_day,
    )
    from research.cipher_forward.storage import LEDGER_RETENTION_DAYS
    universe = frozen_config()['universe']
    assert len(universe) == 96
    hour = 60 * MINUTE
    asof = (T // hour) * hour
    assert asof < 20454 * 24 * 60 * MINUTE  # before 2026-01-01
    quotes = {}
    histories = {}
    for seed, symbol in enumerate(universe):
        quotes[symbol] = dict(
            s=symbol, ts=asof,
            b=[[f'{100 - level * 0.01:.2f}', '1.5'] for level in range(200)],
            a=[[f'{100.01 + level * 0.01:.2f}', '1.5'] for level in range(200)],
        )
        histories[symbol] = dict(
            symbol=symbol,
            instrument=_production_instrument(symbol),
            hours=_parsed_bars(HISTORY_HOURLY_BARS, hour, asof, seed),
            four=_parsed_bars(HISTORY_FOUR_HOUR_BARS, 4 * hour, asof, seed + 1000),
        )
    def quote_bytes(include):
        payload = compact_event_payload(asof, quotes, {}, [], {}, False, include_levels=include)
        if include:
            assert len(payload['quotes'][universe[0]]['b']) == STORED_LEVELS
        return len(zlib.compress(canonical(payload).encode()))
    snapshot = quote_bytes(True)
    hash_only = quote_bytes(False)
    quote_day = project_quote_event_bytes_per_day(snapshot, hash_only)
    history_one = len(zlib.compress(canonical(histories).encode()))
    history_day = history_one * HISTORY_SNAPSHOTS_PER_DAY
    equity_row = len(canonical(dict(
        book='desk031:IC', minute=1, at_ms=asof, equity=20000.0, peak=20000.0,
        complete_marks=1, funding_known=1)))
    equity_day = equity_row * len(BOOKS) * 1440
    total = quote_day + history_day + equity_day
    ten_day = total * LEDGER_RETENTION_DAYS
    assert HISTORY_HOURLY_BARS == 860 and HISTORY_FOUR_HOUR_BARS == 40
    assert HISTORY_SNAPSHOTS_PER_DAY == 24
    assert QUOTE_SNAPSHOTS_PER_DAY == 96 and CYCLES_PER_DAY == 5760
    assert len(BOOKS) == 16 and LEDGER_RETENTION_DAYS == 10
    assert len(histories[universe[0]]['hours']) == 860
    assert len(histories[universe[0]]['four']) == 40
    assert quote_day > 0 and history_day > 0 and equity_day > 0
    assert ten_day < LEDGER_MAX_BYTES
    documented = '\n'.join(
        path.read_text() for path in (
            ROOT / 'docs/cipher-forward/README.md',
            ROOT / 'docs/cipher-forward/DEPLOYMENT.md'))
    for measured in (quote_day, history_day, equity_day, total, ten_day):
        assert f'{measured:,}' in documented
    assert 'retained for 14 days' not in documented
    assert '1209600000' not in documented
    print(
        f'quote_bytes_per_day={quote_day} history_bytes_per_day={history_day} '
        f'history_snapshot_bytes={history_one} equity_bytes_per_day={equity_day} '
        f'total_bytes_per_day={total} ten_day_bytes={ten_day}')


def test_protocol_clause_is_what_the_runtime_loads():
    protocol = json.loads((ROOT / 'docs/cipher-forward/protocol.json').read_text())
    text = protocol['promotion']['statement']
    assert 'non-promotional' in text
    assert '1.15' in text and 'excluding zero' in text
    assert 'beats random' in text and 'week clusters' in text
    assert 'veto-only' in text
