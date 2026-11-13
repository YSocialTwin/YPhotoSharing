"""Runs the INV-17 binding tests of YPhotoSharing in a separate interpreter (same reason as the clock tests:
the server and client modules are imported with a stand-in for the optional annotation stack).
tests/federation_bindings_impl.py holds them."""

import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


pytest.importorskip("ysocial_federation", reason="the federation SDK is not installed")


def test_federation_bindings_in_isolation():
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", str(ROOT / "tests" / "federation_bindings_impl.py")],
        cwd=ROOT, capture_output=True, text=True, timeout=300,
    )
    assert proc.returncode == 0, proc.stdout[-3000:] + proc.stderr[-1000:]
