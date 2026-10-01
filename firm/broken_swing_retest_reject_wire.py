"""Runtime wire for broken_swing_retest_reject Option B (MCP size constraint).

Registers clock, catalog row, sleeve spec, validate kit, and infer_family
without rewriting the large tip files. Do not set approved=true. No walk.
Live stays off. Soft-watch Job 153. Protect 12+56.
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

    research_jobs.CLOCK_BY_FAMILY["broken_swing_retest_reject"] = "4h/4h"

    _orig_infer = research_jobs.infer_family

    def infer_family(payload, title=""):  # type: ignore[no-untyped-def]
        payload = payload or {}
        blob = " ".join(
            [str(payload.get("name") or ""), str(payload.get("family") or ""), title]
        ).lower()
        if (
            "broken_swing_retest_reject" in blob
            or "broken swing retest" in blob
            or "broken_swing_retest" in blob
        ):
            return "broken_swing_retest_reject"
        return _orig_infer(payload, title)

    research_jobs.infer_family = infer_family  # type: ignore[assignment]

    if not any(r.get("family") == "broken_swing_retest_reject" for r in RESEARCH_HYPOTHESES):
        RESEARCH_HYPOTHESES.append(
            {
                "id": "broken_swing_retest_reject@4h/4h",
                "family": "broken_swing_retest_reject",
                "name": "broken_swing_retest_reject 4h/4h BOTH",
                "clock": "4h/4h",
                "side": "BOTH",
                "rank": 61,
                "coded": True,
                "free_params": 2,
                "disposition": "new_family",
                "justification": (
                    "Garwe STAMP LOCK + Brian Inbox YES for coding only. "
                    "Option B exploratory: SCORE/RETIRE. Do not set "
                    "approved=true. Live stays off. Walk-forward is not "
                    "started from this coding PR. 0 book cells. Protect "
                    "12+56. Soft-watch Job 153 swing_break_fail_reversion: "
                    "this sleeve is CONTINUATION-ONLY after a prior CLOSE-"
                    "break of swing H/L; within retest_bars a retest rejects "
                    "and close STAYS on the break side. FORBID close back "
                    "through swing (=153 fail-reversion territory). Free: "
                    "swing_lookback [5, 8], retest_bars [3, 6]. Locked: "
                    "ATR20, fill t+1, pivot lookback max/min (stamp 3/3), "
                    "require_reject_close. No VP/session VWAP/calendar/"
                    "wick-only unbroken pierce (=89)."
                ),
                "param_change": {"clock": "4h/4h"},
                "needs_feed": False,
            }
        )

    if not any(s.name == "broken_swing_retest_reject" for s in CANDIDATE_SPECS):
        CANDIDATE_SPECS.append(
            SleeveSpec(
                name="broken_swing_retest_reject",
                template="novel",
                clock="4h/4h",
                side="BOTH",
                needs_feed=False,
                needs_new_indicator=False,
                novel_reason=(
                    "Prior close-break of swing H/L then delayed retest "
                    "reject with close staying on break side "
                    "(continuation). Option B. No approved=true. FORBID "
                    "close-through (=153). Soft-watch Job 153. Free "
                    "swing_lookback and retest_bars only."
                ),
                summary=(
                    "After a 4h close-break of lookback swing H/L, within "
                    "retest_bars a retest rejects; close stays on break side."
                ),
                justification=(
                    "Option B SCORE/RETIRE only. Do not set approved=true. "
                    "Live stays off. Soft-watch Job 153."
                ),
            )
        )

    _orig_kit = validate.strategy_kit

    def strategy_kit(name, side):  # type: ignore[no-untyped-def]
        if name == "broken_swing_retest_reject":
            from core.strategy.broken_swing_retest_reject import (
                BrokenSwingRetestRejectParams,
                BrokenSwingRetestRejectStrategy,
            )

            def factory(params):  # type: ignore[no-untyped-def]
                return BrokenSwingRetestRejectStrategy(params)

            base = BrokenSwingRetestRejectParams(side=side)
            space = {
                "swing_lookback": [5, 8],
                "retest_bars": [3, 6],
                "take_profit_pct": [0.03, 0.05],
                "stop_loss_pct": [0.02, 0.03],
            }
            return factory, base, space
        return _orig_kit(name, side)

    validate.strategy_kit = strategy_kit  # type: ignore[assignment]


apply()
