"""Dashboard density UX: grouping, pagination, and collapse hooks.

These checks pin the operator-facing contract in api/static/index.html.
They do not start walk-forwards or touch approved_strategies.json.
"""

import json
from pathlib import Path

DASHBOARD = Path(__file__).resolve().parents[1] / "api" / "static" / "index.html"
PATH2_BAR = DASHBOARD.parent / "path2_research.json"
PATH2_SCAN = ["current-bar", "open-path", "kill-class", "closed-studies", "pipeline"]


def _html() -> str:
    return DASHBOARD.read_text(encoding="utf-8")


def test_on_paper_groups_by_family_and_keeps_research_copy():
    html = _html()
    assert "function groupPaperOverrides(" in html
    assert "function paperFamilyPfLabel(" in html
    assert "best PF" in html
    assert "These sleeves still fail research, so they are not in Approved. Paper scans them for fills. Live stays locked." in html
    assert "paperFamQ" in html
    assert "onclick='toggleCollapse(" in html


def test_next_tests_paginate_five_display_only():
    html = _html()
    assert "nextTests: 5," in html
    assert "Display-only pagination. Does not start, gate, or skip walk-forwards." in html
    assert "PIPELINE_AUTO_ADVANCE" not in html


def test_duty_board_and_who_runs_default_collapsed():
    html = _html()
    assert 'collapsibleCard("dutyBoard", "Duty board"' in html
    assert "defaultCollapsed: true" in html
    assert 'collapsibleCard("whoRunsOps", "Who runs daily ops"' in html
    assert "firmCollapse" in html
    assert "${duties.length} on track" in html


def test_sentiment_tab_l1_clarity_contract():
    """Pin Luke's L1 desk shape. Display only — no trade calls, no WF."""
    html = _html()
    assert "function renderSentiment(" in html
    assert "function sentimentTakeaways(" in html
    assert "function splitMarketNarrative(" in html
    assert "desk.headline" in html
    assert "desk.takeaways" in html
    assert "Watch|Fit" in html
    assert "narrative-split" in html
    assert "heat-narrative" in html
    assert "s.as_of" in html
    assert "n=" in html
    assert "fade" in html and "breakout" in html and "session" in html and "candle" in html
    assert r"[\s.,;:!?]+$" in html
    assert "inf-note" in html
    assert "L1 display only" in html
    assert "Market narrative" in html


def _path2_bar(html: str) -> dict:
    start = html.index('<script type="application/json" id="path2-research">')
    end = html.index("</script>", start)
    embedded = json.loads(html[start:end].split(">", 1)[1])
    on_disk = json.loads(PATH2_BAR.read_text(encoding="utf-8"))
    assert embedded == on_disk
    return embedded


def test_research_tab_path2_scan_is_display_only():
    """Research opens on the Path2 bar. The old queue stays, collapsed.

    Copy is quoted into the page. This test does not recompute census cells
    and does not touch gates, the book, or walk-forward jobs.
    """
    html = _html()
    bar = _path2_bar(html)
    block = html.split("const PATH2_SCAN = [", 1)[1].split("];", 1)[0]
    positions = [block.index(section_id) for section_id in PATH2_SCAN]
    assert positions == sorted(positions)
    assert list(bar["headlines"]) == PATH2_SCAN
    assert "return path2Panel() + collapsibleCard(" in html
    catalog_at = html.index('collapsibleCard("researchCatalog", "Catalog and walk-forward queue"')
    assert "defaultCollapsed: true" in html[catalog_at:catalog_at + 400]
    assert "Display-only pagination. Does not start, gate, or skip walk-forwards." in html
    assert "Approve &amp; start" in html
    assert "codeFamily(" in html

    constraints = bar["constraints"]["headline"] + " " + bar["constraints"]["detail"]
    assert "Paper only" in constraints
    assert "Live OFF" in constraints
    assert "12 approved + 56 paper_override" in constraints
    assert "Not Inbox until PASS" in constraints

    rules = " ".join(bar["current_bar"]["rules"])
    assert "net expR > 0" in rules
    assert "−0.211" in rules and "−0.234" in rules
    assert "No side-cut" in rules
    assert "40.2%" in bar["current_bar"]["scale"]

    paths = {row["id"]: row["status"] for row in bar["paths"]}
    assert paths == {"Path1": "CLOSED", "Path2": "OPEN", "Path3": "NO"}

    killed = {item["name"]: item.get("job", "") for item in bar["kill_class"]["items"]}
    assert killed["donchian_n_fail_reversion"] == "173"
    assert killed["swing_break_fail_reversion"] == "153"
    assert any("volume_dryup_range_fail" in item["detail"] for item in bar["kill_class"]["items"])
    assert any("SMA50/200" in name for name in killed)

    studies = {item["name"]: item["status"] for item in bar["closed_studies"]["items"]}
    assert studies["BTC movement census"] == "FAIL"
    assert studies["ETH census"] == "STOP"
    assert studies["MA cross selectors"] == "FAIL"
    assert studies["Operator GC/death playbook 15m"] == "FAIL"
    gc = next(
        item for item in bar["closed_studies"]["items"] if item["name"].startswith("Operator GC")
    )
    assert "n=608" in gc["detail"] and "−0.062" in gc["detail"]
    nets = [row["net"] for row in bar["closed_studies"]["base_rows"]]
    assert nets == ["−0.2106", "−0.2344"]

    whos = [step["who"] for step in bar["pipeline"]["steps"]]
    assert whos == ["Shumba", "Garwe", "Munha", "Brian", "Then"]
    assert "Protect 12+56" in bar["pipeline"]["not"]
    assert "No walk from this panel" in bar["pipeline"]["not"]
