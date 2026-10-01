"""Runtime wire for amihud_illiquidity_spike_fade Option B (MCP size constraint).

Registers clock, catalog row, sleeve spec, validate kit, and infer_family
without rewriting the large tip files. Do not set approved=true. No walk.
Live stays off. Soft-watch Job 103 EXPLICIT. Protect 12+56.
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

    research_jobs.CLOCK_BY_FAMILY["amihud_illiquidity_spike_fade"] = "4h/4h"

    _orig_infer = research_jobs.infer_family

    def infer_family(payload, title=""):  # type: ignore[no-untyped-def]
        payload = payload or {}
        blob = " ".join(
            [str(payload.get("name") or ""), str(payload.get("family") or ""), title]
        ).lower()
        if (
            "amihud_illiquidity_spike_fade" in blob
            or "amihud illiquidity" in blob
            or "amihud_illiquidity" in blob
        ):
            return "amihud_illiquidity_spike_fade"
        return _orig_infer(payload, title)

    research_jobs.infer_family = infer_family  # type: ignore[assignment]

    if not any(r.get("family") == "amihud_illiquidity_spike_fade" for r in RESEARCH_HYPOTHESES):
        RESEARCH_HYPOTHESES.append(
            {
                "id": "amihud_illiquidity_spike_fade@4h/4h",
                "family": "amihud_illiquidity_spike_fade",
                "name": "amihud_illiquidity_spike_fade 4h/4h BOTH",
                "clock": "4h/4h",
                "side": "BOTH",
                "rank": 63,
                "coded": True,
                "free_params": 2,
                "disposition": "new_family",
                "justification": (
                    "Garwe STAMP LOCK + Brian Inbox YES for coding only. "
                    "Option B exploratory: SCORE/RETIRE. Do not set "
                    "approved=true. Live stays off. Walk-forward is not "
                    "started from this coding PR. 0 book cells. Protect "
                    "12+56. Soft-watch Job 103 turnover_climax_rejection_fade "
                    "EXPLICIT: 103 = turnover NEW 20-bar high + break "
                    "prior-20 H/L + close reject_frac inside climax bar; "
                    "this = Amihud |ret|/turnover (or volume*close) z-spike "
                    "vs prior lookback; fade spike-bar body direction; NO "
                    "prior H/L break; NO reject_frac; FORBID extreme_frac / "
                    "next-thru-mid / CLV. Free: lookback [20, 40], z_min "
                    "[2.0, 2.5]. Locked: causal z (mean/std of PRIOR "
                    "lookback only via shift), fill t+1, prefer existing "
                    "turnover/quote_volume else volume*close (no new feed). "
                    "No VP/session VWAP."
                ),
                "param_change": {"clock": "4h/4h"},
                "needs_feed": False,
            }
        )

    if not any(s.name == "amihud_illiquidity_spike_fade" for s in CANDIDATE_SPECS):
        CANDIDATE_SPECS.append(
            SleeveSpec(
                name="amihud_illiquidity_spike_fade",
                template="novel",
                clock="4h/4h",
                side="BOTH",
                needs_feed=False,
                needs_new_indicator=False,
                novel_reason=(
                    "Amihud |ret|/turnover z-spike; fade spike-bar body. "
                    "Option B. No approved=true. FORBID extreme_frac / "
                    "next-thru-mid / CLV (neq Job 103 climax+reject_frac). "
                    "Soft-watch Job 103. Free lookback and z_min only."
                ),
                summary=(
                    "After a 4h Amihud illiquidity z-spike vs prior "
                    "lookback, fade the spike bar's body direction at t+1."
                ),
                justification=(
                    "Option B SCORE/RETIRE only. Do not set approved=true. "
                    "Live stays off. Soft-watch Job 103 EXPLICIT."
                ),
            )
        )

    _orig_kit = validate.strategy_kit

    def strategy_kit(name, side):  # type: ignore[no-untyped-def]
        if name == "amihud_illiquidity_spike_fade":
            from core.strategy.amihud_illiquidity_spike_fade import (
                AmihudIlliquiditySpikeFadeParams,
                AmihudIlliquiditySpikeFadeStrategy,
            )

            def factory(params):  # type: ignore[no-untyped-def]
                return AmihudIlliquiditySpikeFadeStrategy(params)

            base = AmihudIlliquiditySpikeFadeParams(side=side)
            space = {
                "lookback": [20, 40],
                "z_min": [2.0, 2.5],
                "take_profit_pct": [0.03, 0.05],
                "stop_loss_pct": [0.02, 0.03],
            }
            return factory, base, space
        return _orig_kit(name, side)

    validate.strategy_kit = strategy_kit  # type: ignore[assignment]


apply()
