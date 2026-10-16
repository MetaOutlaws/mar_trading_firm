"""Collector clean-tree guard for the SGP1 overlay, the #135 blobs, and #138.

The contract: those paths pass only when both the index and the worktree are
the pinned blob at that path's pinned mode, a different byte fails, and any
other dirty or staged path fails even when the overlay itself is exact.
``saved_path_parity`` is derived from the checked-in parity run.
"""

from __future__ import annotations

import csv
import json
import subprocess
from pathlib import Path

import pytest

from scripts import f111_repair_clean_tree as guard

ROOT = Path(__file__).resolve().parents[1]
COLLECTOR = ROOT / "scripts" / "collect_f111_execution_repair_audit.sh"
DEPLOY = ROOT / "scripts" / "deploy_f111_execution_repair.sh"

# Abbreviations printed in the 2026-10-16 FINDINGS note. The guard stores the
# one full blob id each abbreviation names.
FINDINGS_BLOB_PREFIXES = {
    "api/app.py": "c9b9f03f",
    # desk_status and index.html were replaced by the later SGP1 overlay.
    "api/dashboard_cache.py": "77f83d56",
    "api/desk_status.py": "dbe90dba",
    "api/static/index.html": "c12e3e53",
    "api/status_app.py": "ad4de7a2",
    "api/status_auth.py": "28a9ccd9",
    "api/status_snapshot.py": "9fe475f6",
    "config/settings.py": "9c02305f",
    "scripts/run_status_page.py": "b2f130fd",
    "scripts/status_cert_fingerprint.sh": "94c8b412",
    "scripts/ufw_status_443.sh": "f9ef5d0f",
}

# Small stand-ins. The production pins are the real overlay blobs, asserted below.
OVERLAY = {
    "api/app.py": b"overlay app\n",
    "api/desk_status.py": b"overlay desk\n",
    "api/static/index.html": b"overlay html\n",
    "api/status_app.py": b"overlay status app\n",
    "api/status_auth.py": b"overlay status auth\n",
    "api/status_snapshot.py": b"overlay status snapshot\n",
    "config/settings.py": b"overlay settings\n",
    "scripts/run_status_page.py": b"overlay run status\n",
    "scripts/status_cert_fingerprint.sh": b"overlay cert\n",
    "scripts/ufw_status_443.sh": b"overlay ufw\n",
}


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)


def _init(tmp_path: Path) -> Path:
    """A committed base whose overlay paths are not the allowed bytes."""
    repo = tmp_path / "app"
    repo.mkdir()
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "clean-tree@example.com")
    _git(repo, "config", "user.name", "Clean Tree Test")
    (repo / "api").mkdir()
    (repo / "api" / "static").mkdir()
    (repo / "core" / "execution").mkdir(parents=True)
    (repo / "api" / "app.py").write_bytes(b"base app\n")
    (repo / "api" / "static" / "index.html").write_bytes(b"base html\n")
    (repo / "core" / "execution" / "engine.py").write_bytes(b"engine-base\n")
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", "base")
    return repo


def _blob(data: bytes) -> str:
    proc = subprocess.run(
        ["git", "hash-object", "--stdin"],
        input=data,
        check=True,
        capture_output=True,
    )
    return proc.stdout.decode().strip()


def _pins(contents: dict[str, bytes], mode: str = "100644") -> dict[str, tuple[str, str]]:
    return {path: (mode, _blob(data)) for path, data in contents.items()}


def _stage(repo: Path, path: str, data: bytes, *, mode: str = "100644") -> None:
    file = repo / path
    file.parent.mkdir(parents=True, exist_ok=True)
    file.write_bytes(data)
    # git records 100755 when any execute bit is set, 100644 otherwise.
    file.chmod(0o755 if mode == "100755" else 0o644)
    _git(repo, "add", "--", path)


def _stage_overlay(
    repo: Path, contents: dict[str, bytes] | None = None
) -> dict[str, tuple[str, str]]:
    contents = OVERLAY if contents is None else contents
    for path, data in contents.items():
        _stage(repo, path, data)
    return _pins(contents)


def _run(repo: Path, capsys: pytest.CaptureFixture[str]) -> tuple[int, str]:
    code = guard.main(["f111_repair_clean_tree.py", str(repo)])
    return code, capsys.readouterr().err


def test_allowed_exact_match(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """A clean tree passes, and so does the overlay when every blob matches."""
    assert guard.ALLOWED_OVERLAY == {
        "api/app.py": ("100644", "c9b9f03f8f4759e809ec17324daee52baffae4fa"),
        "api/dashboard_cache.py": ("100644", "77f83d566ab03c176dea46904db361d5e074cadb"),
        "api/desk_status.py": ("100644", "dbe90dba9aca406bd9a5d16cd8b20cba0e428809"),
        "api/observer_status.py": ("100644", "a3813379faa22c2449d288aa2953f6318d095ba2"),
        "api/static/index.html": ("100644", "c12e3e53fddc7b130a5f9986fb9f11a369667600"),
        "api/status_app.py": ("100644", "ad4de7a26776f2a14dd384057ef85c47fd936ef7"),
        "api/status_auth.py": ("100644", "28a9ccd99a3705dcbe370430e1e72215e6f1b51d"),
        "api/status_snapshot.py": ("100644", "9fe475f649a0f049f6406ddece144b7481f66b4c"),
        "api/why_no_trade.py": ("100644", "1ee0e13f313adca20c43018a6ec804ccde23c207"),
        "config/settings.py": ("100644", "9c02305f6e855960410daa9761abc4a849c97a1a"),
        "core/execution/engine.py": ("100644", "fd6a6b8e4238312502e830d41ef7ae29f382a0d4"),
        "core/execution/f111_paper.py": ("100644", "ab390d3f2b98d6977574d2a40f265e7a2154a8fe"),
        "core/execution/paper.py": ("100644", "c73ead0f9dc5a2373f17da76cb2b1c9d11804381"),
        "core/execution/paper_bar_eval.py": (
            "100644",
            "5374ab24628ef9e330dbf4b6f433461cc1f299e5",
        ),
        "core/execution/paper_cash.py": ("100644", "fde5e49bc1e72261ce258a182aee2e7913fb8f52"),
        "core/execution/paper_settle.py": ("100644", "830b3c5b9e408c726bd6f2c9714347cf61b8d3b3"),
        "core/strategy/spec_sleeve.py": (
            "100644",
            "0b9496b0152d32df23313f220129985dd71a104b",
        ),
        "firm/integrity.py": ("100644", "fa4ee9e9e2b33f752d4a964cd5d333f78383c0dd"),
        "firm/memory.py": ("100644", "c5885e60bf784a9f98832a5c825a0af211692ba2"),
        "firm/orchestrator.py": (
            "100644",
            "1ced376e5718b670453d37859c4790651a00231d",
        ),
        "firm/read_cache.py": ("100644", "a878bcfe633347928b02c071b5ba2a69eae75fbf"),
        "firm/research_catalog.py": (
            "100644",
            "fceddead19de1f6f2cfb25e3427eedd98099c88d",
        ),
        "firm/scan_inbox.py": (
            "100644",
            "8fe9688f6c7001d6dcddfa75b942cde105284a1b",
        ),
        "scripts/run_status_page.py": ("100644", "b2f130fd36fda79a3d23d987c56ad3484f7e7767"),
        "scripts/status_cert_fingerprint.sh": (
            "100755",
            "94c8b4126490d57ef728d258567dd294e098f0f4",
        ),
        "scripts/ufw_status_443.sh": ("100755", "f9ef5d0f510b19421d88f6f249d1c8fb37f92824"),
        "tests/test_dashboard_ux.py": (
            "100644",
            "477cf0dad1f9a9397454fa9248e9519986820459",
        ),
        "tests/test_f111_execution_repair.py": (
            "100644",
            "162c2620ea20ae7c24e09b08a96e46cbb5fcf913",
        ),
        "tests/test_scan_fill_counts.py": (
            "100644",
            "f0520d2ea966389b521b5cd962a0cdd150696d53",
        ),
        "tests/test_scan_inbox.py": (
            "100644",
            "8e61d1b20b853076111341536d7d1d9936251331",
        ),
        "tests/test_why_no_trade.py": (
            "100644",
            "1e76aaa07bc5f59b7347d494e4e4753b3eb9c410",
        ),
    }
    assert set(FINDINGS_BLOB_PREFIXES) < set(guard.ALLOWED_OVERLAY)
    prefixes = {
        **FINDINGS_BLOB_PREFIXES,
        "api/observer_status.py": "a3813379",
        "api/why_no_trade.py": "1ee0e13f",
        "core/strategy/spec_sleeve.py": "0b9496b0",
        "firm/integrity.py": "fa4ee9e9",
        "firm/memory.py": "c5885e60",
        "firm/orchestrator.py": "1ced376e",
        "firm/read_cache.py": "a878bcfe",
        "firm/research_catalog.py": "fceddead",
        "firm/scan_inbox.py": "8fe9688f",
        "core/execution/engine.py": "fd6a6b8e",
        "core/execution/f111_paper.py": "ab390d3f",
        "core/execution/paper.py": "c73ead0f",
        "core/execution/paper_bar_eval.py": "5374ab24",
        "core/execution/paper_cash.py": "fde5e49b",
        "core/execution/paper_settle.py": "830b3c5b",
        "tests/test_dashboard_ux.py": "477cf0da",
        "tests/test_f111_execution_repair.py": "162c2620",
        "tests/test_scan_fill_counts.py": "f0520d2e",
        "tests/test_scan_inbox.py": "8e61d1b2",
        "tests/test_why_no_trade.py": "1e76aaa0",
    }
    assert set(prefixes) == set(guard.ALLOWED_OVERLAY)
    for path, prefix in prefixes.items():
        mode, blob = guard.ALLOWED_OVERLAY[path]
        executable = path in {
            "scripts/status_cert_fingerprint.sh",
            "scripts/ufw_status_443.sh",
        }
        assert mode == ("100755" if executable else "100644")
        assert blob.startswith(prefix) and len(blob) == 40
        # When this clone has the object, the pin must be that blob and no other.
        found = subprocess.run(
            ["git", "-C", str(ROOT), "rev-parse", f"--disambiguate={prefix}"],
            capture_output=True,
            text=True,
        )
        if found.returncode == 0 and found.stdout.strip():
            assert found.stdout.split() == [blob]
    # The #135 pins are the blobs in 3424c265, which SGP1 overlays on b00c4f73.
    repair = "3424c2650930ddc493bc0faca3be0016e7568823"
    for path in (
        "core/execution/engine.py",
        "core/execution/f111_paper.py",
        "core/execution/paper.py",
        "core/execution/paper_bar_eval.py",
        "core/execution/paper_cash.py",
        "core/execution/paper_settle.py",
        "tests/test_f111_execution_repair.py",
        "tests/test_scan_fill_counts.py",
    ):
        listed = subprocess.run(
            ["git", "-C", str(ROOT), "ls-tree", repair, "--", path],
            capture_output=True,
            text=True,
        )
        assert listed.returncode == 0 and listed.stdout.strip()
        meta, name = listed.stdout.strip().split("\t", 1)
        mode, _kind, blob = meta.split()
        assert name == path
        assert guard.ALLOWED_OVERLAY[path] == (mode, blob)
    # firm/scan_inbox.py is still the 5dff9454 blob. The inbox test at that
    # commit was 3cc0e6e4; the allowlist now carries the once-a-minute prune.
    scan_commit = "5dff9454a5dce55e861aeea86eec84779e809ba3"
    listed = subprocess.run(
        ["git", "-C", str(ROOT), "ls-tree", scan_commit, "--", "firm/scan_inbox.py"],
        capture_output=True,
        text=True,
    )
    assert listed.returncode == 0 and listed.stdout.strip()
    meta, name = listed.stdout.strip().split("\t", 1)
    mode, _kind, blob = meta.split()
    assert name == "firm/scan_inbox.py"
    assert (mode, blob) == ("100644", "8fe9688f6c7001d6dcddfa75b942cde105284a1b")
    assert guard.ALLOWED_OVERLAY["firm/scan_inbox.py"] == (mode, blob)
    old_inbox_test = subprocess.run(
        ["git", "-C", str(ROOT), "ls-tree", scan_commit, "--", "tests/test_scan_inbox.py"],
        capture_output=True,
        text=True,
    )
    assert old_inbox_test.returncode == 0 and old_inbox_test.stdout.strip()
    old_blob = old_inbox_test.stdout.split()[2]
    assert old_blob == "3cc0e6e47d4f967be2182843a91595d12d454894"
    assert guard.ALLOWED_OVERLAY["tests/test_scan_inbox.py"][1] != old_blob
    # Later dashboard pins are ids. They stay pinned when the blob is absent,
    # and they are not the older ee994abe or FINDINGS objects.
    assert guard.ALLOWED_OVERLAY["api/observer_status.py"][1] != (
        "28713d3bc4a18806b6dfbbe1675c9108afb5594e"
    )
    collector = COLLECTOR.read_text(encoding="utf-8")
    assert "f111_repair_clean_tree.py" in collector
    assert 'test -f "$helper"' in collector
    # The old pathspec check did not pin blob ids.
    assert "diff --quiet HEAD -- core config scripts api" not in collector

    repo = _init(tmp_path)
    code, err = _run(repo, capsys)
    assert code == 0 and err == ""

    pins = _stage_overlay(repo)
    monkeypatch.setattr(guard, "ALLOWED_OVERLAY", pins)
    code, err = _run(repo, capsys)
    assert code == 0 and err == ""
    assert guard.clean_tree_violations(repo) == []


def test_mismatched_content_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """An allowed path fails when the staged or on-disk bytes differ."""
    repo = _init(tmp_path)
    contents = dict(OVERLAY)
    contents["api/static/index.html"] = b"overlay html tampered\n"
    pins = _pins(OVERLAY)
    _stage_overlay(repo, contents)
    monkeypatch.setattr(guard, "ALLOWED_OVERLAY", pins)

    code, err = _run(repo, capsys)
    assert code == 1
    assert err == "clean-tree guard: dirty path(s): api/static/index.html\n"

    # The stale #119 blotter test is not one of the ten paths.
    _stage(repo, "api/static/index.html", OVERLAY["api/static/index.html"])
    _stage(repo, "tests/test_blotter_strategy.py", b"not an overlay path\n")
    code, err = _run(repo, capsys)
    assert code == 1
    assert "tests/test_blotter_strategy.py" in err
    assert "api/app.py" not in err

    # Staged blob is exact, then the worktree is edited without another add.
    _git(repo, "rm", "-q", "-f", "--", "tests/test_blotter_strategy.py")
    (repo / "api" / "app.py").write_bytes(b"worktree drifted\n")
    code, err = _run(repo, capsys)
    assert code == 1
    assert err == "clean-tree guard: dirty path(s): api/app.py\n"


def test_other_file_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """An exact overlay does not excuse any other staged or unstaged tracked file."""
    repo = _init(tmp_path)
    pins = _stage_overlay(repo)
    monkeypatch.setattr(guard, "ALLOWED_OVERLAY", pins)

    # Staged-only edit: worktree matches HEAD, so ``git diff HEAD`` is silent.
    engine = repo / "core" / "execution" / "engine.py"
    engine.write_bytes(b"engine-staged\n")
    _git(repo, "add", "--", "core/execution/engine.py")
    engine.write_bytes(b"engine-base\n")
    code, err = _run(repo, capsys)
    assert code == 1
    assert err == "clean-tree guard: dirty path(s): core/execution/engine.py\n"

    # Drop the staged engine edit from both the index and the worktree.
    _git(repo, "checkout", "HEAD", "--", "core/execution/engine.py")
    note = repo / "docs" / "unrelated.md"
    note.parent.mkdir()
    note.write_bytes(b"outside the old pathspec\n")
    _git(repo, "add", "--", "docs/unrelated.md")
    code, err = _run(repo, capsys)
    assert code == 1
    assert "docs/unrelated.md" in err
    assert "api/app.py" not in err


def test_executable_script_requires_100755(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """The pinned shell script passes at 100755 and fails at 100644."""
    repo = _init(tmp_path)
    path = "scripts/ufw_status_443.sh"
    data = OVERLAY[path]
    monkeypatch.setattr(guard, "ALLOWED_OVERLAY", {path: ("100755", _blob(data))})

    _stage(repo, path, data, mode="100755")
    code, err = _run(repo, capsys)
    assert code == 0 and err == ""

    _stage(repo, path, data, mode="100644")
    code, err = _run(repo, capsys)
    assert code == 1
    assert err == "clean-tree guard: dirty path(s): scripts/ufw_status_443.sh\n"

    # The index can be 100755 while the worktree is not. That still fails.
    _stage(repo, path, data, mode="100755")
    (repo / path).chmod(0o644)
    code, err = _run(repo, capsys)
    assert code == 1
    assert err == "clean-tree guard: dirty path(s): scripts/ufw_status_443.sh\n"


def test_regular_file_requires_100644(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """A 100644 pin passes only as a non-executable file and fails at 100755."""
    repo = _init(tmp_path)
    path = "api/app.py"
    data = OVERLAY[path]
    monkeypatch.setattr(guard, "ALLOWED_OVERLAY", {path: ("100644", _blob(data))})

    _stage(repo, path, data, mode="100644")
    code, err = _run(repo, capsys)
    assert code == 0 and err == ""

    _stage(repo, path, data, mode="100755")
    code, err = _run(repo, capsys)
    assert code == 1
    assert err == "clean-tree guard: dirty path(s): api/app.py\n"

    # Executable worktree bytes with a 100644 index still fail.
    _stage(repo, path, data, mode="100644")
    (repo / path).chmod(0o755)
    code, err = _run(repo, capsys)
    assert code == 1
    assert err == "clean-tree guard: dirty path(s): api/app.py\n"


def test_scan_inbox_overlay_pin_fails_closed(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The SGP1 scan_inbox overlay passes only as the pinned 100644 blob.

    Server HEAD stays ``b00c4f73``. This path is allowed only when both the
    index and the worktree are blob ``8fe9688f`` at mode 100644. Different
    bytes, or the same bytes with the executable mode, fail closed.
    """
    path = "firm/scan_inbox.py"
    mode, sha = guard.ALLOWED_OVERLAY[path]
    assert (mode, sha) == ("100644", "8fe9688f6c7001d6dcddfa75b942cde105284a1b")
    blob = subprocess.run(
        ["git", "-C", str(ROOT), "cat-file", "blob", sha],
        capture_output=True,
    )
    assert blob.returncode == 0 and blob.stdout

    repo = _init(tmp_path)
    _stage(repo, path, blob.stdout, mode="100644")
    code, err = _run(repo, capsys)
    assert code == 0 and err == ""

    # Different bytes on the allowed path are still dirty.
    _stage(repo, path, blob.stdout + b"\n", mode="100644")
    code, err = _run(repo, capsys)
    assert code == 1
    assert err == "clean-tree guard: dirty path(s): firm/scan_inbox.py\n"

    # The pin is 100644. An executable copy of the same bytes fails.
    _stage(repo, path, blob.stdout, mode="100755")
    code, err = _run(repo, capsys)
    assert code == 1
    assert err == "clean-tree guard: dirty path(s): firm/scan_inbox.py\n"

    # A 100644 index with an executable worktree still fails.
    _stage(repo, path, blob.stdout, mode="100644")
    (repo / path).chmod(0o755)
    code, err = _run(repo, capsys)
    assert code == 1
    assert err == "clean-tree guard: dirty path(s): firm/scan_inbox.py\n"


def _parity_tree(dest: Path, *, deployed: str, remote: bool, flip_runtime: bool) -> None:
    """Copy the real parity artifacts and optionally break one admitted row."""
    src = ROOT / "docs" / "grok-execution-handoff-20261015"
    dst = dest / "docs" / "grok-execution-handoff-20261015"
    dst.mkdir(parents=True)
    with (src / "saved_path_checks.csv").open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
        fieldnames = list(rows[0])
    if flip_runtime:
        for row in rows:
            if row["admitted"] == "True":
                row["runtime_match"] = "False"
                break
    with (dst / "saved_path_checks.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    validation = json.loads((src / "repair_validation.json").read_text(encoding="utf-8"))
    validation["deployed_saved_path_parity"] = deployed
    validation["remote_execution_performed"] = remote
    (dst / "repair_validation.json").write_text(json.dumps(validation), encoding="utf-8")


def test_saved_path_parity_is_computed(tmp_path: Path) -> None:
    """The label follows the parity artifacts. The recorded run stays UNVERIFIED."""
    assert guard.saved_path_parity(ROOT) == "UNVERIFIED"
    assert guard.saved_path_parity(tmp_path) == "UNVERIFIED"

    # Same rows, but a summary that claims the deployed scope was actually run.
    passed = tmp_path / "passed"
    _parity_tree(passed, deployed="PASS", remote=True, flip_runtime=False)
    assert guard.saved_path_parity(passed) == "PASS"

    failed = tmp_path / "failed"
    _parity_tree(failed, deployed="PASS", remote=True, flip_runtime=True)
    assert guard.saved_path_parity(failed) == "FAIL"

    collector = COLLECTOR.read_text(encoding="utf-8")
    assert "'saved_path_parity':'UNVERIFIED'" not in collector
    assert "F111_SAVED_PATH_PARITY" in collector
    assert "module.saved_path_parity(" in collector


def _deploy_preflight(repo: Path, script: Path = DEPLOY) -> subprocess.CompletedProcess[str]:
    """Source the deploy script and run only its clean-tree preflight."""
    return subprocess.run(
        [
            "bash",
            "-c",
            'set -euo pipefail; source "$1"; f111_deploy_clean_preflight "$2"',
            "bash",
            str(script),
            str(repo),
        ],
        capture_output=True,
        text=True,
    )


def test_deploy_preflight_allows_exact_overlay(tmp_path: Path) -> None:
    """The installer preflight calls the same helper and accepts the real overlay blobs."""
    script = DEPLOY.read_text(encoding="utf-8")
    assert "f111_deploy_clean_preflight /data/app" in script
    assert 'test -f "$helper"' in script
    assert 'python3 "$helper" "$repo"' in script
    assert "868f1c9a7a34c240dd81fb0c4b2f25b02455d4a4" in script
    head_check = script.index('test "$(git -C /data/app rev-parse HEAD)" = "$base_sha"')
    preflight = script.index("f111_deploy_clean_preflight /data/app")
    assert head_check < preflight
    assert "diff --quiet HEAD -- core config scripts api research tests" not in script

    repo = _init(tmp_path)
    clean = _deploy_preflight(repo)
    assert clean.returncode == 0, clean.stderr

    for path, (mode, sha) in guard.ALLOWED_OVERLAY.items():
        blob = subprocess.run(
            ["git", "-C", str(ROOT), "cat-file", "blob", sha],
            capture_output=True,
        )
        if blob.returncode != 0:
            # Id-only SGP1 pins. Absence is allowed; a present object is staged.
            if path in {
                "firm/memory.py",
                "api/dashboard_cache.py",
                "api/desk_status.py",
                "api/observer_status.py",
                "api/static/index.html",
                "api/why_no_trade.py",
                "tests/test_dashboard_ux.py",
                "tests/test_why_no_trade.py",
            }:
                continue
            pytest.skip("overlay blobs are not in this clone")
        _stage(repo, path, blob.stdout, mode=mode)
    allowed = _deploy_preflight(repo)
    assert allowed.returncode == 0, allowed.stderr


def test_deploy_preflight_mismatched_content_fails(tmp_path: Path) -> None:
    """Different bytes on an allowed path still stop the installer."""
    repo = _init(tmp_path)
    _stage(repo, "api/app.py", b"not the blotter app\n")
    result = _deploy_preflight(repo)
    assert result.returncode == 1
    assert "api/app.py" in result.stderr
    assert "api/static/index.html" not in result.stderr


def test_deploy_preflight_other_file_fails(tmp_path: Path) -> None:
    """A path outside the ten-file overlay still fails, including staged-only edits."""
    repo = _init(tmp_path)
    engine = repo / "core" / "execution" / "engine.py"
    engine.write_bytes(b"engine-staged\n")
    _git(repo, "add", "--", "core/execution/engine.py")
    engine.write_bytes(b"engine-base\n")
    result = _deploy_preflight(repo)
    assert result.returncode == 1
    assert "core/execution/engine.py" in result.stderr

    _git(repo, "checkout", "HEAD", "--", "core/execution/engine.py")
    note = repo / "docs" / "unrelated.md"
    note.parent.mkdir()
    note.write_bytes(b"outside the old deploy pathspec\n")
    _git(repo, "add", "--", "docs/unrelated.md")
    result = _deploy_preflight(repo)
    assert result.returncode == 1
    assert "docs/unrelated.md" in result.stderr


def test_deploy_preflight_missing_helper_fails_closed(tmp_path: Path) -> None:
    """Extracting the deploy script without the helper must not skip the check."""
    isolated = tmp_path / "scripts"
    isolated.mkdir()
    script = isolated / "deploy_f111_execution_repair.sh"
    script.write_text(DEPLOY.read_text(encoding="utf-8"), encoding="utf-8")
    repo = _init(tmp_path)
    result = _deploy_preflight(repo, script)
    assert result.returncode != 0
