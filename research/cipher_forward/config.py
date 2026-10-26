"""Pinned runtime settings; no inheritance from production overrides."""
from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[2]

# Full desk gates. These are promotion requirements, not the paper risk set
# (50% gross, 15% drawdown latch, 3% daily loss, C24, 1%/10%, 0.5%/5%).
REQUIRED_PROMOTION_GATES = {
    'profit_factor_min': 1.15,
    'profit_factor_net_at_binding_cost_per_leg': 0.0031,
    'confidence_interval_excludes_zero': True,
    'beats_random': True,
    'week_clusters': True,
    'folds_pass_fraction_min': 0.5,
    'no_losing_regime': True,
    'max_drawdown_lt': 0.25,
    'min_weeks': 30,
    'min_leg_trades_per_year': 100,
}

# Flags that keep this paper run, BL8, and the filtered W11S variant off the book.
REQUIRED_PROMOTION_FLAGS = {
    'pass_rule': 'REPORT-ONLY',
    'covers_bl8': True,
    'covers_filtered_w11s': True,
    'can_size_up': False,
    'can_join_book': False,
    'can_feed_walk_forward': False,
    'requires_filing': True,
    'requires_garwe_lock': True,
    'requires_holdout': True,
}


PRIMARY_ARMS = ('I', 'IC', 'IM', 'IF')


def require_primary(protocol: dict) -> str:
    """Refuse a freeze or a start when PRIMARY is missing or not an arm id."""
    primary = protocol.get('primary') if isinstance(protocol, dict) else None
    arm = primary.get('arm') if isinstance(primary, dict) else ''
    if arm not in PRIMARY_ARMS:
        raise ValueError('PRIMARY config is empty or not one of I, IC, IM, IF')
    return arm


def assert_interim_review_veto_only(protocol: dict) -> None:
    """An interim review can stop or void the run and cannot retune it."""
    review = protocol.get('interim_review') if isinstance(protocol, dict) else None
    if not isinstance(review, dict):
        raise ValueError('protocol.json is missing the interim-review veto')
    if review.get('veto_only') is not True or review.get('can_stop_or_void') is not True:
        raise ValueError('interim review must be veto-only and able to stop or void')
    for key in ('can_promote', 'can_repick_primary', 'can_change_config'):
        if review.get(key) is not False:
            raise ValueError(f'interim review must keep {key} false')
    statement = str(review.get('statement') or '').lower()
    for phrase in ('veto-only', 'stop', 'void', 'promote', 'primary', 'config', 'lock'):
        if phrase not in statement:
            raise ValueError(f'interim-review statement is missing {phrase!r}')


def assert_no_promotion_clause(protocol: dict) -> None:
    """Fail closed when protocol.json drops the non-promotion clause."""
    clause = protocol.get('promotion') if isinstance(protocol, dict) else None
    if not isinstance(clause, dict):
        raise ValueError('protocol.json is missing the no-promotion clause')
    if clause.get('non_promotional') is not True or clause.get('promotion_authorized') is not False:
        raise ValueError('protocol.json no-promotion clause is not in force')
    if clause.get('required_gates') != REQUIRED_PROMOTION_GATES:
        raise ValueError('protocol.json promotion gates are not the full desk gates')
    for key, expected in REQUIRED_PROMOTION_FLAGS.items():
        if clause.get(key) != expected:
            raise ValueError(f'protocol.json no-promotion clause missing {key}')
    statement = str(clause.get('statement') or '').lower()
    for phrase in ('non-promotional', '1.15', 'excluding zero', 'beats random',
                   'week cluster', 'veto-only', 'report-only', 'bl8',
                   'filtered w11s', 'filing', 'garwe lock', 'holdout',
                   'size up', 'join the book', 'walk-forward'):
        if phrase not in statement:
            raise ValueError(f'protocol.json no-promotion statement is missing {phrase!r}')


def frozen_config():
    protocol = json.loads((ROOT/'docs/cipher-forward/protocol.json').read_text())
    assert_no_promotion_clause(protocol)
    assert_interim_review_veto_only(protocol)
    primary = require_primary(protocol)
    return dict(version='cipher-forward-v1', mode='paper_comparison',live_authorized=False,
        starting_equity_usdt=20000, max_open_positions=15, gross_fraction=.5,
        risk_fraction=.01, position_fraction=.1, drawdown_fraction=.15,
        recovery_minutes=1440, opportunity_notional_usdt=2000,
        source_order=['H','B','C3'], universe=protocol['universe'],
        arms=['I','IC','IM','IF'], primary=primary, exit_tick_ms=15000,
        protection_decision_ms=60000,
        costs={'desk031':[.00255,.00255], 'baseline':[.002,0.], 'moderate':[.003,.002], 'severe':[.01,.01]},
        fee_each_leg=.00055, stop_bounds={'H':[.005,.15],'B':[.08,.15],'C3':[.005,.15]},
        per_sector=2, daily_entries=20, daily_realised_loss=.03,
        funding_missing='unknown_blocks_funded_entries_exits_continue')
