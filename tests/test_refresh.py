#!/usr/bin/env python3
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import refresh  # noqa: E402


def test_live_snapshot_failure_does_not_abort() -> None:
    orig = subprocess.check_call

    def boom(cmd, cwd=None):
        raise subprocess.CalledProcessError(1, cmd)

    subprocess.check_call = boom
    try:
        refresh.run("fetch_live.py", required=False)
        raised = False
        try:
            refresh.run("fetch_live.py", required=True)
        except subprocess.CalledProcessError:
            raised = True
        assert raised
    finally:
        subprocess.check_call = orig


if __name__ == "__main__":
    test_live_snapshot_failure_does_not_abort()
    print("test_refresh ok")
