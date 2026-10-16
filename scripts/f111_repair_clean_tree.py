"""Clean-tree guard for the F111 execution-repair collector.

The collector refuses to read a Singapore checkout whose tracked files differ
from the pinned repair commit ``b00c4f73``. The allowlist is the 2026-10-16
SGP1 overlay, the ``firm/memory.py`` hot fix, ``api/observer_status.py`` from
``ee994abe``, and the eight files #135 changes at ``3424c265`` (applied on
the server as an overlay on ``b00c4f73``). Nothing else may stay staged.

A path is allowed only when it is one of those paths and both the index and
the worktree are the pinned git blob at that path's pinned mode. The two
status shell scripts are 100755, matching the commits that added them. Every
other pinned path is 100644. Any other staged or unstaged tracked path fails.
An allowed path also fails when its bytes differ or either copy has the other
mode. Untracked files stay out of scope, matching the previous
``git diff HEAD`` check, which never saw them.
"""

from __future__ import annotations

import csv
import json
import subprocess
import sys
from collections.abc import Mapping
from pathlib import Path

# (mode, blob). FINDINGS abbreviations and the later short ids are in the
# comments. Each short id names one blob; the value is that full git blob id,
# not a raw sha256. Mode is what the adding commit recorded: 100755 for the
# two status shell scripts, 100644 for every other path. Both the index and
# the worktree must match both fields. firm/memory.py is the SGP1 hash-object
# id; that blob does not have to be in this clone.
ALLOWED_OVERLAY: dict[str, tuple[str, str]] = {
    "api/app.py": ("100644", "c9b9f03f8f4759e809ec17324daee52baffae4fa"),  # c9b9f03f
    "api/desk_status.py": ("100644", "0ebd3b44a5bf36ff5287780e11090d72bbb83b12"),  # 0ebd3b44
    "api/observer_status.py": ("100644", "28713d3bc4a18806b6dfbbe1675c9108afb5594e"),  # 28713d3b
    "api/static/index.html": ("100644", "e5649287f0122def78d7b3ecab7ddce4c2adec44"),  # e5649287
    "api/status_app.py": ("100644", "ad4de7a26776f2a14dd384057ef85c47fd936ef7"),  # ad4de7a2
    "api/status_auth.py": ("100644", "28a9ccd99a3705dcbe370430e1e72215e6f1b51d"),  # 28a9ccd9
    "api/status_snapshot.py": ("100644", "9fe475f649a0f049f6406ddece144b7481f66b4c"),  # 9fe475f6
    "config/settings.py": ("100644", "9c02305f6e855960410daa9761abc4a849c97a1a"),  # 9c02305f
    # Blobs of these paths at 3424c265 (#135), overlaid on b00c4f73.
    "core/execution/engine.py": ("100644", "fd6a6b8e4238312502e830d41ef7ae29f382a0d4"),
    "core/execution/f111_paper.py": ("100644", "ab390d3f2b98d6977574d2a40f265e7a2154a8fe"),
    "core/execution/paper.py": ("100644", "c73ead0f9dc5a2373f17da76cb2b1c9d11804381"),
    "core/execution/paper_bar_eval.py": ("100644", "5374ab24628ef9e330dbf4b6f433461cc1f299e5"),
    "core/execution/paper_cash.py": ("100644", "fde5e49bc1e72261ce258a182aee2e7913fb8f52"),
    "core/execution/paper_settle.py": ("100644", "830b3c5b9e408c726bd6f2c9714347cf61b8d3b3"),
    "firm/memory.py": ("100644", "fba54b57a7c07c2540dc2246b83ca16913179bfa"),  # fba54b57
    "scripts/run_status_page.py": (
        "100644",
        "b2f130fd36fda79a3d23d987c56ad3484f7e7767",
    ),  # b2f130fd
    "scripts/status_cert_fingerprint.sh": (
        "100755",
        "94c8b4126490d57ef728d258567dd294e098f0f4",
    ),  # 94c8b412
    "scripts/ufw_status_443.sh": ("100755", "f9ef5d0f510b19421d88f6f249d1c8fb37f92824"),  # f9ef5d0f
    "tests/test_f111_execution_repair.py": ("100644", "162c2620ea20ae7c24e09b08a96e46cbb5fcf913"),
    "tests/test_scan_fill_counts.py": ("100644", "f0520d2ea966389b521b5cd962a0cdd150696d53"),
}


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


def _worktree_git_mode(repo: Path, path: str) -> str | None:
    """Return git's 100644 or 100755 for a regular file.

    Git records 100755 when any execute bit is set. Symlinks and missing
    paths return None so they cannot satisfy either pinned mode.
    """
    candidate = repo / path
    if candidate.is_symlink() or not candidate.is_file():
        return None
    if candidate.stat().st_mode & 0o111:
        return "100755"
    return "100644"


def _overlay_ok(repo: Path, path: str, expected: tuple[str, str]) -> bool:
    """Both copies must be the pinned blob and both must be the pinned mode."""
    expected_mode, expected_blob = expected
    staged = _index_blob(repo, path)
    if staged is None:
        return False
    mode, blob = staged
    return (
        mode == expected_mode
        and blob == expected_blob
        and _worktree_git_mode(repo, path) == expected_mode
        and _worktree_blob(repo, path) == expected_blob
    )


def clean_tree_violations(
    repo: Path,
    allowed: Mapping[str, tuple[str, str]] | None = None,
) -> list[str]:
    """Return dirty tracked paths that are not the exact pinned overlay.

    An empty list means the collector may continue. ``allowed`` is the
    production pin unless a test supplies a fixture map of ``(mode, blob)``.
    """
    pins = ALLOWED_OVERLAY if allowed is None else allowed
    violations: list[str] = []
    for path in sorted(changed_tracked_paths(repo)):
        expected = pins.get(path)
        if expected is None or not _overlay_ok(repo, path, expected):
            violations.append(path)
    return violations


# Offline historical run shipped with the handoff. It is not copied into the
# deployed b00c4f73 tree. A collector extracted without these files fails closed.
_PARITY_CSV = Path("docs/grok-execution-handoff-20261015/saved_path_checks.csv")
_PARITY_VALIDATION = Path("docs/grok-execution-handoff-20261015/repair_validation.json")


def _saved_path_row_matches(row: Mapping[str, str]) -> bool:
    """One saved-path row agrees with the historical run's own columns.

    Admitted rows must match semantics, runtime, the cash journal and observed
    funding. Rows the run left unadmitted keep those runtime cells empty; a
    value there would be a different result than the one that was recorded.
    """
    if row.get("semantics_match") != "True" or row.get("observed_funding_match") != "True":
        return False
    if row.get("admitted") == "True":
        return row.get("runtime_match") == "True" and row.get("cash_journal_match") == "True"
    if row.get("admitted") == "False":
        return row.get("runtime_match") == "" and row.get("cash_journal_match") == ""
    return False


def saved_path_parity(root: Path) -> str:
    """Derive the parity label from the checked-in run, or fail closed.

    Matching historical rows are not deployed forward-fill parity. The label
    stays ``UNVERIFIED`` unless that run's validation also records a completed
    remote execution and ``deployed_saved_path_parity`` of ``PASS``. A row that
    does not match the recorded run is ``FAIL``. A missing or unreadable
    artifact is ``UNVERIFIED``.
    """
    try:
        csv_path = root / _PARITY_CSV
        validation_path = root / _PARITY_VALIDATION
        if not csv_path.is_file() or not validation_path.is_file():
            return "UNVERIFIED"
        with csv_path.open(newline="", encoding="utf-8") as handle:
            rows = list(csv.DictReader(handle))
        validation = json.loads(validation_path.read_text(encoding="utf-8"))
        if not isinstance(validation, dict):
            return "UNVERIFIED"
    except (OSError, csv.Error, json.JSONDecodeError, UnicodeError):
        return "UNVERIFIED"
    if not rows or not all(_saved_path_row_matches(row) for row in rows):
        return "FAIL"
    deployed = validation.get("deployed_saved_path_parity")
    if deployed == "PASS" and validation.get("remote_execution_performed") is True:
        return "PASS"
    return "UNVERIFIED"


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
