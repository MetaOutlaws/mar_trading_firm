"""Path2 findings render only Marcus-sealed rows.

The shipped table is four rows: macd_ma_agree long and short, and
ma_rsi_agree 70/30 long and short. All four are FAIL. Cell 80/20 is not
scored. An empty cells list still renders nothing. The loader must not invent
a count, a rate, a green-year note, or a PASS. A positive net stays FAIL
when the sealed verdict is FAIL.
"""

from __future__ import annotations

import json

from config.settings import PROJECT_ROOT
from firm.path2_findings import (
    METRIC_KEYS,
    PATH2_FINDINGS_PATH,
    SEALED_TABLE_NOTE,
    load_path2_findings,
)


# Figures copied from the sealed rows. Strings keep the sign, the percent,
# and the trailing zero that a float would drop.
_LONG = {
    "n": 533,
    "target_first_count": 166,
    "target_first_rate": "31.1%",
    "gross": "+0.009634",
    "net_after_0_31_rt": "-0.197033",
    "same_shell_h18_base_net": "-0.212583",
    "stress_stop_2_net": "-0.178630",
}
_SHORT = {
    "n": 484,
    "target_first_count": 150,
    "target_first_rate": "31.0%",
    "gross": "+0.025144",
    "net_after_0_31_rt": "-0.181523",
    "same_shell_h18_base_net": "-0.248336",
    "stress_stop_2_net": "-0.095669",
}


_RSI_LONG = {
    "n": 1,
    "target_first_count": 1,
    "target_first_rate": "100%",
    "gross": "+2.000",
    "net_after_0_31_rt": "+1.793333",
    "same_shell_h18_base_net": "-0.212583",
    "stress_stop_2_net": "+1.345",
}
_RSI_SHORT = {
    "n": 3,
    "target_first_count": 2,
    "target_first_rate": "66.7%",
    "gross": "+1.000",
    "net_after_0_31_rt": "+0.793333",
    "same_shell_h18_base_net": "-0.248336",
    "stress_stop_2_net": "+0.511667",
}


def test_shipped_findings_are_the_four_sealed_rows() -> None:
    raw_text = PATH2_FINDINGS_PATH.read_text(encoding="utf-8")
    raw = json.loads(raw_text)
    assert raw["sealed"] is True
    assert "Marcus-sealed table" in raw["note"]
    assert "not from briefs" in raw["note"]
    assert [cell["family"] for cell in raw["cells"]] == ["macd_ma_agree", "ma_rsi_agree"]
    macd, rsi = raw["cells"]
    assert macd["clock"] == "4h"
    assert macd["thresholds"]["label"] == "EMA 21 and MACD 12, 26, 9, agreement required"
    assert macd["verdict"] == "FAIL"
    assert macd.get("green_year_note") in (None, "")
    assert macd["sides"]["long"] == _LONG
    assert macd["sides"]["short"] == _SHORT
    assert rsi["clock"] == "4h"
    assert rsi["thresholds"]["label"] == "EMA 21, RSI 14, cell 70/30"
    assert rsi["verdict"] == "FAIL"
    assert rsi.get("green_year_note") in (None, "")
    assert rsi["sides"]["long"] == _RSI_LONG
    assert rsi["sides"]["short"] == _RSI_SHORT
    # 80/20 is not scored. A positive net is still FAIL. No green-year note.
    assert "80/20" not in raw_text
    assert "PASS" not in raw_text
    assert "+2.000" in raw_text
    assert "+1.793333" in raw_text
    assert "+1.345" in raw_text
    assert "+0.511667" in raw_text
    assert "66.7%" in raw_text


def test_shipped_file_loads_four_rows_all_fail() -> None:
    loaded = load_path2_findings()
    assert loaded["sealed"] is True
    assert loaded["load_error"] is None
    assert loaded["note"] == SEALED_TABLE_NOTE
    assert [cell["family"] for cell in loaded["cells"]] == ["macd_ma_agree", "ma_rsi_agree"]
    macd, rsi = loaded["cells"]
    assert macd["thresholds_label"] == "EMA 21 and MACD 12, 26, 9, agreement required"
    assert macd["verdict"] == "FAIL"
    assert macd["green_year_note"] is None
    assert macd["sides"]["long"] == _LONG
    assert macd["sides"]["short"] == _SHORT
    assert rsi["clock"] == "4h"
    assert rsi["thresholds_label"] == "EMA 21, RSI 14, cell 70/30"
    assert rsi["verdict"] == "FAIL"
    assert rsi["green_year_note"] is None
    # Positive nets stay the sealed FAIL. They are not promoted to PASS.
    assert rsi["sides"]["long"]["net_after_0_31_rt"] == "+1.793333"
    assert rsi["sides"]["short"]["net_after_0_31_rt"] == "+0.793333"
    assert rsi["sides"]["long"] == _RSI_LONG
    assert rsi["sides"]["short"] == _RSI_SHORT


def test_zero_cells_stay_empty(tmp_path) -> None:
    path = tmp_path / "findings.json"
    path.write_text(
        json.dumps({"note": SEALED_TABLE_NOTE, "sealed": False, "cells": []}),
        encoding="utf-8",
    )
    loaded = load_path2_findings(path)
    assert loaded["cells"] == []
    assert loaded["sealed"] is False


def test_schema_lists_both_sides_and_metric_columns() -> None:
    schema = json.loads(
        (PROJECT_ROOT / "data" / "research" / "path2_findings.schema.json").read_text(
            encoding="utf-8"
        )
    )
    side = schema["$defs"]["side"]["properties"]
    assert tuple(side) == METRIC_KEYS
    sides = schema["$defs"]["cell"]["properties"]["sides"]
    assert list(sides["properties"]) == ["long", "short"]
    assert sides["required"] == ["long", "short"]
    assert "green_year_note" in schema["$defs"]["cell"]["properties"]
    assert schema["$defs"]["cell"]["properties"]["verdict"]["enum"] == ["PASS", "FAIL", None]


def test_research_page_lists_findings_columns_in_order() -> None:
    html = (PROJECT_ROOT / "api" / "static" / "index.html").read_text(encoding="utf-8")
    labels = [
        "Family",
        "Clock",
        "Side",
        "Frozen thresholds",
        "n",
        "Target-first count",
        "Target-first rate",
        "Gross",
        "Net after 0.31% round trip",
        "Same-shell H=18 base net",
        "Stress stop 2% net",
        "PASS or FAIL",
        "Green year note",
    ]
    start = html.index("const PATH2_FINDING_HEADERS")
    end = html.index("];", start)
    block = html[start:end]
    cursor = 0
    for label in labels:
        found = block.index(f'"{label}"', cursor)
        assert found > cursor or cursor == 0
        cursor = found + 1
    assert "No sealed cells" in html
    assert "does not set PASS or FAIL" in html
    assert "renderPath2Findings()" in html


def test_green_year_note_does_not_set_verdict(tmp_path) -> None:
    path = tmp_path / "findings.json"
    path.write_text(
        json.dumps(
            {
                "note": SEALED_TABLE_NOTE,
                "sealed": True,
                "cells": [
                    {
                        "family": "example_family",
                        "clock": "4h",
                        "thresholds": {"label": "frozen line"},
                        "green_year_note": "one green year",
                        "verdict": "one green year",
                        "sides": {"long": {"n": 4}},
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    cell = load_path2_findings(path)["cells"][0]
    assert cell["verdict"] is None
    assert cell["green_year_note"] == "one green year"
    assert cell["thresholds_label"] == "frozen line"
    assert cell["sides"]["long"]["n"] == 4
    # The short side stays on the cell, with every figure marked absent.
    assert cell["sides"]["short"] == {key: None for key in METRIC_KEYS}
    assert cell["sides"]["long"]["gross"] is None


def test_only_pass_or_fail_tokens_survive(tmp_path) -> None:
    path = tmp_path / "findings.json"
    path.write_text(
        json.dumps(
            {
                "note": SEALED_TABLE_NOTE,
                "sealed": True,
                "cells": [
                    {"verdict": "PASS", "sides": {"long": {}, "short": {}}},
                    {"verdict": "FAIL", "sides": {"long": {}, "short": {}}},
                    {"verdict": "pass", "sides": {"long": {}, "short": {}}},
                    {"verdict": True, "sides": {"long": {}, "short": {}}},
                ],
            }
        ),
        encoding="utf-8",
    )
    verdicts = [cell["verdict"] for cell in load_path2_findings(path)["cells"]]
    assert verdicts == ["PASS", "FAIL", None, None]


def test_bool_and_objects_are_not_metrics(tmp_path) -> None:
    path = tmp_path / "findings.json"
    path.write_text(
        json.dumps(
            {
                "note": SEALED_TABLE_NOTE,
                "sealed": False,
                "cells": [
                    {
                        "sides": {
                            "long": {"n": True, "gross": {"made_up": 1}, "target_first_rate": "kept"},
                            "short": {"n": False},
                        }
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    cell = load_path2_findings(path)["cells"][0]
    assert cell["sides"]["long"]["n"] is None
    assert cell["sides"]["long"]["gross"] is None
    assert cell["sides"]["long"]["target_first_rate"] == "kept"
    assert cell["sides"]["short"]["n"] is None


def test_floor_helper_returns_the_sealed_rows() -> None:
    from firm.orchestrator import _safe_path2_findings

    loaded = _safe_path2_findings()
    assert loaded["sealed"] is True
    assert [cell["family"] for cell in loaded["cells"]] == ["macd_ma_agree", "ma_rsi_agree"]
    assert [cell["verdict"] for cell in loaded["cells"]] == ["FAIL", "FAIL"]
    assert all(cell["green_year_note"] is None for cell in loaded["cells"])
