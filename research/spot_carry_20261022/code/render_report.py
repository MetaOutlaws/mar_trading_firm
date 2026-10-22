#!/usr/bin/env python3
"""Build the self-contained HTML report from the simulator summaries."""
from __future__ import annotations

import json
import sys
from pathlib import Path


def load(path: Path) -> dict:
    return json.loads(path.read_text())


def pct(value, digits=2):
    if value is None:
        return "—"
    if value == float("inf"):
        return "inf"
    return f"{100 * value:.2f}%"


def num(value, digits=2):
    if value is None:
        return "—"
    if value == float("inf"):
        return "inf"
    return f"{value:,.{digits}f}"


def row(summary, slice_name, year=None):
    if year is None:
        return [
            slice_name,
            pct(summary["net_return"]),
            num(summary["ending_equity"]),
            pct(summary["max_drawdown"]),
            str(summary["trades"]),
            pct(summary["win_rate"], 1) if summary["win_rate"] is not None else "—",
            num(summary["profit_factor"], 2),
            num(summary["expectancy"], 2),
            num(summary["components"]["fees"] + summary["components"]["slippage"] + summary["components"]["penalty"], 0),
            num(summary["mean_R"], 3),
        ]
    block = summary["years"][year]
    return [
        slice_name,
        pct(block["net_return"]),
        num(block["end_equity"]),
        pct(block["max_drawdown"]),
        str(block["trades"]),
        pct(block["win_rate"], 1) if block["win_rate"] is not None else "—",
        num(block["profit_factor"], 2),
        num(block["expectancy"], 2),
        "—",
        "—",
    ]


def table(headers, rows):
    head = "".join(f"<th>{h}</th>" for h in headers)
    body = []
    for item in rows:
        body.append("<tr>" + "".join(f"<td>{c}</td>" for c in item) + "</tr>")
    return "<table><thead><tr>" + head + "</tr></thead><tbody>" + "".join(body) + "</tbody></table>"


def main():
    src = Path(sys.argv[1])
    dest = Path(sys.argv[2])
    models = ("baseline", "moderate", "desk_031", "severe")
    books = ("BTC", "ETH", "combined")
    headers = ["Slice", "Net return", "Ending equity", "Max DD", "Trades", "Win rate", "Profit factor", "Expectancy USDT", "Fees+slip+penalty", "Mean R"]
    sections = []
    for model in models:
        rows = []
        for book in books:
            summary = load(src / f"{model}_{book}_d1_selective.json")
            name = {"BTC": "BTC", "ETH": "ETH", "combined": "Combined"}[book]
            for year in ("2022", "2023", "2024", "2025"):
                rows.append(row(summary, f"{name} {year}", year))
            rows.append(row(summary, f"{name} overall"))
        sections.append(f"<h2>{model}</h2>" + table(headers, rows))
    # Controls at baseline, the first primary view. Other models are in the files.
    control_rows = []
    for model in models:
        for kind, title in (("selective", "Selective"), ("passive", "Passive")):
            summary = load(src / f"{model}_combined_d1_{kind}.json")
            control_rows.append([
                f"{model} {title}",
                pct(summary["net_return"]),
                num(summary["ending_equity"]),
                pct(summary["max_drawdown"]),
                str(summary["trades"]),
                num(summary["components"]["funding"], 0),
                num(summary["components"]["fees"], 0),
                num(summary["profit_factor"], 2),
            ])
        if model != "severe":
            delayed = load(src / f"{model}_combined_d5_selective.json")
            control_rows.append([
                f"{model} selective, 5-minute delay",
                pct(delayed["net_return"]),
                num(delayed["ending_equity"]),
                pct(delayed["max_drawdown"]),
                str(delayed["trades"]),
                num(delayed["components"]["funding"], 0),
                num(delayed["components"]["fees"], 0),
                num(delayed["profit_factor"], 2),
            ])
    gates = []
    for model in ("baseline", "moderate", "desk_031"):
        summary = load(src / f"{model}_combined_d1_selective.json")
        gate = summary["gates"]
        failed = [name for name, ok in gate["checks"].items() if not ok]
        gates.append(
            f"<li><strong>{model}</strong>: {'PASS' if gate['pass'] else 'FAIL'}. "
            f"Failed checks: {', '.join(failed) if failed else 'none'}. "
            f"Null shifts beaten: {gate['beats_null_count']} of 200. "
            f"Bootstrap mean-trade interval: {num(summary.get('bootstrap_low'), 2)} to {num(summary.get('bootstrap_high'), 2)} USDT.</li>"
        )
    base = load(src / "baseline_combined_d1_selective.json")
    parts = base["components"]
    bridge = table(
        ["Component", "USDT"],
        [
            ["Spot price, quoted", num(parts["spot_price"], 0)],
            ["Perpetual price, quoted", num(parts["perp_price"], 0)],
            ["Funding", num(parts["funding"], 0)],
            ["Fees", num(-parts["fees"], 0)],
            ["Slippage", num(-parts["slippage"], 0)],
            ["Liquidation penalty", num(-parts["penalty"], 0)],
            ["Net", num(base["ending_equity"] - 20000, 0)],
        ],
    )
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Same-token funding carry — results</title>
<style>
  body {{ font-family: Georgia, serif; max-width: 980px; margin: 2rem auto; padding: 0 1.25rem; color: #1c1917; line-height: 1.45; }}
  table {{ border-collapse: collapse; width: 100%; margin: 0.75rem 0 1.25rem; font-variant-numeric: tabular-nums; font-size: 0.92rem; }}
  th, td {{ border-bottom: 1px solid #d6d3d1; text-align: left; padding: 0.3rem 0.4rem; vertical-align: top; }}
  .verdict {{ background: #fef3c7; border: 1px solid #d6d3d1; padding: 0.75rem 1rem; }}
  code {{ font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; font-size: 0.86rem; }}
</style>
</head>
<body>
<h1>The selective carry does not pass</h1>
<p class="verdict">Long spot against a short perpetual, traded only when recent funding cleared a predeclared cost hurdle, lost money on BTC, on ETH and on the combined 20,000 USDT account. It lost at baseline, at moderate and at the desk’s per-leg 0.31% round trip. A study pass required all three. The result is a fail. The passive version, which just holds the hedge, made a small gain. This is reused 2022–2025 history, not evidence of future profit, and it does not authorise live trading.</p>

<h2>Costs</h2>
<p>The handoff’s primary views are baseline and moderate. Severe is a stress. The assignment also asked for the desk’s 0.31% round trip. That charge is applied to <strong>each</strong> leg, so the pair pays 62 bp, not 31 bp once. Charging it once would have been a lighter test. Slippage in baseline (1 bp), moderate (5 bp) and severe (10 bp) is a label. The archive has no order-book spread.</p>
<p>Mean R uses the frozen 1% of equity at entry as the denominator. Losses per trade are much smaller than that 1% ceiling, so the R figures are close to zero even when the account is down about 10%. A funding-rate sum is not used as R.</p>

<h2>Pass checks</h2>
<ul>
{''.join(gates)}
</ul>
<p>Severe is not required to pass. It also lost. No gate was loosened after the numbers.</p>

<h2>Selective results</h2>
<p>Year rows use marked equity at each 31 December close. Trade counts in a year are pairs closed that year. “Fees+slip+penalty” is the full-sample total and is left blank on year rows. Mean R is the full-sample mean and is left blank on year rows.</p>
{''.join(sections)}

<h2>Combined account against the passive hold</h2>
{table(["Book", "Net return", "Ending equity", "Max DD", "Trades", "Funding USDT", "Fees USDT", "Profit factor"], control_rows)}
<p>Cash, with no orders, ends at 20,000 USDT. The passive hold is the same hedge without the funding hurdle and without the basis exit. It re-enters after a liquidation. On the baseline combined book that happened once, in 2024, and the two positions still open at the last minute were flattened then. Profit factor is infinite because none of those three closes lost money. Beating all 200 shifted-funding paths is not a pass: those paths lost as well, and the account itself finished below 20,000.</p>

<h2>Where the baseline combined loss came from</h2>
{bridge}
<p>Funding collected about {num(parts['funding'], 0)} USDT. Fees were about {num(parts['fees'], 0)} USDT because the hurdle opened and closed the hedge hundreds of times. Quoted spot and perpetual price P&amp;L did not cover that gap. Rebalancing costs are zero because the rule does not rebalance. Financing on idle cash is zero.</p>
<p>Blocked-entry counts are minutes, not separate trades. On the baseline combined book the economic entry was already true while a position was open for {base['blocked']['in_position']:,} minutes. Cash, size, drawdown, gross cap and the risk ceiling blocked nothing. Missing-data exits: {base['exit_reasons'].get('missing_data', 0)}. Sample-end closes: {base['exit_reasons'].get('end_of_sample', 0)}. Liquidations: {base['exit_reasons'].get('liquidation', 0)}.</p>

<h2>Approved strategies</h2>
<p>Hourly compression, Connors and BL8 were not re-run. Their simulator is a different perp-only engine, and this archive was not passed through it. Their published research R is not placed next to these account returns. Comparison with the approved book is unavailable. Against the passive carry that this study did run, on the same dates, capital and costs, the selective rule is worse.</p>

<h2>Protocol order</h2>
<p>The rule was committed in <code>7b99d20</code> and clarified in <code>9a4f440</code> before any of these numbers were computed. Later commits only implement that rule and record this report.</p>
</body>
</html>
"""
    dest.write_text(html)
    print(dest, "bytes", dest.stat().st_size)


if __name__ == "__main__":
    main()
