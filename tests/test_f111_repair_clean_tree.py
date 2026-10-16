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
    "api/desk_status.py": "4814d209",
    "api/static/index.html": "1d13fd9d",
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
        "api/desk_status.py": ("100644", "4814d2096e6b06c4d98d86f39c61938cb4d178ad"),
        "api/observer_status.py": ("100644", "152a6df71e67097128a49cc13f35c16f73102f6e"),
        "api/static/index.html": ("100644", "1d13fd9d414bf6872f14a655a39d6c5ddd494406"),
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
        "firm/memory.py": ("100644", "fba54b57a7c07c2540dc2246b83ca16913179bfa"),
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
            "78398fb6d6b35cc2f309780912365f7f918801c9",
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
            "3cc0e6e47d4f967be2182843a91595d12d454894",
        ),
        "tests/test_why_no_trade.py": (
            "100644",
            "1e76aaa07bc5f59b7347d494e4e4753b3eb9c410",
        ),
        ".env.example": ("100644", "9afdf09c808e1a87178c0eebca826698d75f68db"),
        ".gitignore": ("100644", "cef30f2b9a9fa4603eb869871e431662957e4b65"),
        "deploy/caddy/Caddyfile": ("100644", "8814676372bbe8a71b84bdb04c544306046a1e60"),
        "deploy/caddy/entrypoint.sh": (
            "100755",
            "32cbcd8f84796147bd870a04d864330f2c651cbe",
        ),
        "deploy/status/Dockerfile": ("100644", "9493f6fb6313cacff399b496b285fad418729c2c"),
        "deploy/status/docker-compose.sgp1.yml": (
            "100644",
            "b20ec3cbdd68b376d3903a7af024c51f00afbc4f",
        ),
        "docker-compose.status.yml": (
            "100644",
            "a3a2987d5c6943d256721d676b2ff632bcae0cd9",
        ),
        "docs/runbooks/status_page.md": (
            "100644",
            "d6c8de14708addf25a9a8ad3db2283297323124e",
        ),
        "pyproject.toml": ("100644", "92461189518d51ddf24a5f0eba7fc4df96e2e142"),
        "research/coding_inbox/NOW.md": (
            "100644",
            "b02167b0a4426cf53e264375823055992530f47f",
        ),
        "tests/test_blotter_strategy.py": (
            "100644",
            "97cdc4fe10dce3652faa8224716abfd3aa3db45d",
        ),
        "tests/test_dashboard_desk.py": (
            "100644",
            "49e06a20dec148a9738227bc5e80905a9d15f36c",
        ),
        "tests/test_status_page.py": (
            "100644",
            "66625e60d366ac49c957c6cd1df7a6c8ec721c6f",
        ),
    }
    assert set(FINDINGS_BLOB_PREFIXES) < set(guard.ALLOWED_OVERLAY)
    prefixes = {
        **FINDINGS_BLOB_PREFIXES,
        "api/observer_status.py": "152a6df7",
        "api/why_no_trade.py": "1ee0e13f",
        "firm/memory.py": "fba54b57",
        "firm/scan_inbox.py": "8fe9688f",
        "core/execution/engine.py": "fd6a6b8e",
        "core/execution/f111_paper.py": "ab390d3f",
        "core/execution/paper.py": "c73ead0f",
        "core/execution/paper_bar_eval.py": "5374ab24",
        "core/execution/paper_cash.py": "fde5e49b",
        "core/execution/paper_settle.py": "830b3c5b",
        "tests/test_dashboard_ux.py": "78398fb6",
        "tests/test_f111_execution_repair.py": "162c2620",
        "tests/test_scan_fill_counts.py": "f0520d2e",
        "tests/test_scan_inbox.py": "3cc0e6e4",
        "tests/test_why_no_trade.py": "1e76aaa0",
        ".env.example": "9afdf09c",
        ".gitignore": "cef30f2b",
        "deploy/caddy/Caddyfile": "88146763",
        "deploy/caddy/entrypoint.sh": "32cbcd8f",
        "deploy/status/Dockerfile": "9493f6fb",
        "deploy/status/docker-compose.sgp1.yml": "b20ec3cb",
        "docker-compose.status.yml": "a3a2987d",
        "docs/runbooks/status_page.md": "d6c8de14",
        "pyproject.toml": "92461189",
        "research/coding_inbox/NOW.md": "b02167b0",
        "tests/test_blotter_strategy.py": "97cdc4fe",
        "tests/test_dashboard_desk.py": "49e06a20",
        "tests/test_status_page.py": "66625e60",
    }
    assert set(prefixes) == set(guard.ALLOWED_OVERLAY)
    for path, prefix in prefixes.items():
        mode, blob = guard.ALLOWED_OVERLAY[path]
        executable = path in {
            "deploy/caddy/entrypoint.sh",
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
    # Blobs of these paths at 5dff9454, which SGP1 overlays on b00c4f73.
    # tests/test_scan_inbox.py replaces 456b0c8e from that server HEAD.
    scan_commit = "5dff9454a5dce55e861aeea86eec84779e809ba3"
    for path, expected in {
        "firm/scan_inbox.py": ("100644", "8fe9688f6c7001d6dcddfa75b942cde105284a1b"),
        "tests/test_scan_inbox.py": ("100644", "3cc0e6e47d4f967be2182843a91595d12d454894"),
    }.items():
        listed = subprocess.run(
            ["git", "-C", str(ROOT), "ls-tree", scan_commit, "--", path],
            capture_output=True,
            text=True,
        )
        assert listed.returncode == 0 and listed.stdout.strip()
        meta, name = listed.stdout.strip().split("\t", 1)
        mode, _kind, blob = meta.split()
        assert name == path
        assert (mode, blob) == expected
        assert guard.ALLOWED_OVERLAY[path] == (mode, blob)
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


def test_disk_mode_normalizes_and_paths_missing_from_head_pass(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Disk mode 600 is git 100644 and 700 is git 100755.

    The guard compares the executable bit, not the rest of the permission
    bits. A path that HEAD does not contain still passes when both the index
    and the worktree are the pinned blob at that git mode.
    """
    repo = _init(tmp_path)
    regular = "deploy/status/docker-compose.sgp1.yml"
    script = "deploy/caddy/entrypoint.sh"
    regular_bytes = b"services: {}\n"
    script_bytes = b"#!/bin/sh\nexit 0\n"
    monkeypatch.setattr(
        guard,
        "ALLOWED_OVERLAY",
        {
            regular: ("100644", _blob(regular_bytes)),
            script: ("100755", _blob(script_bytes)),
        },
    )

    def place(path: str, data: bytes, disk_mode: int) -> None:
        file = repo / path
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_bytes(data)
        file.chmod(disk_mode)
        _git(repo, "add", "--", path)

    # Neither path is in the base commit. They exist only after git add.
    listed = subprocess.run(
        ["git", "-C", str(repo), "ls-tree", "HEAD", "--", regular, script],
        capture_output=True,
        text=True,
        check=True,
    )
    assert listed.stdout == ""

    place(regular, regular_bytes, 0o600)
    place(script, script_bytes, 0o700)
    assert guard._worktree_git_mode(repo, regular) == "100644"
    assert guard._worktree_git_mode(repo, script) == "100755"
    regular_index = guard._index_blob(repo, regular)
    script_index = guard._index_blob(repo, script)
    assert regular_index is not None and regular_index[0] == "100644"
    assert script_index is not None and script_index[0] == "100755"
    code, err = _run(repo, capsys)
    assert code == 0 and err == ""

    # Staged as a normal git mode, then the disk mode is tightened. 600 stays
    # 100644 and 700 stays 100755, so the pins still match.
    place(regular, regular_bytes, 0o644)
    (repo / regular).chmod(0o600)
    place(script, script_bytes, 0o755)
    (repo / script).chmod(0o700)
    assert guard._worktree_git_mode(repo, regular) == "100644"
    assert guard._worktree_git_mode(repo, script) == "100755"
    code, err = _run(repo, capsys)
    assert code == 0 and err == ""

    # 700 sets the execute bit, so it does not satisfy a 100644 pin.
    (repo / regular).chmod(0o700)
    code, err = _run(repo, capsys)
    assert code == 1
    assert err == f"clean-tree guard: dirty path(s): {regular}\n"

    # 600 clears the execute bit, so it does not satisfy a 100755 pin.
    (repo / regular).chmod(0o600)
    (repo / script).chmod(0o600)
    code, err = _run(repo, capsys)
    assert code == 1
    assert err == f"clean-tree guard: dirty path(s): {script}\n"


def test_status_overlay_new_paths_accept_normalized_disk_modes(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The status-page pins pass at disk mode 600 or 700 when absent from HEAD.

    ``research/coding_inbox/NOW.md`` stays an id-only pin when its blob is not
    in this clone. Every other new path is staged from the pinned blob.
    """
    repo = _init(tmp_path)
    disk_mode_for = {
        "deploy/caddy/entrypoint.sh": 0o700,
    }
    staged = {
        ".env.example",
        ".gitignore",
        "deploy/caddy/Caddyfile",
        "deploy/caddy/entrypoint.sh",
        "deploy/status/Dockerfile",
        "deploy/status/docker-compose.sgp1.yml",
        "docker-compose.status.yml",
        "docs/runbooks/status_page.md",
        "pyproject.toml",
        "tests/test_blotter_strategy.py",
        "tests/test_dashboard_desk.py",
        "tests/test_status_page.py",
    }
    assert guard.ALLOWED_OVERLAY["research/coding_inbox/NOW.md"] == (
        "100644",
        "b02167b0a4426cf53e264375823055992530f47f",
    )
    for path in sorted(staged):
        mode, sha = guard.ALLOWED_OVERLAY[path]
        blob = subprocess.run(
            ["git", "-C", str(ROOT), "cat-file", "blob", sha],
            capture_output=True,
        )
        assert blob.returncode == 0 and blob.stdout, path
        file = repo / path
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_bytes(blob.stdout)
        file.chmod(disk_mode_for.get(path, 0o600))
        _git(repo, "add", "--", path)
        # The fixture commit does not contain these paths.
        missing = subprocess.run(
            ["git", "-C", str(repo), "cat-file", "-e", f"HEAD:{path}"],
            capture_output=True,
        )
        assert missing.returncode != 0
        assert guard._worktree_git_mode(repo, path) == mode
        assert guard._index_blob(repo, path) == (mode, sha)
    code, err = _run(repo, capsys)
    assert code == 0 and err == ""


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
                "api/desk_status.py",
                "api/observer_status.py",
                "api/static/index.html",
                "api/why_no_trade.py",
                "tests/test_dashboard_ux.py",
                "tests/test_why_no_trade.py",
                # Id-only SGP1 pin. The blob is not in this clone.
                "research/coding_inbox/NOW.md",
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
