"""Garwe ruling and the one-service / twelve-portfolio display rules."""
import inspect
import json
import re
from pathlib import Path

import pytest

from research.cipher_forward.config import assert_no_promotion_clause, frozen_config
from research.cipher_forward.desk_cost import desk_cost_read
from research.cipher_forward.freeze import (
    TWELVE_LOOKS, current_identity, digest as freeze_digest, enforce_identity,
    entries_halted, freeze_before_warmup, warmup_begun)
from research.cipher_forward.ledger import BOOKS, DAY, MINUTE, PaperTrial, digest as ledger_digest
from research.cipher_forward.reporting import report, render
from research.cipher_forward.strategy import COSTS, FEE
from scripts.run_cipher_forward_paper import warmup

ROOT = Path(__file__).resolve().parents[1]
T = 20000 * DAY + MINUTE


def _quote(symbol='BTCUSDT', t=T, bid=99.9, ask=100., size='100000'):
    return dict(s=symbol, ts=t, b=[[str(bid), size]], a=[[str(ask), size]])


def _instrument(symbol='BTCUSDT'):
    return dict(symbol=symbol, status='Trading', fundingInterval=480,
        lotSizeFilter=dict(qtyStep='.001', minOrderQty='.001', maxMktOrderQty='100000', minNotionalValue='5'))


def signal(uid='one', symbol='BTCUSDT', t=T, source='B', side=1, **changes):
    return dict(uid=uid, symbol=symbol, source=source, side=side, sector='majors', signal_ms=t - MINUTE,
        action_ms=t, eligible_signal=True, stop=90., target=110., prior_atr=3.) | changes


def cycle(book, t=T, signals=(), bid=99.9, ask=100., manual=False):
    symbols = {p['symbol'] for p in book.positions()} | {s['symbol'] for s in signals}
    return book.cycle(str(t), t, {s: _quote(s, t, bid, ask) for s in symbols},
        {s: _instrument(s) for s in symbols}, signals, None, manual_halt=manual)


@pytest.fixture
def book(tmp_path):
    trial = PaperTrial(tmp_path / 'trial.db', frozen_config(), create=True)
    yield trial
    trial.db.close()
LABEL = 'port verified byte-identical to PR #149 @0519f425; strategy logic not desk-reviewed'
WORD = re.compile(r'\b(best|winner)\b', re.I)


def _protocol():
    return json.loads((ROOT / 'docs/cipher-forward/protocol.json').read_text())


def _walk(value):
    if isinstance(value, dict):
        for key, item in value.items():
            assert 'best' not in key.lower() and 'winner' not in key.lower()
            _walk(item)
    elif isinstance(value, list):
        for item in value:
            _walk(item)
    elif isinstance(value, str):
        assert WORD.search(value) is None, value


def test_no_cost_setting_equals_binding_and_numbers_stay():
    roles = desk_cost_read()
    protocol = _protocol()
    assert protocol['desk_cost_read'] == roles
    assert roles['any_setting_equals_0_31pct_per_leg'] is False
    assert roles['settings_changed'] is False
    assert roles['binding_per_leg'] == '0.0031'
    baseline, moderate, severe = (roles['settings'][name] for name in ('baseline', 'moderate', 'severe'))
    assert (baseline['entry']['percent'], baseline['nonstop_exit']['percent'], baseline['stop_exit']['percent']) == ('0.255%', '0.255%', '0.055%')
    assert baseline['role'] == 'REPORT-ONLY' and baseline['display'] == 'prominent'
    assert (moderate['entry']['percent'], moderate['stop_exit']['percent']) == ('0.355%', '0.255%')
    assert moderate['role'] == 'not_binding' and moderate['stop_exit']['role'] == 'REPORT-ONLY'
    assert moderate['display'] == 'prominent'
    assert severe['entry']['percent'] == severe['stop_exit']['percent'] == '1.055%'
    assert severe['role'] == 'secondary_display_only' and severe['display'] == 'secondary'
    assert all(row['role'] != 'BINDING' for row in roles['settings'].values())
    # The paper tuples themselves are untouched.
    assert FEE == .00055
    assert COSTS == {'baseline': (.002, 0.), 'moderate': (.003, .002), 'severe': (.01, .01)}
    cfg = frozen_config()
    assert cfg['costs'] == {'baseline': [.002, 0.], 'moderate': [.003, .002], 'severe': [.01, .01]}
    assert cfg['fee_each_leg'] == .00055
    assert cfg['gross_fraction'] == .5 and cfg['drawdown_fraction'] == .15
    assert cfg['daily_realised_loss'] == .03 and cfg['risk_fraction'] == .01
    assert cfg['position_fraction'] == .1 and cfg['starting_equity_usdt'] == 20000
    assert protocol['execution']['baseline']['entry_and_nonstop_slip'] == 0.002
    assert protocol['execution']['moderate_sidecar']['total_extra_stop_slip'] == 0.002
    assert protocol['execution']['severe_secondary_sidecar']['entry_and_nonstop_slip'] == 0.01
    assert protocol['accounts']['gross_admission'] == .5
    assert protocol['accounts']['drawdown_entry_latch'] == .15


def test_report_has_no_best_of_selection_and_groups_four_comparisons(book):
    cycle(book, signals=[signal()])
    value = report(book, T + 1)
    html = render(value | {'verification': {'activation_verified': False}})
    _walk(value)
    assert WORD.search(html) is None
    assert value['twelve_looks_statement'] == TWELVE_LOOKS
    assert TWELVE_LOOKS in html
    assert 'internal simulated portfolios' in html
    assert 'not exchange accounts' in html
    assert list(value['comparisons']) == ['I', 'IC', 'IM', 'IF']
    assert value['comparison_order'] == ['I', 'IC', 'IM', 'IF']
    for arm in ('I', 'IC', 'IM', 'IF'):
        assert list(value['comparisons'][arm]['primary']) == ['baseline', 'moderate']
        assert list(value['comparisons'][arm]['secondary']) == ['severe']
        assert 'severe' not in value['comparisons'][arm]['primary']
    assert len(value['accounts']) == 12
    assert len({id(value['accounts'][name]) for name in BOOKS}) == 12
    assert html.index('Strategy comparison I') < html.index('Strategy comparison IC')
    assert html.index('Strategy comparison IC') < html.index('Strategy comparison IM')
    assert html.index('Strategy comparison IM') < html.index('Strategy comparison IF')
    assert '<details open' not in html
    assert html.count('secondary display only') >= 4
    assert 'REPORT-ONLY' in html and 'not the 2022' in html and '<table>' in html
    assert value['cost_roles']['settings']['baseline']['role'] == 'REPORT-ONLY'
    assert value['cost_roles']['settings']['severe']['display'] == 'secondary'
    assert _protocol()['twelve_looks']['statement'] == TWELVE_LOOKS
    assert _protocol()['twelve_looks']['selects_a_config_or_cost'] is False


def test_freeze_precedes_warmup_and_mismatch_voids_entries(book, tmp_path, monkeypatch):
    assert enforce_identity(tmp_path, 1)['void'] is False
    assert warmup_begun(tmp_path) is False

    def stop_before_bars(*_args, **_kwargs):
        frozen = json.loads((tmp_path / 'config_freeze.json').read_text())
        assert frozen['frozen_before_warmup'] is True
        assert len(frozen['portfolio_hashes']) == 12
        assert frozen['code_sha']
        raise RuntimeError('stop before bars')

    monkeypatch.setattr('scripts.run_cipher_forward_paper.SeedStore', stop_before_bars)
    with pytest.raises(RuntimeError, match='stop before bars'):
        warmup(tmp_path / 'seed', tmp_path / 'context')
    assert (tmp_path / 'config_freeze.json').is_file()
    assert not (tmp_path / 'warmup.json').exists()
    source = inspect.getsource(warmup)
    assert source.index('freeze_before_warmup') < source.index('SeedStore')
    assert 'PaperTrial' not in source and 'ledger.cycle' not in source

    (tmp_path / 'warmup.json').write_text('{"ready": true}\n')
    stored = json.loads((tmp_path / 'config_freeze.json').read_text())
    stored['portfolio_hashes']['baseline:I'] = '0' * 64
    (tmp_path / 'config_freeze.json').write_text(json.dumps(stored))
    halted, status = entries_halted(tmp_path, 2)
    assert halted and status['void'] is True
    assert (tmp_path / 'void.json').is_file()
    assert (tmp_path / 'entries_disabled').is_file()
    # A later startup and a later cycle both keep the VOID mark.
    halted_again, again = entries_halted(tmp_path, 3)
    assert halted_again and again['void'] and again['reason'] == status['reason']
    result = cycle(book, signals=[signal()], manual=halted)
    assert result['new_entries'] == 0
    value = report(book, T + 1)
    value['void'] = status
    value['verification'] = {'activation_verified': False}
    html = render(value)
    assert 'VOID' in html and 'Entries are disabled' in html and 'not evidence' in html


def test_warmup_trade_pnl_is_omitted_from_performance(book):
    sentinel = 123456.789
    book.save_position(dict(
        book='baseline:I', uid='warm', symbol='BTCUSDT', source='B', sector='majors',
        status='closed', entry_ms=1, exit_ms=2, net_pnl=sentinel, original_risk_usdt=1.,
        side=1, quantity=1., entry=1., mark=1., entry_fee=0., exit_fee=0., funding=0.,
        gross_pnl=sentinel, missed_exit_ticks=0, missed_exit_minutes=0,
        decision_latency_ms=0, quote_age_ms=0, entry_slippage_usdt=0.,
        exit_slippage_usdt=0., entry_depth_usdt=0., exit_depth_usdt=0.,
        entry_half_spread_usdt=0.))
    book.db.execute(
        'INSERT INTO decisions VALUES (?,?,?,?,?)',
        ('baseline:I', 'warm', 1, 'entered', '{"reasons":[]}'))
    book.save_feed('first_forward_hour', 10)
    value = report(book, T)
    row = value['accounts']['baseline:I']
    assert row['entries'] == 0 and row['closed'] == 0 and row['closed_net_usdt'] == 0
    assert row['return_pct'] is None and row['calendar_years'] == {}
    assert value['warmup_rows_omitted'] >= 2
    assert value['warmup_performance_suppressed'] is True
    html = render(value | {'verification': {'activation_verified': False}})
    assert '123456.789' not in json.dumps(value)
    assert '123456.789' not in html


def test_promotion_covers_bl8_and_filtered_w11s_and_stays_report_only():
    protocol = _protocol()
    assert_no_promotion_clause(protocol)
    assert protocol['promotion']['pass_rule'] == 'REPORT-ONLY'
    assert protocol['promotion']['can_size_up'] is False
    assert protocol['promotion']['can_join_book'] is False
    assert protocol['promotion']['can_feed_walk_forward'] is False
    assert protocol['incumbent']['B'] == LABEL
    assert protocol['incumbent']['bl8_label'] == LABEL
    assert LABEL in (ROOT / 'research/cipher_forward/bl8.py').read_text()
    stripped = json.loads(json.dumps(protocol))
    stripped['promotion']['statement'] = stripped['promotion']['statement'].replace('BL8', 'strategy')
    with pytest.raises(ValueError, match='bl8'):
        assert_no_promotion_clause(stripped)
    stripped = json.loads(json.dumps(protocol))
    stripped['promotion']['statement'] = stripped['promotion']['statement'].replace('filtered W11S', 'variant')
    with pytest.raises(ValueError, match='filtered w11s'):
        assert_no_promotion_clause(stripped)
    stripped = json.loads(json.dumps(protocol))
    stripped['promotion']['covers_filtered_w11s'] = False
    with pytest.raises(ValueError, match='covers_filtered_w11s'):
        assert_no_promotion_clause(stripped)
    stripped = json.loads(json.dumps(protocol))
    stripped['promotion']['can_feed_walk_forward'] = True
    with pytest.raises(ValueError, match='can_feed_walk_forward'):
        assert_no_promotion_clause(stripped)


def test_config_hash_matches_ledger_and_lists_every_portfolio():
    assert freeze_digest({'arm': 'I', 'n': 1}) == ledger_digest({'n': 1, 'arm': 'I'})
    identity = current_identity()
    assert identity['portfolio_order'] == [
        f'{cost}:{arm}' for cost in ('baseline', 'moderate', 'severe') for arm in ('I', 'IC', 'IM', 'IF')]
    assert len(set(identity['portfolio_hashes'].values())) == 12
    assert set(identity['portfolio_hashes']) == set(BOOKS)
