"""Runtime wire for impulse_pullback_continuation Option B (MCP size constraint).

Registers clock, catalog row, sleeve spec, validate kit, and infer_family
without rewriting the large tip files. Do not set approved=true. No walk.
Live stays off. Soft-watch 165 + three_black_crows + sma20_stretch_fade
EXPLICIT. Protect 12+56.
"""

from __future__ import annotations

_APPLIED = False


def apply() -> None:
    global _APPLIED
    if _APPLIED:
        return
    _APPLIED = True

    from core.strategy.sleeve_spec import SleeveSpec
    from firm import research_jobs
    from firm.research_catalog import RESEARCH_HYPOTHESES
    from firm.sleeve_factory import CANDIDATE_SPECS
    from research import validate

    research_jobs.CLOCK_BY_FAMILY["impulse_pullback_continuation"] = "4h/4h"

    _orig_infer = research_jobs.infer_family

    def infer_family(payload, title=""):  # type: ignore[no-untyped-def]
        payload = payload or {}
        blob = " ".join(
            [str(payload.get("name") or ""), str(payload.get("family") or ""), title]
        ).lower()
        if (
            "impulse_pullback_continuation" in blob
            or "impulse pullback continuation" in blob
            or "impulse_pullback_cont" in blob
        ):
            return "impulse_pullback_continuation"
        return _orig_infer(payload, title)

    research_jobs.infer_family = infer_family  # type: ignore[assignment]

    if not any(r.get("family") == "impulse_pullback_continuation" for r in RESEARCH_HYPOTHESES):
        RESEARCH_HYPOTHESES.append(
            {
                "id": "impulse_pullback_continuation@4h/4h",
                "family": "impulse_pullback_continuation",
                "name": "impulse_pullback_continuation 4h/4h BOTH",
                "clock": "4h/4h",
                "side": "BOTH",
                "rank": 66,
                "coded": True,
                "free_params": 2,
                "disposition": "new_family",
                "justification": (
                    "Garwe LOCK PASS + Brian Inbox YES for coding only. "
                    "Option B exploratory: SCORE/RETIRE. Do not set "
                    "approved=true. Live stays off. Walk-forward is not "
                    "started from this coding PR. 0 book cells. Protect "
                    "12+56. Soft-watch EXPLICIT: impulse_midpoint_fail_fade "
                    "(Job 165 RETIRE) + three_black_crows + sma20_stretch_fade "
                    "— theme adjacency only, not soft-clone. Geometry "
                    "OPPOSITE of 165: after directional impulse (W=2 "
                    "close-to-close %), shallow pullback that does NOT take "
                    "impulse start extreme, then break of pullback extreme "
                    "→ CONTINUE (mid_anchor=false, fail_of_impulse=false). "
                    "Regime gate REQUIRED aligned_200sma (1d close vs "
                    "SMA200 permission layer from shell §1.3 — NOT a "
                    "sma20_stretch_fade signal). Fill next_open / engine "
                    "t+1 ONLY — forbid signal-close fill. Free ≤2: "
                    "pullback_max_retrace_frac [0.38, 0.50], "
                    "impulse_min_close_pct [1.5, 2.0]. Locked shell: "
                    "TP=0.03 S∈{0.015,0.02} H=18. BOTH LONG priority. "
                    "No VP/session VWAP. No EMA/MACD/Elder pullback entry."
                ),
                "param_change": {"clock": "4h/4h"},
                "needs_feed": False,
            }
        )

    if not any(s.name == "impulse_pullback_continuation" for s in CANDIDATE_SPECS):
        CANDIDATE_SPECS.append(
            SleeveSpec(
                name="impulse_pullback_continuation",
                template="novel",
                clock="4h/4h",
                side="BOTH",
                needs_feed=False,
                needs_new_indicator=False,
                novel_reason=(
                    "Impulse → shallow PB (no take extreme) → break PB "
                    "extreme CONTINUE. Option B. No approved=true. "
                    "OPPOSITE Job 165 mid-fail fade. mid_anchor=false, "
                    "fail_of_impulse=false. Regime aligned_200sma REQUIRED "
                    "(permission ≠ sma20_stretch_fade). Soft-watch 165 + "
                    "three_black_crows + sma20_stretch_fade EXPLICIT. "
                    "Free pullback_max_retrace_frac and "
                    "impulse_min_close_pct only."
                ),
                summary=(
                    "After a 4h directional impulse and shallow pullback "
                    "that holds the impulse extreme, continue on break of "
                    "pullback extreme at next_open (aligned 200SMA gate)."
                ),
                justification=(
                    "Option B SCORE/RETIRE only. Do not set approved=true. "
                    "Live stays off. Soft-watch 165 + three_black_crows + "
                    "sma20_stretch_fade EXPLICIT."
                ),
            )
        )

    _orig_kit = validate.strategy_kit

    def strategy_kit(name, side):  # type: ignore[no-untyped-def]
        if name == "impulse_pullback_continuation":
            from core.strategy.impulse_pullback_continuation import (
                ImpulsePullbackContinuationParams,
                ImpulsePullbackContinuationStrategy,
            )

            def factory(params):  # type: ignore[no-untyped-def]
                return ImpulsePullbackContinuationStrategy(params)

            base = ImpulsePullbackContinuationParams(side=side)
            space = {
                "pullback_max_retrace_frac": [0.38, 0.50],
                "impulse_min_close_pct": [1.5, 2.0],
                "take_profit_pct": [0.03],
                "stop_loss_pct": [0.015, 0.02],
            }
            return factory, base, space
        return _orig_kit(name, side)

    validate.strategy_kit = strategy_kit  # type: ignore[assignment]


apply()
