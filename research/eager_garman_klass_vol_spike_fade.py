"""Eager-load helper for garman_klass_vol_spike_fade Option B wire.

Kit-path registration: research/validate.py already eager-loads body_gap wire
(PR #81); that wire chains broken_swing (PR #82), two_bar, amihud, donchian,
and this apply when MCP cannot rewrite the large validate.py tip. Params
module also calls apply on import. Do not set approved=true. Live stays off.
Soft-watch Job 172 EXPLICIT.
"""

from __future__ import annotations

try:
    from firm.garman_klass_vol_spike_fade_wire import apply as _apply_garman_klass_vol_spike_fade_wire

    _apply_garman_klass_vol_spike_fade_wire()
except Exception:
    pass
