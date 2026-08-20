#!/usr/bin/env python3
"""One-shot playoff refresh: ingest → schedule → bracket → odds → simulate → bundle."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"


def run(name: str, required: bool = True) -> None:
    print("==>", name)
    try:
        subprocess.check_call([sys.executable, str(SCRIPTS / name)], cwd=str(ROOT))
    except subprocess.CalledProcessError as err:
        if required:
            raise
        print(name, "failed, continuing", err.returncode)


def main() -> None:
    run("ingest_games.py")
    run("fetch_schedule.py")
    run("resolve_bracket.py")
    run("fetch_polymarket.py")
    run("simulate_playoffs.py")
    # Fresh live.json first so the briefing can switch to Game N+1 from LP score.
    run("fetch_live.py", required=False)
    run("daily_briefing.py")
    run("map_trigger.py")
    run("build_bundle.py")
    run("launch_eod_cursor.py", required=False)
    print("refresh ok")


if __name__ == "__main__":
    main()
