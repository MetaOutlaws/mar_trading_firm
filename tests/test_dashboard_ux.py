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


def test_floor_tab_is_process_view_not_job_list():
    """Floor shows the firm workflow. Validator job cards stay on Research."""
    html = _html()
    assert "function floorWorkflowCard(" in html
    start = html.index("function renderFloor()")
    end = html.index("function floorWorkflowCard()")
    floor_body = html[start:end]
    assert "floorWorkflowCard()" in floor_body
    assert "pipelineCard()" not in floor_body
    assert "job-list" not in floor_body
    assert "Hypothesis" in html
    assert "COO ONE" in html
    assert "CEO YES" in html
    assert "function renderResearch(" in html
    research_fn = html[html.index("function renderResearch()"):html.index("function sentimentDesk()")]
    assert "pipelineCard()" in research_fn
    assert "Walk-forward jobs" in html
    assert "jobs live on research" in html.lower()
    assert "Live ${esc(book.live" in html or "Live ${esc(book.live ||" in html
    assert "who_waits" in html
    assert "buffer-card" in html
    assert "now-job" in html
    assert "PIPELINE_AUTO_ADVANCE" not in html
