"""Old name for the consolidation backfill.

The command now lives in ``scripts/backfill_consolidated_trades.py``.
This module remains so an earlier invocation still runs the same main.
Pass ``--input`` and ``--variant A`` or ``--variant B``.
"""

from __future__ import annotations

from scripts.backfill_consolidated_trades import main

if __name__ == "__main__":
    raise SystemExit(main())
