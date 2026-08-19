#!/usr/bin/env python3
"""T1 majors in the six months before TI15: catalog, recency weights, rename map.

Newer events sit closer to EWC's 0.45; older ones decay with a 75-day half-life.
Draft / F10K stay on the current patch (TI + EWC). Majors only move team WR and H2H.
"""
from __future__ import annotations

from datetime import date

TI_REF = date(2026, 8, 13)
EWC_WEIGHT = 0.45
EWC_ANCHOR_DAYS = 30
HALF_LIFE_DAYS = 75

# OpenDota league ids. BLAST Slam VI (Feb 3–15) is outside the ~6 month window.
MAJORS = [
    {
        "id": "dl28",
        "name": "DreamLeague Season 28",
        "leagueId": 19269,
        "start": "2026-02-16",
        "end": "2026-03-01",
        "winner": "Iron Wing",
        "winnerAs": "Tundra Esports",
    },
    {
        "id": "pgl7",
        "name": "PGL Wallachia Season 7",
        "leagueId": 19435,
        "start": "2026-03-07",
        "end": "2026-03-15",
        "winner": "Team Yandex",
        "winnerAs": "Team Yandex",
    },
    {
        "id": "esl-birm",
        "name": "ESL One Birmingham 2026",
        "leagueId": 19422,
        "start": "2026-03-22",
        "end": "2026-03-29",
        "winner": "Iron Wing",
        "winnerAs": "Tundra Esports",
    },
    {
        "id": "pgl8",
        "name": "PGL Wallachia Season 8",
        "leagueId": 19543,
        "start": "2026-04-18",
        "end": "2026-04-26",
        "winner": "BoomBoys",
        "winnerAs": "BetBoom Team",
    },
    {
        "id": "dl29",
        "name": "DreamLeague Season 29",
        "leagueId": 19696,
        "start": "2026-05-13",
        "end": "2026-05-24",
        "winner": "TEAM VISION",
        "winnerAs": "PARIVISION",
    },
    {
        "id": "blast7",
        "name": "BLAST Slam VII",
        "leagueId": 19101,
        "start": "2026-05-26",
        "end": "2026-06-07",
        "winner": "Team Yandex",
        "winnerAs": "Team Yandex",
    },
]

# Org ids seen in these leagues → canonical playoff name (roster still has to match).
TEAM_IDS = {
    9572001: "TEAM VISION",  # PARIVISION / TEAM VISION
    9824702: "TEAM VISION",  # PVISION at BLAST / EWC
    8255888: "BoomBoys",  # BetBoom Team
    8291895: "Iron Wing",  # Tundra Esports
    10182357: "Iron Wing",  # 1w
    10150413: "Iron Wing",
    2163: "Team Liquid",
    7119388: "Team Spirit",
    9247354: "Team Falcons",
    9823272: "Team Yandex",
    10136357: "Nigma Galaxy",
    7554697: "Nigma Galaxy",  # older org id; dropped unless TI roster is on the map
}

# TI15 playoff five. A side maps to that team only with ≥ ROSTER_MIN of these accounts.
ROSTERS = {
    "TEAM VISION": {1044002267, 106573901, 195108598, 164199202, 73401082},
    "Team Liquid": {152962063, 201358612, 97590558, 77490514, 16497807},
    "Nigma Galaxy": {111620041, 210053851, 138880576, 152168157, 101356886},
    "Team Spirit": {321580662, 106305042, 302214028, 218231587, 847565596},
    "Iron Wing": {331855530, 93618577, 86698277, 346412363, 136829091},
    "Team Falcons": {100058342, 898455820, 183719386, 25907144, 10366616},
    "BoomBoys": {172099728, 480412663, 165564598, 317880638, 196878136},
    "Team Yandex": {171262902, 312436974, 56351509, 103735745, 93817671},
}
ROSTER_MIN = 4
EIGHT = list(ROSTERS)
# If OpenDota omitted player rows, still trust these orgs. NGX changed cores — never by id alone.
TRUST_ORG_IF_NO_PLAYERS = {
    "TEAM VISION",
    "BoomBoys",
    "Iron Wing",
    "Team Liquid",
    "Team Spirit",
    "Team Falcons",
    "Team Yandex",
}


def recency_weight(end: date | str, *, ti_ref: date = TI_REF) -> float:
    """Weight vs TI=1.0 / EWC≈0.45. Older end dates decay; floor 0.10."""
    if isinstance(end, str):
        end = date.fromisoformat(end[:10])
    days = (ti_ref - end).days
    if days <= 0:
        return 1.0
    raw = EWC_WEIGHT * (0.5 ** ((days - EWC_ANCHOR_DAYS) / HALF_LIFE_DAYS))
    return round(min(1.0, max(0.10, raw)), 2)


def majors_with_weights() -> list[dict]:
    out = []
    for row in MAJORS:
        item = dict(row)
        item["weight"] = recency_weight(row["end"])
        out.append(item)
    return out


def league_by_id() -> dict[int, dict]:
    return {int(m["leagueId"]): m for m in majors_with_weights()}


def all_player_ids() -> set[int]:
    ids: set[int] = set()
    for group in ROSTERS.values():
        ids |= group
    return ids


def overlap_count(account_ids: set[int], team: str) -> int:
    return len(account_ids & ROSTERS[team])


def canonical_side(account_ids: set[int], opendota_name: str | None, team_id: int | None = None) -> str:
    """Map a side to a playoff team only when the TI roster is actually on it."""
    best, best_n = None, 0
    for team in EIGHT:
        n = overlap_count(account_ids, team)
        if n > best_n:
            best, best_n = team, n
    if best is not None and best_n >= ROSTER_MIN:
        return best
    org = TEAM_IDS.get(int(team_id)) if team_id else None
    if best_n == 0 and org in TRUST_ORG_IF_NO_PLAYERS:
        return org
    hint = (opendota_name or "").strip() or org or ""
    if hint in ROSTERS:
        return f"{hint}（旧阵容）"
    if hint:
        return hint
    if team_id:
        return f"team-{int(team_id)}"
    return "Unknown"
