"""Score stored sentiment readings against subsequent prices."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from core.data.ohlcv import BybitOHLCV
from firm import memory


def _price_at(candles, when: datetime) -> float | None:
    if candles.empty:
        return None
    idx = candles.index.searchsorted(when)
    if idx >= len(candles):
        return float(candles["close"].iloc[-1])
    return float(candles["close"].iloc[max(0, idx)])


def main() -> int:
    pending = memory.unscored_sentiment(older_than=timedelta(hours=24))
    if not pending:
        print("No sentiment readings old enough to score.")
        return 0
    scored = 0
    with BybitOHLCV() as source:
        for row in pending:
            recorded = row["recorded_at"]
            if isinstance(recorded, str):
                recorded = datetime.fromisoformat(recorded)
            if recorded.tzinfo is None:
                recorded = recorded.replace(tzinfo=timezone.utc)
            entry = float(row["price_at_reading"])
            if entry <= 0:
                continue
            later = source.fetch(
                row["symbol"], "1h", recorded, recorded + timedelta(hours=26)
            )
            if later.empty:
                continue
            r4 = _price_at(later, recorded + timedelta(hours=4))
            r24 = _price_at(later, recorded + timedelta(hours=24))
            memory.set_sentiment_forward_returns(
                row["id"],
                (r4 / entry - 1.0) if r4 else None,
                (r24 / entry - 1.0) if r24 else None,
            )
            scored += 1
    print(f"Scored {scored} of {len(pending)} sentiment readings.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
