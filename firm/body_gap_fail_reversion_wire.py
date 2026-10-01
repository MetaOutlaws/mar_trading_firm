"""Runtime wire for body_gap_fail_reversion Option B (MCP size constraint).

Registers clock, catalog row, sleeve spec, validate kit, and infer_family
without rewriting the large tip files. Do not set approved=true. No walk.
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

    research_jobs.CLOCK_BY_FAMILY["body_gap_fail_reversion"] = "4h/4h"

    _orig_infer = research_jobs.infer_family

    def infer_family(payload, title=""):  # type: ignore[no-untyped-def]
        payload = payload or {}
        blob = " ".join(
            [str(payload.get("name") or ""), str(payload.get("family") or ""), title]
        ).lower()
        if (
            "body_gap_fail_reversion" in blob
            or "body gap fail" in blob
            or "body_gap_fail" in blob
        ):
            return "body_gap_fail_reversion"
        return _orig_infer(payload, title)

    research_jobs.infer_family = infer_family  # type: ignore[assignment]

    if not any(r.get("family") == "body_gap_fail_reversion" for r in RESEARCH_HYPOTHESES):
        RESEARCH_HYPOTHESES.append(
            {
                "id": "body_gap_fail_reversion@4h/4h",
                "family": "body_gap_fail_reversion",
                "name": "body_gap_fail_reversion 4h/4h BOTH",
                "clock": "4h/4h",
                "side": "BOTH",
                "rank": 60,
                "coded": True,
                "free_params": 2,
                "disposition": "new_family",
                "justification": (
                    "Garwe stamp + Brian YES for coding only. Option B "
                    "exploratory: SCORE/RETIRE. Do not set approved=true. "
                    "Live stays off. Walk-forward is not started from this "
                    "coding PR. 0 book cells. Protect 12+56. Fade a 4h bar "
                    "that opens outside prior H/L by min_gap_atr*ATR20 and "
                    "closes back inside prior H-L. FORBID follow body "
                    "(neq Job 143 displacement_gap_follow). Free: "
                    "min_gap_atr [0.10, 0.25], min_prior_range_atr [0.5, 1.0]."
                ),
                "param_change": {"clock": "4h/4h"},
                "needs_feed": False,
            }
        )

    if not any(s.name == "body_gap_fail_reversion" for s in CANDIDATE_SPECS):
        CANDIDATE_SPECS.append(
            SleeveSpec(
                name="body_gap_fail_reversion",
                template="novel",
                clock="4h/4h",
                side="BOTH",
                needs_feed=False,
                needs_new_indicator=False,
                novel_reason=(
                    "Bar-to-bar open gap outside prior H/L then close reclaim "
                    "inside prior range. Option B. No approved=true. FORBID "
                    "follow (neq Job 143). Free min_gap_atr and "
                    "min_prior_range_atr only."
                ),
                summary=(
                    "Fade a 4h open that gaps outside the prior bar by "
                    "min_gap*ATR20 and closes back inside prior H-L."
                ),
                justification=(
                    "Option B SCORE/RETIRE only. No approved=true. Live stays off."
                ),
            )
        )

    _orig_kit = validate.strategy_kit

    def strategy_kit(name, side):  # type: ignore[no-untyped-def]
        if name == "body_gap_fail_reversion":
            from core.strategy.body_gap_fail_reversion import (
                BodyGapFailReversionParams,
                BodyGapFailReversionStrategy,
            )

            def factory(params):  # type: ignore[no-untyped-def]
                return BodyGapFailReversionStrategy(params)

            base = BodyGapFailReversionParams(side=side)
            space = {
                "min_gap_atr": [0.10, 0.25],
                "min_prior_range_atr": [0.5, 1.0],
                "take_profit_pct": [0.03, 0.05],
                "stop_loss_pct": [0.02, 0.03],
            }
            return factory, base, space
        return _orig_kit(name, side)

    validate.strategy_kit = strategy_kit  # type: ignore[assignment]

    # Option B sibling eager-load (MCP size: avoid rewriting research/validate.py).
    # validate.py already calls this body_gap apply() on kit path; chain siblings here.
    try:
        from firm.broken_swing_retest_reject_wire import apply as _apply_broken_swing_retest_reject_wire

        _apply_broken_swing_retest_reject_wire()
    except Exception:
        pass

    try:
        from firm.two_bar_run_mid_fail_wire import apply as _apply_two_bar_run_mid_fail_wire

        _apply_two_bar_run_mid_fail_wire()
    except Exception:
        pass

    try:
        from firm.amihud_illiquidity_spike_fade_wire import apply as _apply_amihud_illiquidity_spike_fade_wire

        _apply_amihud_illiquidity_spike_fade_wire()
    except Exception:
        pass


apply()
