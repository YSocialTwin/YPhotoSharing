"""Runs the federated-clock hook tests of YPhotoSharing (F2.7) in a separate interpreter.

They import the server and client modules with a stand-in for the optional annotation stack; doing that in-process
would change how the other tests of this repository import those modules. tests/federation_clock_impl.py holds them."""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_federation_clock_hooks_in_isolation():
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", str(ROOT / "tests" / "federation_clock_impl.py")],
        cwd=ROOT, capture_output=True, text=True, timeout=300,
    )
    assert proc.returncode == 0, proc.stdout[-3000:] + proc.stderr[-1000:]
