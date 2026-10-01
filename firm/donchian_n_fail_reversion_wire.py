"""Runtime wire for donchian_n_fail_reversion Option B (MCP size constraint).

Registers clock, catalog row, sleeve spec, validate kit, and infer_family
without rewriting the large tip files. Do not set approved=true. No walk.
Live stays off. Soft-watch Jobs 119 + 167 EXPLICIT. Protect 12+56.
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

    research_jobs.CLOCK_BY_FAMILY["donchian_n_fail_reversion"] = "4h/4h"

    _orig_infer = research_jobs.infer_family

    def infer_family(payload, title=""):  # type: ignore[no-untyped-def]
        payload = payload or {}
        blob = " ".join(
            [str(payload.get("name") or ""), str(payload.get("family") or ""), title]
        ).lower()
        if (
            "donchian_n_fail_reversion" in blob
            or "donchian n fail" in blob
            or "donchian_n_fail" in blob
        ):
            return "donchian_n_fail_reversion"
        return _orig_infer(payload, title)

    research_jobs.infer_family = infer_family  # type: ignore[assignment]

    if not any(r.get("family") == "donchian_n_fail_reversion" for r in RESEARCH_HYPOTHESES):
        RESEARCH_HYPOTHESES.append(
            {
                "id": "donchian_n_fail_reversion@4h/4h",
                "family": "donchian_n_fail_reversion",
                "name": "donchian_n_fail_reversion 4h/4h BOTH",
                "clock": "4h/4h",
                "side": "BOTH",
                "rank": 64,
                "coded": True,
                "free_params": 2,
                "disposition": "new_family",
                "justification": (
                    "Garwe STAMP LOCK + Brian Inbox YES for coding only. "
                    "Option B exploratory: SCORE/RETIRE. Do not set "
                    "approved=true. Live stays off. Walk-forward is not "
                    "started from this coding PR. 0 book cells. Protect "
                    "12+56. Soft-watch Job 119 failed_range_break_reversion "
                    "EXPLICIT: 119 = prior CLOSE outside rolling range then "
                    "later reclaim within max_bars; this = SAME-bar wick "
                    "pierce of causal prior-N Donchian + close back inside "
                    "+ body confirms; NO delayed reclaim; NO max_bars_since_"
                    "break. Soft-watch Job 167 horizontal_liquidity_reject "
                    "EXPLICIT: 167 = min_touches≥3 flat band; this has NO "
                    "touch count / multi-touch flat band. FORBID multi-touch "
                    "flat band / next-thru-mid / extreme_frac / CLV. Free: "
                    "n [10, 20], pierce_tol_atr [0.0, 0.10]. Locked: ATR20 "
                    "atr.shift(1) causal; Donchian exclude-t via "
                    "shift(1).rolling(n); fill t+1. No VP/session VWAP."
                ),
                "param_change": {"clock": "4h/4h"},
                "needs_feed": False,
            }
        )

    if not any(s.name == "donchian_n_fail_reversion" for s in CANDIDATE_SPECS):
        CANDIDATE_SPECS.append(
            SleeveSpec(
                name="donchian_n_fail_reversion",
                template="novel",
                clock="4h/4h",
                side="BOTH",
                needs_feed=False,
                needs_new_indicator=False,
                novel_reason=(
                    "Same-bar wick pierce of causal prior-N Donchian then "
                    "close inside + body confirm. Option B. No approved=true. "
                    "FORBID multi-touch flat band / next-thru-mid / "
                    "extreme_frac / CLV (neq Jobs 119 + 167). Soft-watch "
                    "Jobs 119 + 167. Free n and pierce_tol_atr only."
                ),
                summary=(
                    "After a 4h wick pierces causal Donchian N beyond "
                    "pierce_tol*ATR20 and closes back inside with body "
                    "confirm, fade at t+1."
                ),
                justification=(
                    "Option B SCORE/RETIRE only. Do not set approved=true. "
                    "Live stays off. Soft-watch Jobs 119 + 167 EXPLICIT."
                ),
            )
        )

    _orig_kit = validate.strategy_kit

    def strategy_kit(name, side):  # type: ignore[no-untyped-def]
        if name == "donchian_n_fail_reversion":
            from core.strategy.donchian_n_fail_reversion import (
                DonchianNFailReversionParams,
                DonchianNFailReversionStrategy,
            )

            def factory(params):  # type: ignore[no-untyped-def]
                return DonchianNFailReversionStrategy(params)

            base = DonchianNFailReversionParams(side=side)
            space = {
                "n": [10, 20],
                "pierce_tol_atr": [0.0, 0.10],
                "take_profit_pct": [0.03, 0.05],
                "stop_loss_pct": [0.02, 0.03],
            }
            return factory, base, space
        return _orig_kit(name, side)

    validate.strategy_kit = strategy_kit  # type: ignore[assignment]


apply()
