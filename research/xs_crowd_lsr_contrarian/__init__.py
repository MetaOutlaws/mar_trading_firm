"""Research-only harness for xs_crowd_lsr_contrarian v2.

Paper only. Live off. This package does not register a strategy, does not
set ``approved``, and does not import the paper book or the execution
engine. The frozen preregistration and Garwe's countersign are the spec.
"""

from __future__ import annotations

CELL = "xs_crowd_lsr_contrarian"
LIVE = "off"

__all__ = ["CELL", "LIVE"]
