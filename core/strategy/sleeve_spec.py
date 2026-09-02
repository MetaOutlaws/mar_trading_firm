"""JSON sleeve specs: the only way a new family is auto-coded.

A spec names an allowed template and frozen knobs. Sleeve Engineer materializes
it into `config/sleeves/{name}.json`; `SpecSleeveStrategy` executes it. Novel
math, a new indicator, or a missing feed is not a spec — that is a Cursor
coding request.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

TEMPLATES = ("channel_break", "pullback_trend", "fade_stretch")
CHANNELS = ("atr", "donchian", "bollinger")
TRENDS = ("ema", "macd", "adx")
STRETCHES = ("rsi", "bollinger", "atr")


class SleeveSpec(BaseModel):
    """One testable family. Names are registry ids; do not rename after a walk-forward."""

    name: str = Field(min_length=3, max_length=48)
    template: Literal["channel_break", "pullback_trend", "fade_stretch", "novel"]
    clock: str = "4h/4h"
    side: str = "BOTH"
    summary: str = ""
    justification: str = ""
    needs_feed: bool = False
    needs_new_indicator: bool = False
    novel_reason: str = ""
    channel: str = "atr"
    trend: str = "ema"
    stretch: str = "rsi"
    squeeze: bool = False
    volume_filter: bool = False
    defaults: dict[str, float] = Field(default_factory=dict)

    @field_validator("name")
    @classmethod
    def _name_is_slug(cls, value: str) -> str:
        slug = value.strip().lower()
        if not slug.replace("_", "").isalnum() or "__" in slug:
            raise ValueError(f"sleeve name must be a snake_case slug, got {value!r}")
        return slug

    @field_validator("clock")
    @classmethod
    def _clock_ok(cls, value: str) -> str:
        parts = [p.strip() for p in value.split("/") if p.strip()]
        if len(parts) != 2 or any(p not in {"15m", "1h", "4h"} for p in parts):
            raise ValueError(f"clock must be like 4h/4h, got {value!r}")
        if parts[0] == "15m" or parts[1] == "15m":
            raise ValueError("15m is excluded from auto-coded specs after costs")
        return f"{parts[0]}/{parts[1]}"

    @field_validator("side")
    @classmethod
    def _side_ok(cls, value: str) -> str:
        side = value.upper()
        if side not in {"BOTH", "LONG", "SHORT"}:
            raise ValueError(f"side must be BOTH/LONG/SHORT, got {value!r}")
        return side

    @property
    def auto_code(self) -> bool:
        """True when Sleeve Engineer can register this without writing Python."""
        return (
            self.template in TEMPLATES
            and not self.needs_feed
            and not self.needs_new_indicator
        )

    def search_space(self) -> dict[str, list[Any]]:
        """Walk-forward grid. Kept small so fold CV stays meaningful."""
        space: dict[str, list[Any]] = {
            "take_profit_pct": [0.03, 0.05],
            "stop_loss_pct": [0.02, 0.03],
        }
        if self.template == "channel_break":
            if self.channel == "atr":
                space["atr_k"] = [2.0, 2.5]
            elif self.channel == "donchian":
                space["lookback"] = [20, 55]
            else:
                space["band_k"] = [2.0, 2.5]
            space["min_adx"] = [0.0, 20.0]
        elif self.template == "fade_stretch":
            space["max_adx"] = [0.0, 20.0]
            if self.stretch == "rsi":
                space["rsi_os"] = [25.0, 30.0]
            else:
                space["band_k"] = [2.0, 2.5]
        else:
            space["min_adx"] = [0.0, 20.0]
            space["ema_fast"] = [12, 20]
        return space

    def hypothesis_row(self, *, coded: bool) -> dict[str, Any]:
        hid = f"{self.name}@{self.clock}"
        if self.side != "BOTH":
            hid = f"{hid}@{self.side}"
        return {
            "id": hid,
            "family": self.name,
            "name": f"{self.name} {self.clock} {self.side}",
            "clock": self.clock,
            "side": self.side,
            "coded": coded,
            "free_params": min(4, len(self.search_space())),
            "disposition": "retest_under_different_regime",
            "justification": self.justification or self.summary,
            "needs_feed": self.needs_feed,
            "spec_name": self.name,
        }
