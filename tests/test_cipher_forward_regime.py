"""Synthetic EMA series only. No bars and no 2026 timestamps are labelled."""
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from research.cipher_forward.regime import (
    REGIME_RULE, RegimeInputError, classify_ema_series, classify_regime,
    label_week_cluster, label_week_clusters, no_losing_regime_gate,
)

ROOT_RULE = REGIME_RULE


def test_band_edges_on_a_synthetic_ema_series():
    slow = [100.0, 100.0, 100.0, 100.0, 200.0]
    # 98 < 99 BEAR; 99 is the lower edge CHOP; 101 is the upper edge CHOP; 102 BULL.
    fast = [98.0, 99.0, 101.0, 102.0, 197.0]
    assert classify_ema_series(fast, slow) == ["BEAR", "CHOP", "CHOP", "BULL", "BEAR"]
    assert classify_regime(100.0 * 1.01, 100.0) == "CHOP"
    assert classify_regime(100.0 * 0.99, 100.0) == "CHOP"
    assert classify_regime(100.0 * 1.01 + 1e-9, 100.0) == "BULL"
    assert classify_regime(100.0 * 0.99 - 1e-9, 100.0) == "BEAR"


def test_week_cluster_uses_the_monday_open_only():
    monday = datetime(2024, 1, 1, tzinfo=timezone.utc)
    assert monday.weekday() == 0
    assert label_week_cluster(monday, 90.0, 100.0) == "BEAR"
    assert label_week_clusters(
        [monday, monday + timedelta(days=7)],
        [90.0, 110.0],
        [100.0, 100.0],
    ) == ["BEAR", "BULL"]
    with pytest.raises(RegimeInputError, match="Monday"):
        label_week_cluster(monday + timedelta(days=1), 90.0, 100.0)
    with pytest.raises(RegimeInputError, match="Monday"):
        label_week_cluster(monday + timedelta(minutes=1), 90.0, 100.0)


def test_classifier_refuses_2026_and_does_not_need_bars():
    monday_2026 = datetime(2026, 1, 5, tzinfo=timezone.utc)
    assert monday_2026.weekday() == 0
    with pytest.raises(RegimeInputError, match="2026-01-01"):
        label_week_cluster(monday_2026, 90.0, 100.0)
    source = (Path(__file__).resolve().parents[1] / "research/cipher_forward/regime.py").read_text()
    assert "read_text" not in source and "parquet" not in source and "http" not in source


def test_short_regime_is_incomplete_and_not_a_pass():
    short = no_losing_regime_gate({"BULL": 4, "BEAR": 3, "CHOP": 4})
    assert short["result"] == "INCOMPLETE"
    assert short["passed"] is False
    assert short["result"] != "PASS"
    ready = no_losing_regime_gate({"BULL": 4, "BEAR": 4, "CHOP": 4})
    assert ready["result"] == "NOT_SCORED"
    assert ready["passed"] is False
    assert ready["loss_evaluated"] is False


def test_protocol_and_filing_quote_the_rule_verbatim():
    import json
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    protocol = json.loads((root / "docs/cipher-forward/protocol.json").read_text())
    filing = (root / "docs/cipher-forward/v2.2_filing_pr172.md").read_text()
    assert protocol["regime_rule"] == ROOT_RULE
    assert protocol["evidence_window"]["bear_spell_classifier"] == ROOT_RULE
    assert ROOT_RULE in filing
    assert "Soko's live label is not used" in protocol["regime_rule"]
