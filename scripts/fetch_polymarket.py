#!/usr/bin/env python3
"""Fetch latest Polymarket prices for TI15 playoff matchups."""
from __future__ import annotations

import json
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GAMMA = "https://gamma-api.polymarket.com"

TAGS = {
    "Iron Wing": ["iron wing", "ironwi", "1win", "tundra"],
    "Team Spirit": ["team spirit", "ts8", "spirit"],
    "TEAM VISION": ["vision", "vsn", "parivision", "pvision"],
    "BoomBoys": ["boombo", "boomboys", "betboom", "bb team"],
    "Team Liquid": ["liquid"],
    "Team Yandex": ["yandex"],
    "Nigma Galaxy": ["nigma", "ngx"],
    "Team Falcons": ["falcon", "flc"],
}


def get_json(url: str) -> object:
    req = urllib.request.Request(url, headers={"User-Agent": "ti15-analyzer/1.0"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode())


def parse_field(raw) -> list:
    if isinstance(raw, list):
        return raw
    if isinstance(raw, str):
        return json.loads(raw)
    return []


def normalize_market(market: dict) -> dict:
    outcomes = parse_field(market.get("outcomes"))
    prices = [str(x) for x in parse_field(market.get("outcomePrices") or market.get("prices"))]
    return {
        "question": market.get("question") or "",
        "outcomes": outcomes,
        "prices": prices,
    }


def fetch_event(slug: str) -> dict | None:
    url = GAMMA + "/events?" + urllib.parse.urlencode({"slug": slug})
    rows = get_json(url)
    if not rows:
        return None
    event = rows[0]
    return {
        "slug": event.get("slug") or slug,
        "title": event.get("title") or "",
        "volume": event.get("volume"),
        "markets": [normalize_market(m) for m in event.get("markets") or []],
    }


def name_hits(text: str, name: str) -> bool:
    t = text.lower()
    if name.lower() in t:
        return True
    return any(tag in t for tag in TAGS.get(name, []))


def search_slug(team_a: str, team_b: str) -> str | None:
    query = f"Dota 2 {team_a} {team_b} International Playoffs"
    url = GAMMA + "/public-search?" + urllib.parse.urlencode({"q": query, "limit_per_type": 25})
    try:
        data = get_json(url)
    except Exception as e:  # noqa: BLE001
        print("search failed", query, e)
        return None
    events = data.get("events") if isinstance(data, dict) else data
    if not isinstance(events, list):
        events = (data or {}).get("events") if isinstance(data, dict) else []
    best = None
    for ev in events or []:
        title = ev.get("title") or ""
        slug = ev.get("slug") or ""
        blob = f"{title} {slug}"
        if "dota" not in blob.lower():
            continue
        if name_hits(blob, team_a) and name_hits(blob, team_b):
            if "(BO3)" in title or "(BO5)" in title or "Playoffs" in title:
                return slug
            best = best or slug
    return best


def load_playoffs() -> dict:
    return json.loads((ROOT / "data" / "playoffs.json").read_text())


def ensure_slugs(playoffs: dict) -> list[str]:
    slugs = []
    seen = set()
    changed = False
    for match in playoffs.get("matches") or []:
        a, b = match.get("teamA"), match.get("teamB")
        slug = match.get("polySlug")
        if not slug and isinstance(a, str) and isinstance(b, str):
            slug = search_slug(a, b)
            if slug:
                match["polySlug"] = slug
                match["polyTitle"] = match.get("polyTitle") or f"{a} vs {b}"
                changed = True
                print("discovered slug", match["id"], slug)
        if slug and slug not in seen:
            seen.add(slug)
            slugs.append(slug)
    if changed:
        (ROOT / "data" / "playoffs.json").write_text(json.dumps(playoffs, ensure_ascii=False, indent=2) + "\n")
    return slugs


def slugs_from_snapshot() -> list[str]:
    path = ROOT / "data" / "polymarket-playoffs.json"
    if not path.exists():
        return []
    data = json.loads(path.read_text())
    return [e.get("slug") for e in data.get("events") or [] if e.get("slug")]


def main() -> None:
    playoffs = load_playoffs()
    slugs = ensure_slugs(playoffs) or slugs_from_snapshot()
    if not slugs:
        print("no polymarket slugs; writing empty snapshot")
        payload = {
            "asOf": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%MZ"),
            "source": GAMMA,
            "events": [],
        }
        (ROOT / "data" / "polymarket-playoffs.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2))
        return
    events = []
    for slug in slugs:
        print("fetch", slug)
        try:
            row = fetch_event(slug)
        except Exception as e:  # noqa: BLE001
            print("skip", slug, e)
            continue
        if row:
            events.append(row)
    payload = {
        "asOf": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%MZ"),
        "source": GAMMA,
        "events": events,
    }
    out = ROOT / "data" / "polymarket-playoffs.json"
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2))
    print("wrote", out, "events", len(events), "asOf", payload["asOf"])


if __name__ == "__main__":
    main()
