"""Runs the decision (P14) cross-post tests of YPhotoSharing in a separate interpreter, like test_federation_agent_crosspost.py.
tests/federation_decision_impl.py holds them."""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_federation_decision_in_isolation():
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", str(ROOT / "tests" / "federation_decision_impl.py")],
        cwd=ROOT, capture_output=True, text=True, timeout=300,
    )
    assert proc.returncode == 0, proc.stdout[-3000:] + proc.stderr[-1000:]
