"""Runs the agent-action cross-post tests of YPhotoSharing (F6.2) in a separate interpreter, like test_federation_bus.py.
tests/federation_agent_crosspost_impl.py holds them."""

import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


pytest.importorskip("ysocial_federation", reason="the federation SDK is not installed")


def test_federation_agent_crosspost_in_isolation():
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", str(ROOT / "tests" / "federation_agent_crosspost_impl.py")],
        cwd=ROOT, capture_output=True, text=True, timeout=300,
    )
    assert proc.returncode == 0, proc.stdout[-3000:] + proc.stderr[-1000:]
