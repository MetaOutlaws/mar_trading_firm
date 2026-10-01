"""Runtime wire for two_bar_run_mid_fail Option B (MCP size constraint).

Registers clock, catalog row, sleeve spec, validate kit, and infer_family
without rewriting the large tip files. Do not set approved=true. No walk.
Live stays off. Soft-watch Job 165. Protect 12+56.
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

    research_jobs.CLOCK_BY_FAMILY["two_bar_run_mid_fail"] = "4h/4h"

    _orig_infer = research_jobs.infer_family

    def infer_family(payload, title=""):  # type: ignore[no-untyped-def]
        payload = payload or {}
        blob = " ".join(
            [str(payload.get("name") or ""), str(payload.get("family") or ""), title]
        ).lower()
        if (
            "two_bar_run_mid_fail" in blob
            or "two bar run mid" in blob
            or "two_bar_run_mid" in blob
        ):
            return "two_bar_run_mid_fail"
        return _orig_infer(payload, title)

    research_jobs.infer_family = infer_family  # type: ignore[assignment]

    if not any(r.get("family") == "two_bar_run_mid_fail" for r in RESEARCH_HYPOTHESES):
        RESEARCH_HYPOTHESES.append(
            {
                "id": "two_bar_run_mid_fail@4h/4h",
                "family": "two_bar_run_mid_fail",
                "name": "two_bar_run_mid_fail 4h/4h BOTH",
                "clock": "4h/4h",
                "side": "BOTH",
                "rank": 62,
                "coded": True,
                "free_params": 1,
                "disposition": "new_family",
                "justification": (
                    "Garwe STAMP LOCK + Brian Inbox YES for coding only. "
                    "Option B exploratory: SCORE/RETIRE. Do not set "
                    "approved=true. Live stays off. Walk-forward is not "
                    "started from this coding PR. 0 book cells. Protect "
                    "12+56. Soft-watch Job 165 impulse_midpoint_fail_fade "
                    "EXPLICIT: 165 = ONE impulse bar + extreme_frac on that "
                    "bar + next through THAT bar mid; this = TWO same-color "
                    "consecutive closes + monotonic; envelope mid of both "
                    "bars; NO extreme_frac; FORBID single-bar mid as signal "
                    "level. Free: min_range_atr [1.0, 1.5] only (≤2 free). "
                    "Locked: ATR20 atr.shift(1) causal, fill t+1, two-bar "
                    "envelope mid. No VP/session VWAP/gap-open."
                ),
                "param_change": {"clock": "4h/4h"},
                "needs_feed": False,
            }
        )

    if not any(s.name == "two_bar_run_mid_fail" for s in CANDIDATE_SPECS):
        CANDIDATE_SPECS.append(
            SleeveSpec(
                name="two_bar_run_mid_fail",
                template="novel",
                clock="4h/4h",
                side="BOTH",
                needs_feed=False,
                needs_new_indicator=False,
                novel_reason=(
                    "Two same-color consecutive closes + monotonic run; "
                    "next close through TWO-BAR H-L envelope mid. Option B. "
                    "No approved=true. FORBID extreme_frac / single-bar mid "
                    "(neq Job 165). Soft-watch Job 165. Free min_range_atr "
                    "only."
                ),
                summary=(
                    "After a 4h two-bar same-color monotonic run sized by "
                    "min_range_atr*ATR20, fade when close crosses the "
                    "two-bar envelope mid."
                ),
                justification=(
                    "Option B SCORE/RETIRE only. Do not set approved=true. "
                    "Live stays off. Soft-watch Job 165 EXPLICIT."
                ),
            )
        )

    _orig_kit = validate.strategy_kit

    def strategy_kit(name, side):  # type: ignore[no-untyped-def]
        if name == "two_bar_run_mid_fail":
            from core.strategy.two_bar_run_mid_fail import (
                TwoBarRunMidFailParams,
                TwoBarRunMidFailStrategy,
            )

            def factory(params):  # type: ignore[no-untyped-def]
                return TwoBarRunMidFailStrategy(params)

            base = TwoBarRunMidFailParams(side=side)
            space = {
                "min_range_atr": [1.0, 1.5],
                "take_profit_pct": [0.03, 0.05],
                "stop_loss_pct": [0.02, 0.03],
            }
            return factory, base, space
        return _orig_kit(name, side)

    validate.strategy_kit = strategy_kit  # type: ignore[assignment]


apply()
