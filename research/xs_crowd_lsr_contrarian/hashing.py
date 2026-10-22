"""Sha256 of the harness, the scorer, and a run directory.

Bundle hash, in sorted path order::

    sha256.update(relative_posix_path)
    sha256.update(NUL)
    sha256.update(file_bytes)
    sha256.update(NUL)

Document files are checked one by one against the pins. They are not part
of either code bundle.
"""

from __future__ import annotations

import hashlib
import os
from pathlib import Path

from research.xs_crowd_lsr_contrarian.pins import (
    DOC_FILES,
    HARNESS_FILES,
    PACKAGE_DIR,
    RUNNER_FILES,
    SCORER_FILES,
)


class HashSeedError(RuntimeError):
    """The process was not started with PYTHONHASHSEED=0."""


def assert_pythonhashseed() -> str:
    """Refuse unless the interpreter was started with PYTHONHASHSEED=0.

    Assigning PYTHONHASHSEED on the process environment from inside the
    interpreter would not turn hash randomization off, so the value is
    only read. The shell prefix on the documented command is what sets it.
    """
    value = os.environ.get("PYTHONHASHSEED")
    if value != "0":
        raise HashSeedError(
            "refusing to run: PYTHONHASHSEED must be '0' "
            f"(os.environ.get('PYTHONHASHSEED') is {value!r}). "
            "Start the process as PYTHONHASHSEED=0 python -m research.xs_crowd_lsr_contrarian"
        )
    return value


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def bundle_sha256(filenames: tuple[str, ...] | list[str], root: Path | None = None) -> str:
    """Hash a fixed file list. A missing file is an error, not a skip."""
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


def assert_documents() -> dict[str, str]:
    """Sha256 of each shipped document. A mismatch refuses the run."""
    found: dict[str, str] = {}
    for name, expected in DOC_FILES:
        path = PACKAGE_DIR / name
        if not path.is_file():
            raise FileNotFoundError(f"{name} is missing; refusing to run")
        digest = sha256_file(path)
        if digest != expected:
            raise RuntimeError(f"{name} sha256 {digest} != pin {expected}")
        found[name] = digest
    return found


def source_hashes() -> dict[str, object]:
    """Per-file sha256 plus the harness and scorer bundle hashes."""
    files: dict[str, str] = {}
    for name in (*HARNESS_FILES, *SCORER_FILES, *RUNNER_FILES):
        files[name] = sha256_file(PACKAGE_DIR / name)
    for name, _expected in DOC_FILES:
        files[name] = sha256_file(PACKAGE_DIR / name)
    return {
        "harness_sha256": bundle_sha256(HARNESS_FILES),
        "scorer_sha256": bundle_sha256(SCORER_FILES),
        "files": files,
    }


def format_source_hashes(hashes: dict[str, object] | None = None) -> str:
    """Plain-text report printed by the ``hash`` command."""
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


def write_sha256sums(directory: Path, *, exclude: frozenset[str] | None = None) -> str:
    """Write SHA256SUMS for every file in ``directory`` except itself.

    ``exclude`` keeps post-seal sidecars (FINAL_HASH, metrics.json) out of
    the sealed set. Returns the sha256 of the SHA256SUMS bytes. That digest
    is the seal.
    """
    skip = {"SHA256SUMS"}
    if exclude:
        skip |= set(exclude)
    paths = sorted(p for p in directory.iterdir() if p.is_file() and p.name not in skip)
    lines = [f"{sha256_file(path)}  {path.name}" for path in paths]
    text = ("\n".join(lines) + "\n") if lines else ""
    target = directory / "SHA256SUMS"
    target.write_text(text, encoding="utf-8")
    return sha256_file(target)
