"""Pinned runtime settings; no inheritance from production overrides."""
from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[2]


def frozen_config():
    protocol = json.loads((ROOT/'docs/cipher-forward/protocol.json').read_text())
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
