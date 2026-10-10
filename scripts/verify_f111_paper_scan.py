"""Evaluate all 192 F111 paper sleeves and print explicit instrument status.

Does not start a worker, place an order, or reset cash. Exit 0 when every
sleeve was evaluated and instruments-info answered. Exit 2 when the scan is
complete but the endpoint was unreachable: those symbols are UNAVAILABLE with
a reason, not silently treated as tradable. Exit 1 when a sleeve is missing.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.execution.f111_paper import fresh_scan  # noqa: E402
from core.strategy.f111_config import assert_not_a_second_worker  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=None, help="Write the JSON report here.")
    args = parser.parse_args(argv)
    assert_not_a_second_worker(False)
    report = fresh_scan()
    text = json.dumps({key: value for key, value in report.items() if key != "rows"}, indent=2)
    print(text)
    if args.output is not None:
        args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    if report["sleeves_evaluated"] != report["sleeves_expected"]:
        return 1
    if any(row.get("feature_values", {}).get("evaluated") is not True for row in report["rows"]):
        return 1
    if report["transport_failures"]:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
