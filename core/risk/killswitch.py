"""
Kill switch: a persistent, human-reset-only trading halt.

Two properties matter, and the legacy project had neither:

1. **Persistent.** The tripped state survives a process restart. A halt that
   clears when the bot crashes and restarts is not a halt -- and a crash loop is
   exactly when you least want trading to resume automatically.
2. **Human-reset only.** Nothing in the codebase can untrip it. No agent, no
   scheduled job, no recovery routine. Automatic re-arming would defeat the
   purpose, because whatever condition tripped it has not been investigated.

State lives in a small JSON file so it is trivially inspectable and editable in
an emergency, independent of the database being healthy.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path

from config.settings import PROJECT_ROOT

logger = logging.getLogger(__name__)

DEFAULT_STATE_PATH = PROJECT_ROOT / "data" / "killswitch.json"


class TripReason(str, Enum):
    """Why trading was halted."""

    MAX_DRAWDOWN = "max_drawdown"
    DAILY_LOSS_LIMIT = "daily_loss_limit"
    CONSECUTIVE_LOSSES = "consecutive_losses"
    BROKER_ERROR = "broker_error"
    DATA_STALE = "data_stale"
    RECONCILIATION_MISMATCH = "reconciliation_mismatch"
    MANUAL = "manual"
    UNKNOWN = "unknown"


@dataclass
class KillSwitchState:
    """Serialisable kill switch state."""

    tripped: bool = False
    reason: TripReason = TripReason.UNKNOWN
    detail: str = ""
    tripped_at: str | None = None
    tripped_by: str = ""

    @property
    def is_tripped(self) -> bool:
        """Alias for `.tripped`.

        `KillSwitch` exposes `is_tripped`; gather paths sometimes call the same
        name on the state object returned by `read()`. Keep both so a tripped
        check cannot crash an employee run.
        """
        return self.tripped

    def to_dict(self) -> dict[str, object]:
        return {
            "tripped": self.tripped,
            "reason": self.reason.value,
            "detail": self.detail,
            "tripped_at": self.tripped_at,
            "tripped_by": self.tripped_by,
        }

    @classmethod
    def from_dict(cls, payload: dict) -> "KillSwitchState":
        try:
            reason = TripReason(payload.get("reason", TripReason.UNKNOWN.value))
        except ValueError:
            reason = TripReason.UNKNOWN
        return cls(
            tripped=bool(payload.get("tripped", False)),
            reason=reason,
            detail=str(payload.get("detail", "")),
            tripped_at=payload.get("tripped_at"),
            tripped_by=str(payload.get("tripped_by", "")),
        )


class KillSwitch:
    """File-backed trading halt."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = path or DEFAULT_STATE_PATH
        self.path.parent.mkdir(parents=True, exist_ok=True)

    # -- state -------------------------------------------------------------
    def read(self) -> KillSwitchState:
        """Current state. A missing or corrupt file reads as *not* tripped.

        Failing open here is the right call: a corrupt file should not silently
        halt a healthy system, and every actual trip is also recorded as a risk
        event in the database.
        """
        if not self.path.exists():
            return KillSwitchState()
        try:
            return KillSwitchState.from_dict(json.loads(self.path.read_text(encoding="utf-8")))
        except (json.JSONDecodeError, OSError) as exc:
            logger.error("Unreadable kill switch state (%s); treating as not tripped.", exc)
            return KillSwitchState()

    def _write(self, state: KillSwitchState) -> None:
        # Write-then-rename so a crash mid-write cannot leave a truncated file.
        temp = self.path.with_suffix(".tmp")
        temp.write_text(json.dumps(state.to_dict(), indent=2), encoding="utf-8")
        temp.replace(self.path)

    @property
    def is_tripped(self) -> bool:
        return self.read().tripped

    # -- transitions -------------------------------------------------------
    def trip(self, reason: TripReason, detail: str = "", tripped_by: str = "system") -> KillSwitchState:
        """Halt trading. Idempotent: the first trip's cause is preserved.

        Keeping the original reason matters for diagnosis, since a cascade of
        secondary failures usually follows the first one.
        """
        current = self.read()
        if current.tripped:
            logger.warning(
                "Kill switch already tripped (%s); new trigger %s recorded but not overwritten.",
                current.reason.value, reason.value,
            )
            return current

        state = KillSwitchState(
            tripped=True,
            reason=reason,
            detail=detail,
            tripped_at=datetime.now(timezone.utc).isoformat(),
            tripped_by=tripped_by,
        )
        self._write(state)
        logger.critical(
            "KILL SWITCH TRIPPED by %s: %s - %s. Trading halted until manual reset.",
            tripped_by, reason.value, detail,
        )
        return state

    def reset(self, operator: str, acknowledgement: str) -> KillSwitchState:
        """Clear the halt. Requires an explicit acknowledgement string.

        The acknowledgement is friction on purpose: resetting without
        understanding the cause is how a small loss becomes a large one.

        Args:
            operator: Who is resetting, recorded in the log.
            acknowledgement: Must equal "I HAVE INVESTIGATED THE CAUSE".
        """
        required = "I HAVE INVESTIGATED THE CAUSE"
        if acknowledgement != required:
            raise ValueError(f"Reset requires acknowledgement exactly equal to: {required!r}")

        previous = self.read()
        self._write(KillSwitchState())
        logger.warning(
            "Kill switch reset by %s. Previous trip: %s - %s (%s)",
            operator, previous.reason.value, previous.detail, previous.tripped_at,
        )
        return KillSwitchState()
