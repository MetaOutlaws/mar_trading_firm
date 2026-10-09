"""Outcome-free unit tests for the expansion adapter boundary."""
import json
import tempfile
from pathlib import Path

import pandas as pd

from adapter import audited_membership, partition_of


def test_partition_boundary() -> None:
    index = pd.DatetimeIndex(
        [
            "2021-12-31 23:59Z",
            "2022-01-01 00:00Z",
            "2024-12-31 23:59Z",
            "2025-01-01 00:00Z",
            "2025-12-31 23:59Z",
            "2026-01-01 00:00Z",
        ]
    )
    assert partition_of(index, False).tolist() == [
        "",
        "historical",
        "historical",
        "evaluation",
        "evaluation",
        "",
    ]
    assert partition_of(index, True)[-1] == "reserved_replication"


def test_audited_membership() -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        rows = [
            {"month": "2025-01", "symbol": "AAAUSDT", "rank": 1, "selected": True},
            {"month": "2025-01", "symbol": "BBBUSDT", "rank": 2, "selected": True},
        ]
        (root / "membership.json").write_text(json.dumps(rows))
        (root / "audit.json").write_text(
            json.dumps(
                {
                    "status": "usable_provisional",
                    "scores_2026": False,
                    "outcomes_scored": False,
                    "new_token_symbols": ["AAAUSDT", "BBBUSDT"],
                }
            )
        )
        audit, member, symbols = audited_membership(root)
        assert audit["status"] == "usable_provisional"
        assert member.eligible.all()
        assert symbols == ["AAAUSDT", "BBBUSDT"]


def test_closed_outcome_and_reference_rejection() -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        (root / "membership.json").write_text(
            json.dumps([{"month": "2025-01", "symbol": "BTCUSDT", "rank": 1}])
        )
        base = {
            "status": "usable_provisional",
            "scores_2026": False,
            "outcomes_scored": False,
            "new_token_symbols": ["BTCUSDT"],
        }
        (root / "audit.json").write_text(json.dumps(base))
        try:
            audited_membership(root)
        except ValueError as exc:
            assert "reference symbols" in str(exc)
        else:
            raise AssertionError("reference symbol entered primary membership")
        base["scores_2026"] = True
        (root / "audit.json").write_text(json.dumps(base))
        try:
            audited_membership(root)
        except ValueError as exc:
            assert "outcome-blind" in str(exc)
        else:
            raise AssertionError("opened 2026 status passed")


if __name__ == "__main__":
    tests = [
        test_partition_boundary,
        test_audited_membership,
        test_closed_outcome_and_reference_rejection,
    ]
    for test in tests:
        test()
        print("PASS", test.__name__)
