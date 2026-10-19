"""#145 desk caches on the #150 snapshot, without changing the paper imports.

``firm/scan_inbox.py`` imports ``soko_display`` (the paper worker reaches that
module from ``firm/memory.py`` pending proposals). ``scripts/verify_l01_paper.py``
imports ``deployed_git_sha``. Those names, signatures, and ``soko_display``
outputs stay put. The F111 and JSONL caches sit on the desk read, not on them.
"""

from __future__ import annotations

import ast
import inspect
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Outside api/ and tests. A new import here has to be locked in this file.
_SKIP_ROOTS = {"api", "tests", ".git", ".venv", "htmlcov", "__pycache__"}

NOW = datetime(2026, 10, 10, 15, 30, tzinfo=timezone.utc)

# Locked from the pre-cache function. age is 15:30 minus 12:30.
_SOKO_BODY = {
    "label": "chop",
    "as_of": "2026-10-10T12:30:00+00:00",
    "age_seconds": 10800,
    "source": "file",
}


def _external_desk_imports() -> dict[str, set[str]]:
    """Names imported from ``api.desk_status`` by code that is not the desk."""
    found: dict[str, set[str]] = {}
    for path in ROOT.rglob("*.py"):
        rel = path.relative_to(ROOT)
        if not rel.parts or rel.parts[0] in _SKIP_ROOTS:
            continue
        if any(part.startswith(".") or part == "__pycache__" for part in rel.parts):
            continue
        # utf-8-sig drops a leading BOM. config/pipeline.py is saved with one.
        tree = ast.parse(path.read_text(encoding="utf-8-sig"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name == "api.desk_status" or alias.name.startswith("api.desk_status."):
                        found.setdefault(alias.name, set()).add(str(rel))
            if isinstance(node, ast.ImportFrom) and node.module == "api.desk_status":
                for alias in node.names:
                    found.setdefault(alias.name, set()).add(str(rel))
    return found


def _param_shape(fn: object) -> list[tuple[str, str, bool, object]]:
    signature = inspect.signature(fn)
    return [
        (
            name,
            param.kind.name,
            param.default is inspect.Parameter.empty,
            param.annotation,
        )
        for name, param in signature.parameters.items()
    ]


def test_paper_imports_keep_signatures_and_soko_output(tmp_path, monkeypatch) -> None:
    """Call sites outside api/ see the same functions and the same Soko dict."""
    found = _external_desk_imports()
    assert found == {
        "soko_display": {"firm/scan_inbox.py"},
        "deployed_git_sha": {"scripts/verify_l01_paper.py"},
    }

    scan_inbox = (ROOT / "firm" / "scan_inbox.py").read_text(encoding="utf-8")
    assert "from api.desk_status import soko_display" in scan_inbox
    assert "shown = soko_display(now=now)" in scan_inbox
    verifier = (ROOT / "scripts" / "verify_l01_paper.py").read_text(encoding="utf-8")
    assert "from api.desk_status import deployed_git_sha" in verifier
    assert "deployed_git_sha()" in verifier

    # Same statements the call sites execute.
    namespace: dict[str, object] = {}
    exec("from api.desk_status import soko_display, deployed_git_sha", namespace)
    soko_display = namespace["soko_display"]
    deployed_git_sha = namespace["deployed_git_sha"]

    assert _param_shape(soko_display) == [
        ("path", "POSITIONAL_OR_KEYWORD", False, "Path | None"),
        ("now", "KEYWORD_ONLY", False, "datetime | None"),
    ]
    assert inspect.signature(soko_display).return_annotation == "dict[str, Any]"
    assert _param_shape(deployed_git_sha) == [
        ("root", "POSITIONAL_OR_KEYWORD", False, "Path | None"),
    ]
    assert inspect.signature(deployed_git_sha).return_annotation == "dict[str, Any]"

    fixture = tmp_path / "last_soko_trend.json"
    fixture.write_text(
        json.dumps({"trend": "chop", "as_of": "2026-10-10T12:30:00+00:00"}),
        encoding="utf-8",
    )
    expected = {**_SOKO_BODY, "path": str(fixture)}
    monkeypatch.setattr("core.data.soko_trend.LAST_SOKO_TREND_PATH", fixture)

    before = soko_display(now=NOW)
    assert before == expected

    missing = tmp_path / "absent.json"
    assert soko_display(missing, now=NOW) == {
        "label": None,
        "as_of": None,
        "age_seconds": None,
        "source": "missing",
        "path": str(missing),
    }

    for key in ("GIT_SHA", "APP_GIT_SHA", "DEPLOYED_GIT_SHA", "GIT_COMMIT"):
        monkeypatch.delenv(key, raising=False)
    assert deployed_git_sha(tmp_path) == {
        "sha": None,
        "short": None,
        "source": "unavailable",
    }

    # The caches run between the two reads. Soko's dict does not move.
    from api.dashboard_cache import panel_cache
    from api.desk_status import _read_jsonl, clear_jsonl_cache, f111_status

    telemetry = tmp_path / "f111_telemetry.jsonl"
    state = tmp_path / "state.json"
    telemetry.write_text('{"symbol": "BTCUSDT"}\n', encoding="utf-8")
    state.write_text("{}", encoding="utf-8")
    clear_jsonl_cache()
    panel_cache.clear()
    assert _read_jsonl(telemetry) == [{"symbol": "BTCUSDT"}]
    f111_status(now=NOW, telemetry_path=telemetry, state_path=state)

    after = soko_display(now=NOW)
    assert after == before == expected
    clear_jsonl_cache()
    panel_cache.clear()


def test_jsonl_cache_is_present_and_used(tmp_path, monkeypatch) -> None:
    """The same mtime and size returns the parsed rows without reading again."""
    import api.desk_status as desk

    desk.clear_jsonl_cache()
    path = tmp_path / "telemetry.jsonl"
    path.write_text('{"a": 1}\nnot-json\n{"b": 2}\n', encoding="utf-8")
    loads = {"n": 0}
    real_loads = desk.json.loads

    def counting(text: str, *args, **kwargs):
        loads["n"] += 1
        return real_loads(text, *args, **kwargs)

    monkeypatch.setattr(desk.json, "loads", counting)
    first = desk._read_jsonl(path)
    parsed = loads["n"]
    assert first == [{"a": 1}, {"b": 2}]
    assert parsed >= 2
    assert any(rows is first for rows in desk._JSONL_CACHE.values())
    second = desk._read_jsonl(path)
    assert second is first
    assert loads["n"] == parsed
    path.write_text('{"a": 3}\n', encoding="utf-8")
    third = desk._read_jsonl(path)
    assert third == [{"a": 3}]
    assert third is not first
    assert loads["n"] > parsed
    desk.clear_jsonl_cache()


def test_f111_and_dashboard_cache_are_present_and_used(tmp_path, monkeypatch) -> None:
    """A second F111 read with the same scan does not rebuild the panel."""
    import api.dashboard_cache as cache
    import api.desk_status as desk

    assert isinstance(cache.panel_cache, cache.PanelCache)
    assert cache.DEFAULT_TTL_SECONDS == 30.0
    assert "panel_cache.fetch" in inspect.getsource(desk.f111_status)
    assert "f111_cache_key" in inspect.getsource(desk.f111_status)
    assert hasattr(desk, "_JSONL_CACHE")

    cache.panel_cache.clear()
    desk.clear_jsonl_cache()
    calls = {"n": 0}
    original = desk._f111_status_uncached

    def wrapped(**kwargs):
        calls["n"] += 1
        return original(**kwargs)

    monkeypatch.setattr(desk, "_f111_status_uncached", wrapped)
    telemetry = tmp_path / "f111_telemetry.jsonl"
    state = tmp_path / "f111_paper_state.json"
    telemetry.write_text("", encoding="utf-8")
    state.write_text('{"pending": [], "protection": {}}', encoding="utf-8")
    now = datetime(2026, 10, 16, 15, 30, tzinfo=timezone.utc)
    first = desk.f111_status(now=now, telemetry_path=telemetry, state_path=state)
    second = desk.f111_status(now=now, telemetry_path=telemetry, state_path=state)
    assert calls["n"] == 1
    assert second["registry"] == first["registry"]
    assert second["computed_at"] == first["computed_at"]
    assert second["age"] == 0
    assert "f111" in cache.panel_cache._slots

    telemetry.write_text('{"run_id": "next-scan"}\n', encoding="utf-8")
    third = desk.f111_status(now=now, telemetry_path=telemetry, state_path=state)
    assert calls["n"] == 2
    assert third["telemetry_present"] is True
    cache.panel_cache.clear()
    desk.clear_jsonl_cache()


def test_observers_cache_is_used_off_the_request_path(tmp_path, monkeypatch) -> None:
    """The snapshot builder hits the observers cache. GET only copies memory."""
    import api.observer_status as obs
    from api.app import observers as observers_route
    from api.dashboard_cache import panel_cache
    from api.observer_snapshot import snapshot_store

    source = inspect.getsource(observers_route)
    assert "list_observers" not in source
    assert "snapshot_store.serve()" in source
    assert "observers_cache_key" in inspect.getsource(obs.list_observers)

    panel_cache.clear()
    calls = {"n": 0}
    original = obs._list_observers_uncached

    def wrapped(**kwargs):
        calls["n"] += 1
        return original(**kwargs)

    monkeypatch.setattr(obs, "_list_observers_uncached", wrapped)
    kwargs = {
        "now": datetime(2026, 10, 16, 15, 30, tzinfo=timezone.utc),
        "telemetry_path": tmp_path / "missing.jsonl",
        "state_path": tmp_path / "missing-state.json",
        "status_path": tmp_path / "missing-status.json",
        "db_path": tmp_path / "missing.db",
    }
    first = obs.list_observers(**kwargs)
    second = obs.list_observers(**kwargs)
    assert calls["n"] == 1
    assert [row["id"] for row in second["observers"]] == [row["id"] for row in first["observers"]]
    assert [row["id"] for row in first["observers"]] == ["f111", "bl8"]

    builds = {"n": 0}

    def fake_list(**_kwargs):
        builds["n"] += 1
        return {
            "ok": True,
            "observers": [{"id": "f111"}, {"id": "bl8"}],
            "pulses": [],
        }

    monkeypatch.setattr(obs, "list_observers", fake_list)
    snapshot_store.stop()
    snapshot_store.clear()
    snapshot_store.refresh()
    served = snapshot_store.serve()
    assert builds["n"] == 1
    assert served["status"] == "ready"
    assert [row["id"] for row in served["observers"]] == ["f111", "bl8"]
    snapshot_store.serve()
    assert builds["n"] == 1
    panel_cache.clear()
    snapshot_store.clear()
