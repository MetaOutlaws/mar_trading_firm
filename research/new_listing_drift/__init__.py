"""Event-level listing-drift spread research harness.

Paper only. Live stays off. This package does not register a sleeve
and does not place an order.

The engine (harness) and the metrics (scorer) are separate modules so each
can be hashed on its own. Garwe has not countersigned, so those hashes are
provisional: no real-tape metric is read until that ACK exists.
"""

from __future__ import annotations

__all__ = ["PACKAGE_DIR"]

from pathlib import Path

PACKAGE_DIR = Path(__file__).resolve().parent
