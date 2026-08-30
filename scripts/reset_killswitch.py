"""Manually reset the kill switch after investigating the cause."""

from __future__ import annotations

import argparse
import sys

from core.risk.killswitch import KillSwitch


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--operator", required=True)
    parser.add_argument(
        "--acknowledgement",
        required=True,
        help="Must be exactly: I HAVE INVESTIGATED THE CAUSE",
    )
    args = parser.parse_args()
    try:
        KillSwitch().reset(args.operator, args.acknowledgement)
    except ValueError as exc:
        print(exc, file=sys.stderr)
        return 1
    print("Kill switch cleared.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
