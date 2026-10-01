"""Eager-load helper for two_bar_run_mid_fail Option B wire.

Kit-path registration: research/validate.py already eager-loads body_gap wire
(PR #81); that wire chains broken_swing (PR #82) and this apply when MCP cannot
rewrite the large validate.py tip. Params module also calls apply on import.
Do not set approved=true. Live stays off. Soft-watch Job 165.
"""

from __future__ import annotations

try:
    from firm.two_bar_run_mid_fail_wire import apply as _apply_two_bar_run_mid_fail_wire

    _apply_two_bar_run_mid_fail_wire()
except Exception:
    pass
