"""Sha256 of the harness source, the scorer source, and run outputs.

Bundle hash, in sorted path order::

    sha256.update(relative_posix_path)
    sha256.update(NUL)
    sha256.update(file_bytes)
    sha256.update(NUL)

SPEC.md, PREREG.md and COUNTERSIGN.md are hashed on their own. They are
not part of either code bundle. ``__init__.py`` and ``__main__.py`` are
reported per file and are not part of the two ACK bundles: those bundles
are the engine and the scorer.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

from research.xs_spread import PACKAGE_DIR

#: Engine that produces weights, paths, weekly spread returns, trades, turnover, costs.
HARNESS_FILES: tuple[str, ...] = (
    "HOLDOUT_LOCK",
    "bab.py",
    "book.py",
    "cells.py",
    "costs.py",
    "harness.py",
    "hashing.py",
    "signals.py",
    "tape.py",
)

#: Metrics and the turnover-matched random book. Hashed on its own.
SCORER_FILES: tuple[str, ...] = ("scorer.py",)

#: Documents copied verbatim. Hashed individually, not inside a code bundle.
DOC_FILES: tuple[str, ...] = ("SPEC.md", "PREREG.md", "COUNTERSIGN.md")

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


def source_hashes() -> dict[str, object]:
    """Per-file sha256 plus the two ACK bundle hashes."""
    files: dict[str, str] = {}
    for name in (*HARNESS_FILES, *SCORER_FILES, *DOC_FILES, *RUNNER_FILES):
        files[name] = sha256_file(PACKAGE_DIR / name)
    return {
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
        f"harness_sha256  {payload['harness_sha256']}",
        f"scorer_sha256   {payload['scorer_sha256']}",
        "files:",
    ]
    for name in sorted(files):
        lines.append(f"  {files[name]}  {name}")
    return "\n".join(lines) + "\n"


def write_sha256sums(directory: Path) -> str:
    """Write SHA256SUMS for every file in ``directory`` except itself.

    Returns the sha256 of the SHA256SUMS bytes. That digest is the
    main-output hash the holdout lock requires.
    """
    paths = sorted(
        p for p in directory.iterdir() if p.is_file() and p.name != "SHA256SUMS"
    )
    lines = [f"{sha256_file(path)}  {path.name}" for path in paths]
    text = ("\n".join(lines) + "\n") if lines else ""
    target = directory / "SHA256SUMS"
    target.write_text(text, encoding="utf-8")
    return sha256_file(target)
