#!/usr/bin/env python3
"""国服英雄/物品中文名。写复盘只准用这里的 call 或 official。"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = ROOT / "data" / "dota-zh.json"

_blob: dict | None = None
_hero_index: dict[str, dict] | None = None
_item_index: dict[str, dict] | None = None


def load() -> dict:
    global _blob, _hero_index, _item_index
    if _blob is not None:
        return _blob
    _blob = json.loads(DATA_PATH.read_text())
    _hero_index = {}
    for row in _blob.get("heroes") or []:
        for key in (row.get("id"), row.get("en"), row.get("npc"), row.get("official"), row.get("call")):
            if key is None or key == "":
                continue
            _hero_index[str(key).strip().lower()] = row
    _item_index = {}
    for row in _blob.get("items") or []:
        for key in (row.get("key"), row.get("en"), row.get("official"), row.get("call")):
            if key:
                _item_index[str(key).strip().lower()] = row
    aliases = _blob.get("itemAliases") or {}
    for alias, target in aliases.items():
        src = _item_index.get(str(target).strip().lower())
        if src:
            _item_index[str(alias).strip().lower()] = src
    return _blob


def _hero_row(*, hero_id=None, en=None, npc=None) -> dict | None:
    load()
    assert _hero_index is not None
    for key in (hero_id, npc, en):
        if key is None or key == "":
            continue
        row = _hero_index.get(str(key).strip().lower())
        if row:
            return row
    return None


def hero_call(*, hero_id=None, en=None, npc=None, fallback: str | None = None) -> str:
    row = _hero_row(hero_id=hero_id, en=en, npc=npc)
    if not row:
        return fallback or en or npc or (str(hero_id) if hero_id is not None else "")
    return row.get("call") or row.get("official") or fallback or ""


def item_call(key: str | None, fallback: str | None = None) -> str:
    load()
    assert _item_index is not None
    if not key:
        return fallback or ""
    row = _item_index.get(str(key).strip().lower())
    if not row:
        return fallback or str(key)
    return row.get("call") or row.get("official") or fallback or str(key)
