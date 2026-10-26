"""Pinned runtime settings; no inheritance from production overrides."""
from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[2]

# Full desk gates. These are promotion requirements, not the paper risk set.
REQUIRED_PROMOTION_GATES = {
    'profit_factor_min': 1.15,
    'confidence_interval_excludes_zero': True,
    'beats_random': True,
    'week_clusters': True,
}


def assert_no_promotion_clause(protocol: dict) -> None:
    """Fail closed when protocol.json drops the non-promotion clause."""
    clause = protocol.get('promotion') if isinstance(protocol, dict) else None
    if not isinstance(clause, dict):
        raise ValueError('protocol.json is missing the no-promotion clause')
    if clause.get('non_promotional') is not True or clause.get('promotion_authorized') is not False:
        raise ValueError('protocol.json no-promotion clause is not in force')
    if clause.get('required_gates') != REQUIRED_PROMOTION_GATES:
        raise ValueError('protocol.json promotion gates are not the full desk gates')
    statement = str(clause.get('statement') or '').lower()
    for phrase in ('non-promotional', '1.15', 'excluding zero', 'beats random',
                   'week cluster', 'veto-only'):
        if phrase not in statement:
            raise ValueError(f'protocol.json no-promotion statement is missing {phrase!r}')


def frozen_config():
    protocol = json.loads((ROOT/'docs/cipher-forward/protocol.json').read_text())
    assert_no_promotion_clause(protocol)
    return dict(version='cipher-forward-v1', mode='paper_comparison',live_authorized=False,
        starting_equity_usdt=20000, max_open_positions=15, gross_fraction=.5,
        risk_fraction=.01, position_fraction=.1, drawdown_fraction=.15,
        recovery_minutes=1440, opportunity_notional_usdt=2000,
        source_order=['H','B','C3'], universe=protocol['universe'],
        arms=['I','IC','IM','IF'], exit_tick_ms=15000,
        protection_decision_ms=60000,
        costs={'baseline':[.002,0.], 'moderate':[.003,.002], 'severe':[.01,.01]},
        fee_each_leg=.00055, stop_bounds={'H':[.005,.15],'B':[.08,.15],'C3':[.005,.15]},
        per_sector=2, daily_entries=20, daily_realised_loss=.03,
        funding_missing='unknown_blocks_funded_entries_exits_continue')
