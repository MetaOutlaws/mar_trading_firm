"""Eager-load helper for donchian_n_fail_reversion Option B wire.

Kit-path registration: research/validate.py already eager-loads body_gap wire
(PR #81); that wire chains broken_swing, two_bar, amihud, and this apply when
MCP cannot rewrite the large validate.py tip. Params module also calls apply
on import. Do not set approved=true. Live stays off. Soft-watch Jobs 119+167.
"""

from __future__ import annotations

try:
    from firm.donchian_n_fail_reversion_wire import apply as _apply_donchian_n_fail_reversion_wire

    _apply_donchian_n_fail_reversion_wire()
except Exception:
    pass
