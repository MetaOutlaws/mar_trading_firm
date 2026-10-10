"""Desk sha when the container has no .git directory.

Order is env (GIT_SHA, then APP_GIT_SHA), then a stamp file, then git.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from api.desk_status import _sha_files, deployed_git_sha

SHA_ENV = "a" * 40
SHA_APP = "b" * 40
SHA_FILE = "c" * 40
SHA_DATA = "d" * 40
SHA_GIT = "e" * 40


def _clear_sha_env(monkeypatch) -> None:
    for key in ("GIT_SHA", "APP_GIT_SHA", "DEPLOYED_GIT_SHA", "GIT_COMMIT"):
        monkeypatch.delenv(key, raising=False)


def test_stamp_file_candidates_cover_app_and_data() -> None:
    paths = [str(path) for path in _sha_files(Path("/opt/app"))]
    assert paths[0] == "/app/GIT_SHA"
    assert "/opt/app/GIT_SHA" in paths
    assert "/opt/app/data/DEPLOYED_SHA" in paths


def test_git_sha_env_beats_file_and_git(monkeypatch, tmp_path) -> None:
    _clear_sha_env(monkeypatch)
    monkeypatch.setenv("GIT_SHA", SHA_ENV + "\n")
    monkeypatch.setenv("APP_GIT_SHA", SHA_APP)
    (tmp_path / "GIT_SHA").write_text(SHA_FILE + "\n", encoding="utf-8")
    monkeypatch.setattr(
        "api.desk_status._sha_files",
        lambda root: [tmp_path / "GIT_SHA"],
    )

    def boom(*args, **kwargs):
        raise AssertionError("git must not run when GIT_SHA is set")

    monkeypatch.setattr(subprocess, "check_output", boom)
    found = deployed_git_sha(tmp_path)
    assert found["sha"] == SHA_ENV
    assert found["short"] == SHA_ENV[:12]
    assert found["source"] == "env"
    assert found["env"] == "GIT_SHA"


def test_app_git_sha_is_the_second_env(monkeypatch, tmp_path) -> None:
    _clear_sha_env(monkeypatch)
    monkeypatch.setenv("APP_GIT_SHA", SHA_APP)
    monkeypatch.setenv("DEPLOYED_GIT_SHA", "f" * 40)
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "DEPLOYED_SHA").write_text(SHA_DATA, encoding="utf-8")
    found = deployed_git_sha(tmp_path)
    assert found["sha"] == SHA_APP
    assert found["source"] == "env"
    assert found["env"] == "APP_GIT_SHA"


def test_file_used_when_env_missing_and_git_would_differ(monkeypatch, tmp_path) -> None:
    """A container without .git still shows the stamp file, ahead of git."""
    _clear_sha_env(monkeypatch)
    app_file = tmp_path / "app" / "GIT_SHA"
    data_file = tmp_path / "data" / "DEPLOYED_SHA"
    app_file.parent.mkdir()
    data_file.parent.mkdir()
    app_file.write_text("# deploy\n" + SHA_FILE + "\n", encoding="utf-8")
    data_file.write_text(SHA_DATA + "\n", encoding="utf-8")
    monkeypatch.setattr(
        "api.desk_status._sha_files",
        lambda root: [app_file, data_file],
    )
    monkeypatch.setattr(
        subprocess,
        "check_output",
        lambda *args, **kwargs: SHA_GIT + "\n",
    )
    found = deployed_git_sha(tmp_path)
    assert found == {
        "sha": SHA_FILE,
        "short": SHA_FILE[:12],
        "source": "file",
        "path": str(app_file),
    }


def test_data_deployed_sha_when_app_file_missing(monkeypatch, tmp_path) -> None:
    _clear_sha_env(monkeypatch)
    data_file = tmp_path / "data" / "DEPLOYED_SHA"
    data_file.parent.mkdir()
    data_file.write_text(SHA_DATA + "\n", encoding="utf-8")
    monkeypatch.setattr(
        "api.desk_status._sha_files",
        lambda root: [tmp_path / "missing" / "GIT_SHA", data_file],
    )
    monkeypatch.setattr(
        subprocess,
        "check_output",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            subprocess.CalledProcessError(128, ["git"])
        ),
    )
    found = deployed_git_sha(tmp_path)
    assert found["source"] == "file"
    assert found["sha"] == SHA_DATA
    assert found["path"] == str(data_file)


def test_git_when_no_env_and_no_file(monkeypatch, tmp_path) -> None:
    _clear_sha_env(monkeypatch)
    monkeypatch.setattr("api.desk_status._sha_files", lambda root: [])
    monkeypatch.setattr(
        subprocess,
        "check_output",
        lambda *args, **kwargs: SHA_GIT + "\n",
    )
    found = deployed_git_sha(tmp_path)
    assert found["sha"] == SHA_GIT
    assert found["source"] == "git"


def test_unavailable_when_container_has_no_git_and_no_stamp(monkeypatch, tmp_path) -> None:
    _clear_sha_env(monkeypatch)
    monkeypatch.setattr("api.desk_status._sha_files", lambda root: [tmp_path / "nope"])

    def missing(*args, **kwargs):
        raise FileNotFoundError("git")

    monkeypatch.setattr(subprocess, "check_output", missing)
    found = deployed_git_sha(tmp_path)
    assert found == {"sha": None, "short": None, "source": "unavailable"}
