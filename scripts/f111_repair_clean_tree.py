"""Clean-tree guard for the F111 execution-repair collector.

The collector refuses to read a Singapore checkout whose tracked files differ
from the pinned repair commit ``b00c4f73``. SGP1 currently has three files from
the blotter Strategy column (#119, squash ``8d35ec7c``) checked out and staged
on top of that tree. Marcus exception 1 tolerates that overlay and nothing
else.

A path is allowed only when it is one of the three #119 paths and both the
index and the worktree are the git blob from that commit (mode 100644). Any
other staged or unstaged tracked path fails. Those three paths also fail when
their bytes differ. Untracked files stay out of scope, matching the previous
``git diff HEAD`` check, which never saw them.
"""

from __future__ import annotations

import subprocess
import sys
from collections.abc import Mapping
from pathlib import Path

# Squash of "Show the opening strategy on the blotter." (#119).
OVERLAY_COMMIT = "8d35ec7c4acaf05958eec79136c3526684517811"

# ``git rev-parse 8d35ec7c:<path>``. These are git blob ids, not raw sha256.
ALLOWED_OVERLAY_BLOBS = {
    "api/app.py": "0b92809901b32009c99c4bbaf0757b56f795d836",
    "api/static/index.html": "c036f22b759ff7fef2d017a014dc2ed73503ed1d",
    "tests/test_blotter_strategy.py": "97cdc4fe10dce3652faa8224716abfd3aa3db45d",
}

_REGULAR_FILE = "100644"


def _git(repo: Path, *args: str, ok: tuple[int, ...] = (0,)) -> subprocess.CompletedProcess[bytes]:
    """Run git in ``repo``. Diff exits 1 when the tree differs; that is not an error."""
    proc = subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
    )
    if proc.returncode not in ok:
        raise subprocess.CalledProcessError(proc.returncode, proc.args, proc.stdout, proc.stderr)
    return proc


def _nul_paths(payload: bytes) -> set[str]:
    text = payload.decode("utf-8", "surrogateescape")
    return {path for path in text.split("\0") if path}


def changed_tracked_paths(repo: Path) -> set[str]:
    """Tracked paths that differ from HEAD in the worktree or only in the index.

    ``git diff HEAD`` misses a staged edit whose worktree was put back to HEAD.
    The index diff is what makes a staged-only file fail.
    """
    worktree = _git(repo, "diff", "--name-only", "-z", "HEAD", ok=(0, 1))
    staged = _git(repo, "diff", "--name-only", "--cached", "-z", "HEAD", ok=(0, 1))
    return _nul_paths(worktree.stdout) | _nul_paths(staged.stdout)


def _index_blob(repo: Path, path: str) -> tuple[str, str] | None:
    """Return ``(mode, blob)`` for the staged path, or None when it is not staged."""
    listed = _git(repo, "ls-files", "--stage", "-z", "--", path)
    records = [record for record in listed.stdout.split(b"\0") if record]
    # A conflict leaves more than one stage. That is not the reviewed overlay.
    if len(records) != 1:
        return None
    record = records[0]
    meta, name = record.split(b"\t", 1)
    if name.decode("utf-8", "surrogateescape") != path:
        return None
    mode, blob, _stage = meta.decode("ascii").split(" ")
    return mode, blob


def _worktree_blob(repo: Path, path: str) -> str | None:
    """Hash the on-disk file. Symlinks and missing paths do not match the overlay."""
    candidate = repo / path
    if candidate.is_symlink() or not candidate.is_file():
        return None
    hashed = _git(repo, "hash-object", "--", path)
    return hashed.stdout.decode("ascii").strip()


def _overlay_ok(repo: Path, path: str, expected: str) -> bool:
    """Both copies of an allowed path must be the pinned regular-file blob."""
    staged = _index_blob(repo, path)
    if staged is None:
        return False
    mode, blob = staged
    return mode == _REGULAR_FILE and blob == expected and _worktree_blob(repo, path) == expected


def clean_tree_violations(
    repo: Path,
    allowed: Mapping[str, str] | None = None,
) -> list[str]:
    """Return dirty tracked paths that are not the exact #119 overlay.

    An empty list means the collector may continue. ``allowed`` is the
    production pin unless a test supplies a fixture map.
    """
    pins = ALLOWED_OVERLAY_BLOBS if allowed is None else allowed
    violations: list[str] = []
    for path in sorted(changed_tracked_paths(repo)):
        expected = pins.get(path)
        if expected is None or not _overlay_ok(repo, path, expected):
            violations.append(path)
    return violations


def main(argv: list[str] | None = None) -> int:
    """Exit 0 when the tree is clean or is exactly the pinned overlay."""
    args = list(sys.argv if argv is None else argv)
    if len(args) != 2:
        print("usage: f111_repair_clean_tree.py REPO", file=sys.stderr)
        return 2
    repo = Path(args[1])
    try:
        violations = clean_tree_violations(repo)
    except (OSError, subprocess.CalledProcessError):
        print("clean-tree guard could not read git state", file=sys.stderr)
        return 2
    if violations:
        print("clean-tree guard: dirty path(s): " + ", ".join(violations), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
