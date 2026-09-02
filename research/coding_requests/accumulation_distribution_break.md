# Proposal: `accumulation_distribution_break`

Break the A/D line channel.

ADL uses close location in the bar; OBV uses only close direction.

## Coding brief (implement this after Inbox approve)

- Clock: `4h/4h`
- Side: `BOTH`
- Why this is novel: Needs Accumulation/Distribution Line: cumulative CLV*volume, then a break of its N-bar high. Not OBV and not VPT percent-change volume.

## What to write

1. `core/strategy/accumulation_distribution_break.py` — `Strategy` subclass, `name = "accumulation_distribution_break"`.
2. Signals may use bars `<= t` only; the engine fills at `t+1` open.
3. Tests: schema, no lookahead (truncation + future shock), at least one entry.
4. Do not copy a rejected family and rename it.
5. After `list_strategies()` contains this name, call `firm.cursor_coding.mark_done("accumulation_distribution_break")`.
