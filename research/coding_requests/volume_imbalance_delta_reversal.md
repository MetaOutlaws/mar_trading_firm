# Proposal: `volume_imbalance_delta_reversal`

Calculates the ratio of buying volume to selling volume (volume imbalance) at the extreme highs and lows of a rolling 20-period window. When price sweeps a new high or low but the volume imbalance shows extreme exhaustion (buying volume is 

It filters out low-volume retail sweeps that lack institutional backing, allowing high-probability fades at local extremes.

## Coding brief (implement this after Inbox approve)

- Clock: `4h/4h`
- Side: `BOTH`
- Why this is novel: Calculates the ratio of buying volume to selling volume (volume imbalance) at the extreme highs and lows of a rolling 20-period window. When price sweeps a new high or low but the volume imbalance shows extreme exhaustion (buying volume is less than 20% of total volume at the high), it triggers a mean-reversion trade targeting the 20-period EMA.

## What to write

1. `core/strategy/volume_imbalance_delta_reversal.py` — `Strategy` subclass, `name = "volume_imbalance_delta_reversal"`.
2. Signals may use bars `<= t` only; the engine fills at `t+1` open.
3. Tests: schema, no lookahead (truncation + future shock), at least one entry.
4. Do not copy a rejected family and rename it.
5. After `list_strategies()` contains this name, call `firm.cursor_coding.mark_done("volume_imbalance_delta_reversal")`.
