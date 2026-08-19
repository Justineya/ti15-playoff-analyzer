#!/usr/bin/env python3
"""Pull live Main Event start times from Liquipedia into playoffs.json.

Organizers move kickoff times. The page must follow the published schedule,
not the first draft we stored. Source: Main Event wikitext, Beijing time.
"""
from __future__ import annotations

import gzip
import json
import re
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CST = timezone(timedelta(hours=8))
PAGE = "The_International/2026/Main_Event"
API = "https://liquipedia.net/dota2/api.php"
PAGE_URL = "https://liquipedia.net/dota2/The_International/2026/Main_Event"
UA = {
    "User-Agent": (
        "TI15PlayoffAnalyzer/1.0 "
        "(https://github.com/Justineya/ti15-playoff-analyzer; live playoff schedule)"
    ),
    "Accept-Encoding": "gzip",
    "Accept": "application/json",
}

# Bracket/8U4L2DSL1D slot → our match id.
# Lower-bracket QF is crossed: R2M3 = lbr1a winner vs ubsf2 loser = lbqf1.
LP_TO_OURS = {
    "R1M1": "ubqf1",
    "R1M2": "ubqf2",
    "R1M3": "ubqf3",
    "R1M4": "ubqf4",
    "R1M5": "lbr1a",
    "R1M6": "lbr1b",
    "R2M1": "ubsf1",
    "R2M2": "ubsf2",
    "R2M3": "lbqf1",
    "R2M4": "lbqf2",
    "R3M1": "lbsf",
    "R4M1": "ubf",
    "R4M2": "lbf",
    "R5M1": "gf",
}

MONTHS = {
    "january": 1,
    "february": 2,
    "march": 3,
    "april": 4,
    "may": 5,
    "june": 6,
    "july": 7,
    "august": 8,
    "september": 9,
    "october": 10,
    "november": 11,
    "december": 12,
}

# Hours to add to get Beijing time.
TZ_TO_CST = {
    "CST": 0,
    "SGT": 0,
    "HKT": 0,
    "PHT": 0,
    "AWST": 0,
    "CST+8": 0,
    "UTC": 8,
    "GMT": 8,
    "CEST": 6,
    "CET": 7,
    "EDT": 12,
    "EST": 13,
    "PDT": 15,
    "PST": 16,
    "MSK": 5,
}

DATE_RE = re.compile(
    r"\|date=\s*"
    r"(?:([A-Za-z]+)\s+(\d{1,2}),\s*(\d{4})|(\d{4})-(\d{2})-(\d{2}))"
    r"\s*[-–]\s*(\d{1,2}):(\d{2})"
    r"(?:\s*\{\{Abbr/([A-Za-z0-9+]+)\}\}|\s*([A-Z]{2,5}))?",
    re.I,
)
BESTOF_RE = re.compile(r"\|bestof\s*=\s*(\d+)", re.I)
MAP_RE = re.compile(r"\|map(\d+)\s*=\s*\{\{Map", re.I)
SLOT_RE = re.compile(r"\|(R\d+M\d+)\s*=\s*\{\{Match")


def fetch_wikitext() -> str:
    query = urllib.parse.urlencode(
        {
            "action": "parse",
            "page": PAGE,
            "prop": "wikitext",
            "format": "json",
        }
    )
    req = urllib.request.Request(API + "?" + query, headers=UA)
    with urllib.request.urlopen(req, timeout=45) as resp:
        raw = resp.read()
        enc = (resp.headers.get("Content-Encoding") or "").lower()
        if "gzip" in enc or raw[:2] == b"\x1f\x8b":
            raw = gzip.decompress(raw)
        data = json.loads(raw.decode("utf-8"))
    if data.get("error"):
        raise RuntimeError(data["error"])
    text = ((data.get("parse") or {}).get("wikitext") or {}).get("*") or ""
    if not text:
        raise RuntimeError("empty wikitext")
    return text


def match_blocks(wikitext: str) -> dict[str, str]:
    hits = list(SLOT_RE.finditer(wikitext))
    out: dict[str, str] = {}
    for i, hit in enumerate(hits):
        start = hit.end()
        end = hits[i + 1].start() if i + 1 < len(hits) else len(wikitext)
        out[hit.group(1)] = wikitext[start:end]
    return out


def parse_kickoff(raw: str) -> datetime | None:
    m = DATE_RE.search(raw or "")
    if not m:
        return None
    if m.group(1):
        month = MONTHS.get(m.group(1).lower())
        if not month:
            return None
        year, day = int(m.group(3)), int(m.group(2))
    else:
        year, month, day = int(m.group(4)), int(m.group(5)), int(m.group(6))
    hour, minute = int(m.group(7)), int(m.group(8))
    abbr = (m.group(9) or m.group(10) or "CST").upper()
    shift = TZ_TO_CST.get(abbr, 0)
    local = datetime(year, month, day, hour, minute)
    return local + timedelta(hours=shift)


def parse_format(body: str) -> str | None:
    best = BESTOF_RE.search(body)
    if best:
        n = int(best.group(1))
        return f"Bo{n}" if n in {1, 3, 5, 7} else None
    maps = {int(n) for n in MAP_RE.findall(body)}
    if maps and max(maps) >= 5:
        return "Bo5"
    if maps and max(maps) >= 3:
        return "Bo3"
    return None


def parse_bracket(wikitext: str) -> dict[str, dict]:
    """Return {our_id: {datetime, day, format?}} from Main Event wikitext."""
    out: dict[str, dict] = {}
    for lp_id, body in match_blocks(wikitext).items():
        ours = LP_TO_OURS.get(lp_id)
        if not ours:
            continue
        kickoff = parse_kickoff(body)
        if not kickoff:
            continue
        row: dict = {
            "lp": lp_id,
            "datetime": kickoff.strftime("%Y-%m-%d %H:%M"),
            "day": kickoff.strftime("%Y-%m-%d"),
        }
        fmt = parse_format(body)
        if fmt:
            row["format"] = fmt
        out[ours] = row
    return out


def rebuild_days(matches: list[dict], old_days: list[dict] | None) -> list[dict]:
    labels = {d.get("date"): d.get("label") for d in old_days or [] if d.get("date")}
    grouped: dict[str, list[dict]] = {}
    for m in matches:
        day = m.get("day") or str(m.get("datetime") or "")[:10]
        if len(day) != 10:
            continue
        grouped.setdefault(day, []).append(m)
    days = []
    for i, date in enumerate(sorted(grouped)):
        ordered = sorted(grouped[date], key=lambda m: m.get("datetime") or "")
        rounds: list[str] = []
        seen: set[str] = set()
        for m in ordered:
            r = m.get("round") or ""
            if r and r not in seen:
                seen.add(r)
                rounds.append(r)
        label = labels.get(date) or ("第{}天 · {}".format(i + 1, " + ".join(rounds) if rounds else "赛程"))
        days.append({"date": date, "label": label, "slots": [m["id"] for m in ordered]})
    return days


def apply_schedule(playoffs: dict, parsed: dict[str, dict], as_of: str) -> dict:
    matches = playoffs.get("matches") or []
    by_id = {m["id"]: m for m in matches}
    changed = []
    for mid, row in parsed.items():
        m = by_id.get(mid)
        if not m:
            continue
        before = (m.get("datetime"), m.get("day"), m.get("format"))
        m["datetime"] = row["datetime"]
        m["day"] = row["day"]
        if row.get("format"):
            m["format"] = row["format"]
        after = (m.get("datetime"), m.get("day"), m.get("format"))
        if before != after:
            changed.append(mid)
    playoffs["days"] = rebuild_days(matches, playoffs.get("days"))
    playoffs["scheduleAsOf"] = as_of
    playoffs["scheduleSource"] = PAGE_URL
    playoffs.pop("scheduleError", None)
    playoffs["note"] = (
        "对阵图按液体百科排好，后续场次队伍会随结果填入。"
        "开赛时间跟液体百科，主办方改点后这里跟着改。时间均为北京时间。"
    )
    return {"changed": changed, "parsed": sorted(parsed)}


def load_playoffs() -> dict:
    return json.loads((ROOT / "data" / "playoffs.json").read_text())


def save_playoffs(playoffs: dict) -> None:
    (ROOT / "data" / "playoffs.json").write_text(
        json.dumps(playoffs, ensure_ascii=False, indent=2) + "\n"
    )


def main() -> None:
    as_of = datetime.now(CST).strftime("%Y-%m-%d %H:%M") + " CST"
    playoffs = load_playoffs()
    try:
        wikitext = fetch_wikitext()
        parsed = parse_bracket(wikitext)
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, RuntimeError, json.JSONDecodeError) as e:
        playoffs["scheduleError"] = str(e)
        playoffs["scheduleAsOf"] = as_of
        save_playoffs(playoffs)
        print("schedule fetch failed; keeping last times:", e)
        return
    if len(parsed) < 8:
        playoffs["scheduleError"] = f"parsed {len(parsed)} slots"
        playoffs["scheduleAsOf"] = as_of
        save_playoffs(playoffs)
        print("schedule parse too thin", sorted(parsed))
        return
    info = apply_schedule(playoffs, parsed, as_of)
    save_playoffs(playoffs)
    times = {mid: parsed[mid]["datetime"] for mid in sorted(parsed)}
    print("schedule slots", len(parsed), "changed", info["changed"] or "none")
    for mid, dt in times.items():
        print(f"  {mid:6} {dt}")


if __name__ == "__main__":
    main()
