# Board remediation calendar — CEO LOCK — 1 week

Prepared for Brian Zhanda (CEO) to send the Board.  
**Clock:** Asia/Dubai (GST, UTC+4).  
**Base HEAD for this lock:** `787f7af` on `feat/employee-floor-and-openai` (includes F01 #60 and F02 #59).

This document is the Board calendar. It **replaces** any 3-week implication in:

- the 12 Sep review (`docs/MAR_Trading_Firm_Review_2026-09-12.md` §9 — eight sequential packages with no Board date);
- the 17 Sep response memo’s previous wording that the P0 sequence was “acceptance gates, **not a calendar**.”

Linked from [`docs/BOARD_REVIEW_RESPONSE_DRAFT_2026-09-17.md`](BOARD_REVIEW_RESPONSE_DRAFT_2026-09-17.md).

---

## HARD deadline

**Complete the P0 DONE list below by Thursday 2026-09-24, end of GST.**

This is a **one-week Board lock**, not a three-week program. Missing a mid-week day does not slide the Thursday 24 Sep date. F06–F09 remain open P0 defects on the books; they do **not** extend this deadline and are not in this week’s DONE.

Live stays **off**. Paper history is **preserved**. Gates are **not** loosened.

---

## Definition of DONE (P0 only) — all required by 24 Sep GST

| Item | Status required by 24 Sep | Notes |
|---|---|---|
| **F01** OOS window | **MERGED** (#60, `787f7af`) | Code on HEAD. Deploy with F02 on Thu 17. Revalidation must key to `RESEARCH_VERSION = wf-f01-oos-window-v1`. |
| **F02** paper cash | **MERGED** (#59, `b3a606a`) | Code on HEAD. Deploy with F01 on Thu 17. Do **not** wipe `data/firm.db` to “fix” cash. |
| **F03** fees / funding | **Merge + deploy by Fri 2026-09-18** | Entry fee, exit fee, funding as first-class events; paper/research cost identity. |
| **F05** exit supervision under halt / empty plan | **Landed** | Kill switch and empty scan plan still run `check_stops`; process does not exit solely because the plan is empty. |
| **F04** research/paper execution contract + golden tape | **Landed** | One contract (timing, stops, expiry, fees, funding, conflicts). Identical candles → identical fills/exits/costs/P&L. Timeout exits at `max_holding_bars`. |
| **Revalidation kit** | **Green, or no new approvals** | Keyed to `RESEARCH_VERSION wf-f01-oos-window-v1`. Re-run ATR BTC/ETH 4h SHORT and doji SOL 1h SHORT. Report deltas vs stored `oos_*`. **No new `approved=true` until the kit is green.** Existing three approved rows stay candidates. |
| **§5 promotion gate** | **Fails closed** | Rejected OOS excluded; paper ledger always; missing drawdown fails; tripped kill switch fails; min paper trades + expectancy required. `evaluate_gates()["ready"]` is false on today’s committed data. |
| **History / live** | **Preserved / off** | No DROP/truncate of trades, positions, or equity snapshots. `TRADING_MODE=paper`. No `GO_LIVE_CONFIRMED`. `PIPELINE_AUTO_ADVANCE` stays fail-closed. |

**Not in this week’s DONE (do not delay the above to finish them):** F06, F07, F08, F09 (order / exit / recon state machine); F17 serialize as a separate package; P1 F10–F21.

---

## Day plan (GST)

| Date | GST day | Work |
|---|---|---|
| **Thu 17 Sep** | Day 0 (today) | Open **F03** PR. **Deploy F01 + F02** to the paper box (cash journal + OOS window). Archive `firm.db` + WAL with the deploy; do not erase. |
| **Fri 18 Sep** | Day 1 | **F03 merge + deploy.** Start **F05** (exit supervision under halt / empty plan). |
| **Sat–Sun 19–20 Sep** | Days 2–3 | **F05 land.** Scaffold **F04** execution contract **and** the revalidation kit (`wf-f01-oos-window-v1`). |
| **Mon–Tue 21–22 Sep** | Days 4–5 | **F04 golden tape.** Kit revalidation runs: ATR BTC 4h SHORT, ATR ETH 4h SHORT, doji SOL 1h SHORT. File deltas. Kit not green → **no** `approved=true`. |
| **Wed 23 Sep** | Day 6 | **§5 promotion-gate PR** (fails closed). Evidence-pack draft (deploy SHAs, kit deltas, gate test results, sanitized `.env`). |
| **Thu 24 Sep** | Day 7 — **Board complete** | Verification report against this DONE list. Board pack closed for the week. Live still off. |

P1 **F10–F21** start **after** the week gate, unless there is free parallel capacity that does not steal owners from F03 / F05 / F04 / kit / §5.

---

## Constraints (do not violate to hit the date)

- Docs and repair PRs only as scoped per finding. **Do not** touch strategy sleeve geometry, `config/approved_strategies.json`, live flags, or loosen research/go-live gates to manufacture a green kit.
- **Do not** start walk-forward promotions or expand the paper book until the kit is green.
- Coding-only sleeve registration may continue; it is not approval and is not this week’s DONE.
- Employees stay L1 / advisory.
- First F02 deploy seeds capital at starting equity; historical cash cannot be reconstructed from existing `trades` rows until F03 records entry fees. That is expected. It is not permission to reset the ledger.

---

## Thursday 24 Sep verification report (minimum contents)

1. SHAs deployed vs this lock HEAD (`787f7af` + F03/F05/F04/§5 merges).
2. F01 #60 and F02 #59 **merged and deployed**; F03 merged and deployed by Fri 18 (or exception with Board-visible date — still must be done by Thu 24).
3. F05 and F04 PRs merged, with the verification tests named in the 17 Sep response memo.
4. Kit keyed to `wf-f01-oos-window-v1`; ATR BTC/ETH 4h SHORT and doji SOL 1h SHORT deltas vs stored `oos_*`; statement that **no** new `approved=true` was written unless the kit is green.
5. §5 `evaluate_gates()["ready"]` is false on committed data; missing DD and tripped kill switch fail closed.
6. Proof live is off: sanitized `.env` with `TRADING_MODE=paper`, `PIPELINE_AUTO_ADVANCE=false`, `GO_LIVE_CONFIRMED` empty.
7. Proof history is intact: backup of `data/firm.db` (+ WAL) and `data/paper_cash.json`; no truncate.

*Not a go-live recommendation. Not a 3-week plan.*
