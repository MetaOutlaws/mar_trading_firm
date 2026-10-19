"""Frontend observer poll: a failed poll keeps the last render; empty clears it."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

NODE_TEST = Path(__file__).resolve().parent / "observers_poll.test.js"


def _node() -> str:
    binary = shutil.which("node")
    if not binary:
        pytest.fail("node is required to run the observers poll tests")
    return binary


@pytest.mark.parametrize(
    "name",
    [
        "failed or timed-out poll keeps the previous render",
        "explicit empty state clears the previous render",
    ],
)
def test_observer_poll_frontend(name: str) -> None:
    completed = subprocess.run(
        [_node(), "--test", "--test-name-pattern", name, str(NODE_TEST)],
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stdout + "\n" + completed.stderr


def test_observer_poll_schedule_and_abort() -> None:
    """Backoff, overlap, and unmount-abort travel with the two render cases."""
    completed = subprocess.run(
        [_node(), "--test", str(NODE_TEST)],
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stdout + "\n" + completed.stderr
