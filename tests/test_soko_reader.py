"""The paper engine reads Soko from core, and the dict does not change.

``soko_display`` used to live in ``api.desk_status``. The scan summary
imported it, and importing that module is what put the desk (and, on a
panel read, ``api.dashboard_cache``) on the paper path. The function now
lives in ``core.soko.reader``. The desk re-exports it.

The expected dicts are the desk output for these files: label, as-of, age,
source, and path. ``_read_soko`` returns the first three of those fields.
"""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
NOW = datetime(2026, 10, 10, 15, 30, tzinfo=timezone.utc)


def _display(path: Path, **fields: object) -> dict[str, object]:
    row: dict[str, object] = {
        "label": None,
        "as_of": None,
        "age_seconds": None,
        "source": "file",
        "path": str(path),
    }
    row.update(fields)
    return row


def _reader(display: dict[str, object]) -> dict[str, object]:
    """The three fields ``firm.scan_inbox._read_soko`` keeps."""
    return {
        "label": display["label"],
        "as_of": display["as_of"],
        "age_seconds": display["age_seconds"],
    }


def test_engine_scan_inbox_import_skips_the_desk(tmp_path: Path) -> None:
    """Importing the engine and reading Soko leaves the desk modules unloaded.

    The check runs in a fresh interpreter. This process already imported
    the desk while collecting the rest of the suite, so ``sys.modules``
    here cannot show the paper path.
    """
    present = tmp_path / "last_soko_trend.json"
    present.write_text(
        json.dumps({"trend": "chop", "as_of": "2026-10-10T12:30:00+00:00"}),
        encoding="utf-8",
    )
    missing = tmp_path / "absent.json"
    code = r"""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import core.data.soko_trend as soko_trend
import core.execution.engine  # noqa: F401
import firm.scan_inbox

now = datetime(2026, 10, 10, 15, 30, tzinfo=timezone.utc)
soko_trend.LAST_SOKO_TREND_PATH = Path(sys.argv[1])
missing_row = firm.scan_inbox._read_soko(now)
soko_trend.LAST_SOKO_TREND_PATH = Path(sys.argv[2])
present_row = firm.scan_inbox._read_soko(now)
banned = ("api.desk_status", "api.dashboard_cache")
print(json.dumps({
    "loaded": [name for name in banned if name in sys.modules],
    "api": sorted(name for name in sys.modules if name == "api" or name.startswith("api.")),
    "missing": missing_row,
    "present": present_row,
}))
"""
    completed = subprocess.run(
        [sys.executable, "-c", code, str(missing), str(present)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
        timeout=120,
    )
    assert completed.returncode == 0, completed.stdout + "\n" + completed.stderr
    payload = json.loads(completed.stdout)
    assert payload["loaded"] == []
    assert payload["api"] == []
    assert payload["missing"] == {"label": None, "as_of": None, "age_seconds": None}
    assert payload["present"] == {
        "label": "chop",
        "as_of": "2026-10-10T12:30:00+00:00",
        "age_seconds": 10800,
    }
    scan_inbox = (ROOT / "firm" / "scan_inbox.py").read_text(encoding="utf-8")
    assert "from core.soko.reader import soko_display" in scan_inbox
    assert "api.desk_status" not in scan_inbox
    assert "api.dashboard_cache" not in scan_inbox


def test_soko_display_and_reader_match_on_the_same_files(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Desk re-export, core reader, and the scan summary agree on each file."""
    from api.desk_status import soko_display as desk_display
    from core.soko.reader import soko_display
    from firm.scan_inbox import _read_soko

    assert desk_display is soko_display

    cases: list[tuple[Path, dict[str, object]]] = []

    missing = tmp_path / "missing.json"
    cases.append((missing, _display(missing, source="missing")))

    broken = tmp_path / "broken.json"
    broken.write_text("{not json", encoding="utf-8")
    cases.append((broken, _display(broken, source="unreadable")))

    empty = tmp_path / "empty.json"
    empty.write_text("", encoding="utf-8")
    cases.append((empty, _display(empty, source="unreadable")))

    null_file = tmp_path / "null.json"
    null_file.write_text("null", encoding="utf-8")
    cases.append((null_file, _display(null_file, source="unreadable")))

    listed = tmp_path / "list.json"
    listed.write_text("[1]", encoding="utf-8")
    cases.append((listed, _display(listed, source="unreadable")))

    folder = tmp_path / "directory.json"
    folder.mkdir()
    cases.append((folder, _display(folder, source="unreadable")))

    chop = tmp_path / "chop-string.json"
    chop.write_text(json.dumps("chop"), encoding="utf-8")
    cases.append((chop, _display(chop, label="chop")))

    alias = tmp_path / "alias-string.json"
    alias.write_text(json.dumps("  bullish  "), encoding="utf-8")
    cases.append((alias, _display(alias, label="bull")))

    raw = tmp_path / "raw-string.json"
    raw.write_text(json.dumps("neutral"), encoding="utf-8")
    cases.append((raw, _display(raw, label="neutral")))

    blank = tmp_path / "blank-string.json"
    blank.write_text(json.dumps("   "), encoding="utf-8")
    cases.append((blank, _display(blank, label=None)))

    aged = tmp_path / "aged.json"
    aged.write_text(
        json.dumps({"trend": "chop", "as_of": "2026-10-10T12:30:00+00:00"}),
        encoding="utf-8",
    )
    cases.append(
        (
            aged,
            _display(
                aged,
                label="chop",
                as_of="2026-10-10T12:30:00+00:00",
                age_seconds=10800,
            ),
        )
    )

    zulu = tmp_path / "zulu.json"
    zulu.write_text(
        json.dumps({"regime": "bear", "as_of": "2026-10-10T15:00:00Z"}),
        encoding="utf-8",
    )
    cases.append(
        (
            zulu,
            _display(
                zulu,
                label="bear",
                as_of="2026-10-10T15:00:00+00:00",
                age_seconds=1800,
            ),
        )
    )

    naive = tmp_path / "naive.json"
    naive.write_text(
        json.dumps({"soko_trend": "up", "as_of": "2026-10-10T12:30:00"}),
        encoding="utf-8",
    )
    cases.append(
        (
            naive,
            _display(
                naive,
                label="bull",
                as_of="2026-10-10T12:30:00+00:00",
                age_seconds=10800,
            ),
        )
    )

    bad_clock = tmp_path / "bad-clock.json"
    bad_clock.write_text(
        json.dumps({"label": "bull", "as_of": "yesterday"}),
        encoding="utf-8",
    )
    cases.append((bad_clock, _display(bad_clock, label="bull", as_of="yesterday")))

    numeric_clock = tmp_path / "numeric-clock.json"
    numeric_clock.write_text(
        json.dumps({"trend": "chop", "as_of": 12345}),
        encoding="utf-8",
    )
    cases.append((numeric_clock, _display(numeric_clock, label="chop")))

    fallthrough = tmp_path / "fallthrough.json"
    fallthrough.write_text(
        json.dumps({"trend": "  ", "btc_trend": "bearish"}),
        encoding="utf-8",
    )
    cases.append((fallthrough, _display(fallthrough, label="bear")))

    kept = tmp_path / "kept-raw.json"
    kept.write_text(
        json.dumps({"trend": "neutral", "btc_trend": "bull"}),
        encoding="utf-8",
    )
    cases.append((kept, _display(kept, label="neutral")))

    pairs = tmp_path / "pairs.json"
    pairs.write_text(
        json.dumps(
            {
                "pairs": [
                    {"symbol": "ethusdt", "trend": "bull"},
                    {"symbol": "btcusdt", "trend": "chop"},
                ],
                "as_of": "2026-10-10T15:00:00+00:00",
            }
        ),
        encoding="utf-8",
    )
    cases.append(
        (
            pairs,
            _display(
                pairs,
                label="chop",
                as_of="2026-10-10T15:00:00+00:00",
                age_seconds=1800,
            ),
        )
    )

    pair_fallback = tmp_path / "pair-fallback.json"
    pair_fallback.write_text(
        json.dumps(
            {
                "pairs": [
                    {"symbol": "BTCUSDT", "trend": "sideways-ish"},
                    {"symbol": "BTC", "trend": "down"},
                ]
            }
        ),
        encoding="utf-8",
    )
    cases.append((pair_fallback, _display(pair_fallback, label="bear")))

    for path, expected in cases:
        assert soko_display(path, now=NOW) == expected
        assert desk_display(path, now=NOW) == expected
        monkeypatch.setattr("core.data.soko_trend.LAST_SOKO_TREND_PATH", path)
        assert _read_soko(NOW) == _reader(expected)
