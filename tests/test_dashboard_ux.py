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


def _slice(html: str, start: str, end: str) -> str:
    begin = html.index(start)
    stop = html.index(end, begin + len(start))
    return html[begin:stop]


def test_observers_tab_replaces_f111_and_keeps_the_hourly_book():
    """Observers slot, F111/BL8 chips, deskbar pulses. Hourly tabs stay hourly."""
    html = _html()
    assert "function renderDeskbar(" in html
    assert "function renderObservers(" in html
    assert "function renderF111(" not in html
    assert '["observers", "Observers"]' in html
    assert '["f111", "F111"]' not in html.split("OBSERVER_CHIPS", 1)[0]
    assert 'const OBSERVER_CHIPS = [["f111", "F111"], ["bl8", "BL8"]];' in html
    assert 'const OBSERVER_KEY = "deskObserver";' in html
    assert "localStorage.getItem(OBSERVER_KEY)" in html
    assert "localStorage.setItem(OBSERVER_KEY, id)" in html
    assert "function openObserver(" in html
    assert "Isolated · not in live book" in html
    assert "scan complete" in html
    assert "scan incomplete" in html
    assert "retCode 10006" in html
    assert 'id="deskbar"' in html
    assert "get(\"/api/desk\")" in html
    assert 'get("/api/observers")' in html
    assert 'get("/api/f111")' not in html
    assert "Live book" in html
    assert "source_mtime" in html
    assert "Ack stale" in html
    assert "/api/escalations/ack-stale" in html
    assert "pending_retests" in html
    assert "closed_by_reason" in html
    assert "bar close" in html
    assert "llm_seats_enabled === false" in html
    assert "LLM seats disabled" in html
    assert "Book overrides" in html
    assert "Sitting out (regime)" in html
    assert "Active ${scan.active}" in html
    assert "Active ${counts.active}" in html
    assert "Legacy LLM record" in html
    assert "legacy_llm" in html
    assert 'get("/api/regime")' in html
    assert 'get("/api/trades?limit=100")' in html
    blotter = _slice(html, "function renderBlotter(", "function tradeRow(")
    positions = _slice(html, "function renderPositions(", "function positionsTable(")
    strategies = _slice(html, "function renderStrategies(", "function renderGates(")
    assert "state.trades" in blotter
    assert "bl8" not in blotter.lower()
    assert "observers" not in blotter
    assert "state.risk.open_positions" in positions
    assert "bl8" not in positions.lower()
    assert "state.strategies" in strategies
    assert "bl8" not in strategies.lower()
    assert "/api/observers" not in blotter
    assert "/api/observers" not in positions
    assert "/api/observers" not in strategies


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
