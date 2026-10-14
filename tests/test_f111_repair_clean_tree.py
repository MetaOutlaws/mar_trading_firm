"""Collector clean-tree guard: Marcus exception 1 for the #119 blotter overlay.

The three cases are the contract: the staged files pass only when their git
blobs are the pinned #119 ids, a different byte on those paths fails, and any
other dirty or staged path fails even when the overlay itself is exact.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from scripts import f111_repair_clean_tree as guard

ROOT = Path(__file__).resolve().parents[1]
COLLECTOR = ROOT / "scripts" / "collect_f111_execution_repair_audit.sh"
DEPLOY = ROOT / "scripts" / "deploy_f111_execution_repair.sh"

# Small stand-ins. The production pins are the real 8d35ec7c blobs, asserted below.
OVERLAY = {
    "api/app.py": b"blotter app\n",
    "api/static/index.html": b"blotter html\n",
    "tests/test_blotter_strategy.py": b"blotter test\n",
}


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)


def _init(tmp_path: Path) -> Path:
    """A committed base whose three overlay paths are not the allowed bytes."""
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


def _pins(contents: dict[str, bytes]) -> dict[str, str]:
    return {path: _blob(data) for path, data in contents.items()}


def _stage(repo: Path, path: str, data: bytes) -> None:
    file = repo / path
    file.parent.mkdir(parents=True, exist_ok=True)
    file.write_bytes(data)
    _git(repo, "add", "--", path)


def _stage_overlay(repo: Path, contents: dict[str, bytes] | None = None) -> dict[str, str]:
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
    assert guard.ALLOWED_OVERLAY_BLOBS == {
        "api/app.py": "0b92809901b32009c99c4bbaf0757b56f795d836",
        "api/static/index.html": "c036f22b759ff7fef2d017a014dc2ed73503ed1d",
        "tests/test_blotter_strategy.py": "97cdc4fe10dce3652faa8224716abfd3aa3db45d",
    }
    assert guard.OVERLAY_COMMIT == "8d35ec7c4acaf05958eec79136c3526684517811"
    collector = COLLECTOR.read_text(encoding="utf-8")
    assert "f111_repair_clean_tree.py" in collector
    # The old pathspec check ignored tests/ and would not pin blob ids.
    assert "diff --quiet HEAD -- core config scripts api" not in collector

    repo = _init(tmp_path)
    code, err = _run(repo, capsys)
    assert code == 0 and err == ""

    pins = _stage_overlay(repo)
    monkeypatch.setattr(guard, "ALLOWED_OVERLAY_BLOBS", pins)
    code, err = _run(repo, capsys)
    assert code == 0 and err == ""
    assert guard.clean_tree_violations(repo) == []


def test_mismatched_content_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """The three allowed paths fail when the staged or on-disk bytes differ."""
    repo = _init(tmp_path)
    contents = dict(OVERLAY)
    contents["api/static/index.html"] = b"blotter html tampered\n"
    pins = _pins(OVERLAY)
    _stage_overlay(repo, contents)
    monkeypatch.setattr(guard, "ALLOWED_OVERLAY_BLOBS", pins)

    code, err = _run(repo, capsys)
    assert code == 1
    assert err == "clean-tree guard: dirty path(s): api/static/index.html\n"

    # tests/ was outside the old pathspec. A wrong blob there must still fail.
    _stage(repo, "api/static/index.html", OVERLAY["api/static/index.html"])
    _stage(repo, "tests/test_blotter_strategy.py", b"not the blotter test\n")
    code, err = _run(repo, capsys)
    assert code == 1
    assert "tests/test_blotter_strategy.py" in err
    assert "api/app.py" not in err

    # Staged blob is exact, then the worktree is edited without another add.
    _stage(repo, "tests/test_blotter_strategy.py", OVERLAY["tests/test_blotter_strategy.py"])
    (repo / "api" / "app.py").write_bytes(b"worktree drifted\n")
    code, err = _run(repo, capsys)
    assert code == 1
    assert "api/app.py" in err


def test_other_file_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """An exact overlay does not excuse any other staged or unstaged tracked file."""
    repo = _init(tmp_path)
    pins = _stage_overlay(repo)
    monkeypatch.setattr(guard, "ALLOWED_OVERLAY_BLOBS", pins)

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
    """The installer preflight calls the same helper and accepts the real #119 blobs."""
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

    for path, sha in guard.ALLOWED_OVERLAY_BLOBS.items():
        blob = subprocess.run(
            ["git", "-C", str(ROOT), "cat-file", "blob", sha],
            capture_output=True,
        )
        if blob.returncode != 0:
            pytest.skip("8d35ec7c blobs are not in this clone")
        _stage(repo, path, blob.stdout)
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
    """A path outside the three-file overlay still fails, including staged-only edits."""
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
