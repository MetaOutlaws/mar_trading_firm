# Next shift (from 2 Sep 2026)

Paper research only. Live stays off. PF 1.15 / CI / beats-random stay hard.

## Idle-when-empty (PR #4)

Empty catalog + empty standby = **IDLE**. Do not refill from `CLOCK_BY_FAMILY`
leftovers, a ledger id reset, or clones.

- Do not auto-advance onto a `family@clock@side` that already finished
  (approved, rejected, or completed grid).
- Near-miss retests only if the operator explicitly queued that frozen grid.
  Do not invent near-misses to keep slots busy.
- One walk-forward copy at a time unless the operator queued more.
- Protect the paper book: a later walk-forward of the same family must not
  overwrite an earlier research-approved or operator paper-veto row.
- Do not stash `config/approved_strategies.json` on pull.

## Dead families

Stay dead. Do not recode:

- `squeeze_momentum_break`
- `volume_force_divergence`
- `session_liquidity_sweep`
- `bar_vwap_inflow_surge`
- `fib_retracement_bounce`
- `measured_move_break` (job 86 honest 0/12, stays dead, do not recode, do not overlay skip_bull/chop on the BTC LONG 2.23 miss)
- skip_bull overlay on `fib_extension_break` (job 85 overwrote winners; do not rerun)

## Quant / coding

Quant keeps 2–3 unapproved drafts. Inbox-approve is the coding gate.

## You still must not

- Change risk parameters, add symbols, or go live without a human (Tier C).
- Loosen PF 1.15 / CI / beats-random.
