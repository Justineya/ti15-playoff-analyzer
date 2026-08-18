#!/usr/bin/env python3
"""One-shot playoff refresh: ingest → bracket → odds → simulate → bundle."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"


def run(name: str) -> None:
    print("==>", name)
    subprocess.check_call([sys.executable, str(SCRIPTS / name)], cwd=str(ROOT))


def main() -> None:
    run("ingest_games.py")
    run("resolve_bracket.py")
    run("fetch_polymarket.py")
    run("simulate_playoffs.py")
    run("build_bundle.py")
    print("refresh ok")


if __name__ == "__main__":
    main()
