"""Paper sleeve for research case F111.

The inherited hourly compression, BTC-direction, Connors-RSI and low-efficiency
rules stay in the parent classes. This class only adds the F111 gates
(compression strictly above 0.50, original extension <= 1 prior ATR, and
prior ATR / close >= 0.01). It does not replace the low-efficiency cap.

The trading engine fills a ``latest_signal`` on the hourly close. F111 must
not do that: the entry is a later minute retest. ``latest_signal`` therefore
refuses live mode and returns no immediate order. The minute lifecycle lives
in ``core.execution.f111_paper``.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from core.strategy.base import SignalSide
from core.strategy.f111_config import STRATEGY_ID, load_f111_config
from core.strategy.f111_semantics import gate_decision, gate_mask, signed_extension
from core.strategy.hourly_compression_btc_connors_loweff_v1 import (
    HourlyCompressionBtcConnorsLoweffV1Strategy,
)


def load_universe() -> tuple[str, ...]:
    """The 96 supplied symbols, in spec order. No aliases are applied."""
    config, _digest = load_f111_config()
    return tuple(config["universe"])


class MarF111R12ExtensionLatefloorV1Strategy(HourlyCompressionBtcConnorsLoweffV1Strategy):
    """All 96 symbols, both directions. Paper scan is not an immediate fill."""

    name = STRATEGY_ID

    def __init__(self, params=None):
        super().__init__(params)
        # The parent approval list is BTC/ETH/SOL. F111 keeps that signal math
        # and widens the symbol set to the supplied universe. A symbol that is
        # not on this list is not scanned under another ticker.
        self.symbols = frozenset(load_universe())

    def generate_signals(self, candles: pd.DataFrame) -> pd.DataFrame:
        """Parent signal, then the three F111 gates. A failed gate blanks the row.

        The parent already applied the conditional low-efficiency cap. Rows the
        parent flattened stay flat even when the extension would pass F111.
        """
        out = super().generate_signals(candles)
        required = ("compression", "extension_atr", "prior_atr")
        missing = [name for name in required if name not in out.columns]
        if missing:
            raise ValueError(f"F111 parent frame is missing {missing}")
        out["extension_atr"] = _extension_where_inputs_exist(
            out, candles, int(self.params.side.sign)
        )
        passed = gate_mask(
            out["compression"].to_numpy(dtype=float),
            out["extension_atr"].to_numpy(dtype=float),
            out["prior_atr"].to_numpy(dtype=float),
            candles["close"].to_numpy(dtype=float),
        )
        blocked = (out["signal"] != 0) & ~passed
        blank = self.empty_signals(candles)
        for col in ("signal", "side", "score", "reason"):
            out.loc[blocked, col] = blank.loc[blocked, col]
        out["f111_gate_pass"] = passed
        reasons: list[str] = []
        for compression, extension, prior_atr, close, signal in zip(
            out["compression"],
            out["extension_atr"],
            out["prior_atr"],
            candles["close"],
            out["signal"],
            strict=True,
        ):
            _ok, reason = gate_decision(
                compression=float(compression) if pd.notna(compression) else float("nan"),
                extension_atr=float(extension) if pd.notna(extension) else float("nan"),
                prior_atr=float(prior_atr) if pd.notna(prior_atr) else float("nan"),
                close=float(close) if pd.notna(close) else float("nan"),
            )
            if int(signal) != 0:
                reasons.append("")
            elif reason:
                reasons.append(reason)
            else:
                # Parent low-efficiency / compression / Connors / BTC rule already
                # flattened this bar. That is not an F111 gate failure.
                reasons.append("base_signal_blocked")
        out["f111_rejection_reason"] = reasons
        keep = out["signal"] != 0
        out.loc[keep, "reason"] = (
            "F111: inherited hourly compression + CRSI + BTC24 + low-efficiency cap; "
            "compression > 0.50; extension <= 1 prior ATR; prior ATR / close >= 0.01"
        )
        return out

    def latest_signal(self, symbol: str, candles: pd.DataFrame):
        """No hourly-close order. Live and testnet are refused."""
        from core.strategy.f111_config import assert_f111_paper_only

        self._last_gate_diagnostics = None
        assert_f111_paper_only()
        if symbol not in self.symbols:
            raise ValueError(f"{symbol} is not one of the 96 F111 symbols")
        # The engine would place a market order from a non-None return. The
        # retest has not happened yet, so there is nothing to send.
        return None


def _extension_where_inputs_exist(
    out: pd.DataFrame, candles: pd.DataFrame, side: int
) -> pd.Series:
    """Keep a finite extension. Fill a null from close, boundary, and prior ATR.

    The parent formula already covers both sides. A branch that leaves the
    column null after an earlier rejection still has those inputs on the row.
    """
    extension = pd.to_numeric(out["extension_atr"], errors="coerce")
    if "entry_boundary" not in out.columns:
        return extension
    boundary = pd.to_numeric(out["entry_boundary"], errors="coerce").reindex(extension.index)
    prior = pd.to_numeric(out["prior_atr"], errors="coerce").reindex(extension.index)
    close = pd.to_numeric(candles["close"], errors="coerce").reindex(extension.index)
    recomputed = pd.Series(
        [
            signed_extension(side, float(c), float(b), float(a))
            for c, b, a in zip(close.to_numpy(), boundary.to_numpy(), prior.to_numpy(), strict=True)
        ],
        index=extension.index,
        dtype=float,
    )
    return extension.where(np.isfinite(extension), recomputed)


def rejection_for_parent_row(row: pd.Series, close: float) -> str:
    """Explain one flattened row. Used by telemetry when the parent already blocked it."""
    if int(row.get("signal", 0) or 0) != 0:
        return ""
    ok, reason = gate_decision(
        compression=float(row["compression"]) if pd.notna(row.get("compression")) else float("nan"),
        extension_atr=float(row["extension_atr"]) if pd.notna(row.get("extension_atr")) else float("nan"),
        prior_atr=float(row["prior_atr"]) if pd.notna(row.get("prior_atr")) else float("nan"),
        close=close,
    )
    if reason:
        return reason
    if not ok:
        return "base_signal_blocked"
    return "base_signal_blocked"


# Imported for side-aware construction by the paper runtime. Re-exported so
# callers do not need a second import to name a direction.
__all__ = [
    "STRATEGY_ID",
    "MarF111R12ExtensionLatefloorV1Strategy",
    "SignalSide",
    "load_universe",
]
