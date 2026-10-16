"""Sha256 of the harness source, the scorer source, and run outputs.

Bundle hash, in sorted path order::

    sha256.update(relative_posix_path)
    sha256.update(NUL)
    sha256.update(file_bytes)
    sha256.update(NUL)

SPEC.md and PREREG.md are hashed on their own. They are not part of
either code bundle. ``__init__.py`` and ``__main__.py`` are reported per
file and are not part of the two bundles.

Garwe has not countersigned. ``hash_status`` stays ``provisional`` until
``COUNTERSIGN.md`` exists. Adding that file does not change either bundle.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

from research.new_listing_drift import PACKAGE_DIR

#: Engine that turns tapes and the catalog into spread trades.
HARNESS_FILES: tuple[str, ...] = (
    "HOLDOUT_LOCK",
    "catalog.py",
    "cells.py",
    "costs.py",
    "engine.py",
    "harness.py",
    "hashing.py",
    "tape.py",
)

#: Gates, the week-cluster bootstrap, and the random-date book.
SCORER_FILES: tuple[str, ...] = ("scorer.py",)

#: Documents copied verbatim. Hashed individually, not inside a code bundle.
DOC_FILES: tuple[str, ...] = ("SPEC.md", "PREREG.md")

RUNNER_FILES: tuple[str, ...] = ("__init__.py", "__main__.py")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def bundle_sha256(filenames: tuple[str, ...] | list[str], root: Path | None = None) -> str:
    """Hash a fixed file list. Missing files are an error, not a skip."""
    base = root or PACKAGE_DIR
    digest = hashlib.sha256()
    for name in sorted(filenames):
        path = base / name
        if not path.is_file():
            raise FileNotFoundError(f"bundle file missing: {name}")
        digest.update(name.encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def countersign_path() -> Path:
    return PACKAGE_DIR / "COUNTERSIGN.md"


def countersign_present() -> bool:
    """True only when Garwe's countersign file is in the package."""
    path = countersign_path()
    return path.is_file() and path.stat().st_size > 0


def source_hashes() -> dict[str, object]:
    """Per-file sha256 plus the two bundle hashes.

    The bundles are real digests of the current source. ``hash_status`` is
    ``provisional`` until a countersign file exists; they are not an ACK.
    """
    files: dict[str, str] = {}
    for name in (*HARNESS_FILES, *SCORER_FILES, *DOC_FILES, *RUNNER_FILES):
        files[name] = sha256_file(PACKAGE_DIR / name)
    signed = countersign_present()
    countersign = sha256_file(countersign_path()) if signed else None
    return {
        "hash_status": "countersigned" if signed else "provisional",
        "garwe_ack": signed,
        "countersign_sha256": countersign,
        "harness_sha256": bundle_sha256(HARNESS_FILES),
        "scorer_sha256": bundle_sha256(SCORER_FILES),
        "files": files,
    }


def format_source_hashes(hashes: dict[str, object] | None = None) -> str:
    """Plain-text report printed before any run and by the ``hash`` command."""
    payload = hashes or source_hashes()
    files = payload["files"]
    assert isinstance(files, dict)
    lines = [
        f"hash_status     {payload['hash_status']}",
        f"garwe_ack       {str(payload['garwe_ack']).lower()}",
        f"harness_sha256  {payload['harness_sha256']}",
        f"scorer_sha256   {payload['scorer_sha256']}",
        f"countersign_sha256  {payload['countersign_sha256']}",
        "files:",
    ]
    for name in sorted(files):
        lines.append(f"  {files[name]}  {name}")
    return "\n".join(lines) + "\n"


def write_sha256sums(directory: Path) -> str:
    """Write SHA256SUMS for every file in ``directory`` except itself.

    Returns the sha256 of the SHA256SUMS bytes. That digest is the
    main-output hash the holdout and the 2026 veto require.
    """
    paths = sorted(
        p for p in directory.iterdir() if p.is_file() and p.name != "SHA256SUMS"
    )
    lines = [f"{sha256_file(path)}  {path.name}" for path in paths]
    text = ("\n".join(lines) + "\n") if lines else ""
    target = directory / "SHA256SUMS"
    target.write_text(text, encoding="utf-8")
    return sha256_file(target)
