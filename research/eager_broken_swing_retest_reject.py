"""Eager-load helper for broken_swing_retest_reject Option B wire.

Kit-path registration: research/validate.py already eager-loads body_gap wire
(PR #81); that wire chains this apply when MCP cannot rewrite the large
validate.py tip. Params module also calls apply on import. Do not set
approved=true. Live stays off.
"""

from __future__ import annotations

try:
    from firm.broken_swing_retest_reject_wire import apply as _apply_broken_swing_retest_reject_wire

    _apply_broken_swing_retest_reject_wire()
except Exception:
    pass
