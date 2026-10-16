"""Weekly cross-sectional spread research harness.

Paper only. Live stays off. This package does not register a sleeve, does
not read ``config/approved_strategies.json``, and does not place an order.

The engine (harness) and the metrics (scorer) are separate modules so each
can be hashed on its own. Garwe has to ACK both hashes before a real-tape
metric is read.
"""

from __future__ import annotations

__all__ = ["PACKAGE_DIR"]

from pathlib import Path

PACKAGE_DIR = Path(__file__).resolve().parent
