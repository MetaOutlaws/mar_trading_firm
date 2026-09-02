"""Single-instance locks so two paper loops cannot scan the same book."""

from __future__ import annotations

import os
from pathlib import Path

from config.settings import PROJECT_ROOT

PAPER_PID_PATH = PROJECT_ROOT / "data" / "paper_trading.pid"


def pid_alive(pid: int | None) -> bool:
    """True if `pid` is a live process. Signal 0 is not reliable on Windows."""
    if not pid:
        return False
    try:
        pid_i = int(pid)
    except (TypeError, ValueError):
        return False
    if os.name == "nt":
        import ctypes

        process_query_limited = 0x1000
        handle = ctypes.windll.kernel32.OpenProcess(process_query_limited, False, pid_i)
        if not handle:
            return False
        # OpenProcess can still return a handle for a process that has already
        # exited. STILL_ACTIVE (259) is the only live state.
        exit_code = ctypes.c_ulong()
        ok = ctypes.windll.kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code))
        ctypes.windll.kernel32.CloseHandle(handle)
        return bool(ok) and int(exit_code.value) == 259
    try:
        os.kill(pid_i, 0)
    except OSError:
        return False
    return True


def read_pidfile(path: Path) -> dict[str, object]:
    """Return `{pid, alive}` for a pid file, or pid=None if missing."""
    if not path.exists():
        return {"pid": None, "alive": False, "path": str(path)}
    try:
        pid = int(path.read_text(encoding="utf-8").strip().split()[0])
    except (OSError, ValueError):
        return {"pid": None, "alive": False, "path": str(path)}
    return {"pid": pid, "alive": pid_alive(pid), "path": str(path)}


def acquire_pidfile(path: Path, label: str) -> int:
    """Write this process id, or raise SystemExit if another instance is live."""
    existing = read_pidfile(path)
    old = existing.get("pid")
    if existing.get("alive") and old != os.getpid():
        raise SystemExit(
            f"{label} is already running as pid {old}. "
            "Stop that process before starting another."
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(str(os.getpid()), encoding="utf-8")
    return os.getpid()


def release_pidfile(path: Path) -> None:
    """Delete the pid file if it still names this process."""
    current = read_pidfile(path)
    if current.get("pid") == os.getpid() and path.exists():
        try:
            path.unlink()
        except OSError:
            pass
