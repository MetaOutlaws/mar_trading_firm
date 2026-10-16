"""Clean-tree guard for the F111 execution-repair collector.

The collector refuses to read a Singapore checkout whose tracked files differ
from the pinned repair commit ``b00c4f73``. The allowlist is the 2026-10-16
SGP1 overlay, the ``firm/memory.py`` hot fix, the eight files #135 changes at
``3424c265``, ``firm/scan_inbox.py`` at ``8fe9688f`` (#138),
``tests/test_scan_inbox.py`` at ``8e61d1b2`` (#136, replacing ``456b0c8e``),
the dashboard pins ``api/desk_status.py``, ``api/observer_status.py``,
``api/static/index.html``, ``api/dashboard_cache.py``,
``api/why_no_trade.py``, ``tests/test_dashboard_ux.py``, and
``tests/test_why_no_trade.py``, the read-side caches ``firm/read_cache.py``,
``firm/integrity.py``, ``firm/orchestrator.py``, ``firm/research_catalog.py``,
and ``core/strategy/spec_sleeve.py``, and the status-page overlay
(``.env.example``, ``.gitignore``, ``docker-compose.status.yml``,
``docs/runbooks/status_page.md``, ``pyproject.toml``,
``research/coding_inbox/NOW.md``, ``tests/test_blotter_strategy.py``,
``tests/test_dashboard_desk.py``, ``tests/test_status_page.py``,
``deploy/caddy/Caddyfile``, ``deploy/caddy/entrypoint.sh``,
``deploy/status/Dockerfile``, and ``deploy/status/docker-compose.sgp1.yml``).
Those paths are applied on the server as an overlay on ``b00c4f73``. Nothing
else may stay staged. The cache module is part of that overlay: the desk
panels import it. The why-no-trade panel is included: the why modules stay
the 9caf785 blobs, and the desk, observer, and page pins add that panel on
top of the 60s poll, the in-flight guard, and the 4s observers timeout.

A path is allowed only when it is one of those paths and both the index and
the worktree are the pinned git blob at that path's pinned mode. The two
status shell scripts and ``deploy/caddy/entrypoint.sh`` are 100755. Every
other pinned path is 100644. Worktree modes are git's executable bit, so disk
mode 600 counts as 100644 and 700 as 100755. A path that is in the index but
missing from HEAD still passes when it is pinned. Any other staged or
unstaged tracked path fails. An allowed path also fails when its bytes differ
or either copy has the other mode. Untracked files stay out of scope,
matching the previous ``git diff HEAD`` check, which never saw them.
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
# not a raw sha256. Mode is the git mode: 100755 for the two status shell
# scripts and deploy/caddy/entrypoint.sh, 100644 for every other path. Both
# the index and the worktree must match both fields. firm/memory.py, the later
# dashboard pins, and research/coding_inbox/NOW.md are SGP1 hash-object ids;
# those blobs do not have to be in this clone.
ALLOWED_OVERLAY: dict[str, tuple[str, str]] = {
    "api/app.py": ("100644", "c9b9f03f8f4759e809ec17324daee52baffae4fa"),  # c9b9f03f
    # Desk cache. The panels import this; it is not a trading module.
    "api/dashboard_cache.py": (
        "100644",
        "77f83d566ab03c176dea46904db361d5e074cadb",
    ),  # 77f83d56
    # Cached F111 panel, including why_no_trade. Replaces dbe90dba.
    "api/desk_status.py": ("100644", "ffa6095adc4f0885f8bdf8542d5531b6d3cab193"),  # ffa6095a
    # Cached observers list with the why panel. Replaces a3813379.
    "api/observer_status.py": (
        "100644",
        "4eea3afb165ac25200dca5bc21199582fbda8625",
    ),  # 4eea3afb
    # Panel page, 60s poll, in-flight guard, 4s observers timeout. Replaces c12e3e53.
    "api/static/index.html": (
        "100644",
        "b88ea34763ca8b4b317b20d75bc505cef6922afb",
    ),  # b88ea347
    "api/status_app.py": ("100644", "ad4de7a26776f2a14dd384057ef85c47fd936ef7"),  # ad4de7a2
    "api/status_auth.py": ("100644", "28a9ccd99a3705dcbe370430e1e72215e6f1b51d"),  # 28a9ccd9
    "api/status_snapshot.py": ("100644", "9fe475f649a0f049f6406ddece144b7481f66b4c"),  # 9fe475f6
    "api/why_no_trade.py": ("100644", "1ee0e13f313adca20c43018a6ec804ccde23c207"),  # 1ee0e13f
    "config/settings.py": ("100644", "9c02305f6e855960410daa9761abc4a849c97a1a"),  # 9c02305f
    # Blobs of these paths at 3424c265 (#135), overlaid on b00c4f73.
    "core/execution/engine.py": ("100644", "fd6a6b8e4238312502e830d41ef7ae29f382a0d4"),
    "core/execution/f111_paper.py": ("100644", "ab390d3f2b98d6977574d2a40f265e7a2154a8fe"),
    "core/execution/paper.py": ("100644", "c73ead0f9dc5a2373f17da76cb2b1c9d11804381"),
    "core/execution/paper_bar_eval.py": ("100644", "5374ab24628ef9e330dbf4b6f433461cc1f299e5"),
    "core/execution/paper_cash.py": ("100644", "fde5e49bc1e72261ce258a182aee2e7913fb8f52"),
    "core/execution/paper_settle.py": ("100644", "830b3c5b9e408c726bd6f2c9714347cf61b8d3b3"),
    # Spec JSON is read once per directory mtime. Replaces 55048d05.
    "core/strategy/spec_sleeve.py": (
        "100644",
        "0b9496b0152d32df23313f220129985dd71a104b",
    ),  # 0b9496b0
    # Book certificate is computed once per book sha. Replaces 9dbd11c1.
    "firm/integrity.py": ("100644", "fa4ee9e9e2b33f752d4a964cd5d333f78383c0dd"),  # fa4ee9e9
    # Inbox prune and escalation expiry run at most once a minute on read.
    "firm/memory.py": ("100644", "c5885e60bf784a9f98832a5c825a0af211692ba2"),  # c5885e60
    # /api/floor single-flight, 30s. Replaces d64b6dc3.
    "firm/orchestrator.py": (
        "100644",
        "1ced376e5718b670453d37859c4790651a00231d",
    ),  # 1ced376e
    "firm/read_cache.py": ("100644", "a878bcfe633347928b02c071b5ba2a69eae75fbf"),  # a878bcfe
    # Ranking file is read once per mtime. Replaces a3cb6239.
    "firm/research_catalog.py": (
        "100644",
        "fceddead19de1f6f2cfb25e3427eedd98099c88d",
    ),  # fceddead
    # Blob of this path at 5dff9454 (#138), overlaid on b00c4f73.
    "firm/scan_inbox.py": (
        "100644",
        "8fe9688f6c7001d6dcddfa75b942cde105284a1b",
    ),  # 8fe9688f
    "scripts/run_status_page.py": (
        "100644",
        "b2f130fd36fda79a3d23d987c56ad3484f7e7767",
    ),  # b2f130fd
    "scripts/status_cert_fingerprint.sh": (
        "100755",
        "94c8b4126490d57ef728d258567dd294e098f0f4",
    ),  # 94c8b412
    "scripts/ufw_status_443.sh": ("100755", "f9ef5d0f510b19421d88f6f249d1c8fb37f92824"),  # f9ef5d0f
    # Panel UX contract plus the 4s observers timeout. Replaces 477cf0da.
    "tests/test_dashboard_ux.py": (
        "100644",
        "8df07e92dc81892b24e3f93bd7ca1a9ea266eb0b",
    ),  # 8df07e92
    "tests/test_f111_execution_repair.py": ("100644", "162c2620ea20ae7c24e09b08a96e46cbb5fcf913"),
    "tests/test_scan_fill_counts.py": ("100644", "f0520d2ea966389b521b5cd962a0cdd150696d53"),
    # Inbox read prunes at most once a minute. Replaces 3cc0e6e4.
    "tests/test_scan_inbox.py": (
        "100644",
        "8e61d1b20b853076111341536d7d1d9936251331",
    ),  # 8e61d1b2
    "tests/test_why_no_trade.py": (
        "100644",
        "1e76aaa07bc5f59b7347d494e4e4753b3eb9c410",
    ),  # 1e76aaa0
    # SGP1 status-page overlay on b00c4f73. entrypoint.sh is the only 100755
    # path in this block. research/coding_inbox/NOW.md is an id-only pin.
    # Several of these paths are absent from HEAD; they still pass when the
    # index and the worktree are the pinned blob at the pinned git mode.
    ".env.example": ("100644", "9afdf09c808e1a87178c0eebca826698d75f68db"),  # 9afdf09c
    ".gitignore": ("100644", "cef30f2b9a9fa4603eb869871e431662957e4b65"),  # cef30f2b
    "deploy/caddy/Caddyfile": ("100644", "8814676372bbe8a71b84bdb04c544306046a1e60"),  # 88146763
    "deploy/caddy/entrypoint.sh": (
        "100755",
        "32cbcd8f84796147bd870a04d864330f2c651cbe",
    ),  # 32cbcd8f
    "deploy/status/Dockerfile": ("100644", "9493f6fb6313cacff399b496b285fad418729c2c"),  # 9493f6fb
    "deploy/status/docker-compose.sgp1.yml": (
        "100644",
        "b20ec3cbdd68b376d3903a7af024c51f00afbc4f",
    ),  # b20ec3cb
    "docker-compose.status.yml": (
        "100644",
        "a3a2987d5c6943d256721d676b2ff632bcae0cd9",
    ),  # a3a2987d
    "docs/runbooks/status_page.md": (
        "100644",
        "d6c8de14708addf25a9a8ad3db2283297323124e",
    ),  # d6c8de14
    "pyproject.toml": ("100644", "92461189518d51ddf24a5f0eba7fc4df96e2e142"),  # 92461189
    "research/coding_inbox/NOW.md": (
        "100644",
        "b02167b0a4426cf53e264375823055992530f47f",
    ),  # b02167b0
    "tests/test_blotter_strategy.py": (
        "100644",
        "97cdc4fe10dce3652faa8224716abfd3aa3db45d",
    ),  # 97cdc4fe
    "tests/test_dashboard_desk.py": (
        "100644",
        "49e06a20dec148a9738227bc5e80905a9d15f36c",
    ),  # 49e06a20
    "tests/test_status_page.py": (
        "100644",
        "66625e60d366ac49c957c6cd1df7a6c8ec721c6f",
    ),  # 66625e60
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
    The index diff is what makes a staged-only file fail. A path added to the
    index and absent from HEAD is included, so a pinned new file can pass.
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

    Git records 100755 when any execute bit is set and 100644 otherwise.
    Disk mode 600 therefore counts as 100644, and 700 as 100755. The other
    permission bits are not compared. Symlinks and missing paths return
    None so they cannot satisfy either pinned mode.
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
