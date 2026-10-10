"""Dashboard density UX: grouping, pagination, and collapse hooks.

These checks pin the operator-facing contract in api/static/index.html.
They do not start walk-forwards or touch approved_strategies.json.
"""

from pathlib import Path

DASHBOARD = Path(__file__).resolve().parents[1] / "api" / "static" / "index.html"


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


def test_desk_header_f111_panel_and_live_book_are_wired():
    """Display contract for the header, F111 tab, and live strategy book."""
    html = _html()
    assert "function renderDeskbar(" in html
    assert "function renderF111(" in html
    assert '["f111", "F111"]' in html
    assert 'id="deskbar"' in html
    assert "get(\"/api/desk\")" in html
    assert "get(\"/api/f111\")" in html
    assert "Live book" in html
    assert "source_mtime" in html
    assert "Ack stale" in html
    assert "/api/escalations/ack-stale" in html
    assert "pending_retests" in html
    assert "closed_by_reason" in html
    assert "bar close" in html


def test_hardcoded_status_notes_are_gone():
    """RSI/golden-cross template text and a frozen pair/veto count are not status."""
    html = _html()
    assert "RSI + golden-cross" not in html
    assert "40 pairs/50 vetoes" not in html
    assert "478 simulated rsi_trend" not in html
    assert "given RSI and Donchian" not in html


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
