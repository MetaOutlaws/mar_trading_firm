"""Eager-load helper for impulse_pullback_continuation Option B wire.

Kit-path registration: research/validate.py already eager-loads body_gap wire
(PR #81); that wire chains broken_swing (PR #82), two_bar, amihud, donchian,
garman_klass, and this apply when MCP cannot rewrite the large validate.py tip.
Params module also calls apply on import. Do not set approved=true. Live stays
off. Soft-watch 165 + three_black_crows + sma20_stretch_fade EXPLICIT.
"""

from __future__ import annotations

try:
    from firm.impulse_pullback_continuation_wire import apply as _apply_impulse_pullback_continuation_wire

    _apply_impulse_pullback_continuation_wire()
except Exception:
    pass
