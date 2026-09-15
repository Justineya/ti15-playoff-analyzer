#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import dota_zh  # noqa: E402


def test_hero_calls() -> None:
    assert dota_zh.hero_call(hero_id=76) == "黑鸟"
    assert dota_zh.hero_call(en="Outworld Destroyer") == "黑鸟"
    assert dota_zh.hero_call(npc="obsidian_destroyer") == "黑鸟"
    assert dota_zh.hero_call(en="Night Stalker") == "夜魔"
    assert dota_zh.hero_call(en="Hoodwink") == "松鼠"
    assert dota_zh.hero_call(en="Io") == "小精灵"
    assert dota_zh.hero_call(en="Magnus") == "猛犸"
    assert dota_zh.hero_call(en="Mars") == "玛尔斯"
    assert dota_zh.hero_call(en="Tidehunter") == "潮汐"
    assert dota_zh.hero_call(en="Death Prophet") == "DP"
    assert dota_zh.hero_call(en="Chaos Knight") == "CK"
    assert dota_zh.hero_call(en="Dawnbreaker") == "破晓"
    assert dota_zh.hero_call(en="Legion Commander") == "军团"
    assert dota_zh.hero_call(en="Keeper of the Light") == "光法"
    row = dota_zh._hero_row(en="Outworld Destroyer")
    assert row["official"] == "殁境神蚀者"
    assert dota_zh._hero_row(en="Hoodwink")["official"] == "森海飞霞"
    assert dota_zh._hero_row(en="Io")["official"] == "艾欧"
    assert dota_zh._hero_row(en="Magnus")["official"] == "马格纳斯"


def test_item_calls() -> None:
    assert dota_zh.item_call("moon_shard") == "银月"
    assert dota_zh.item_call("Moon Shard") == "银月"
    assert dota_zh.item_call("hurricane_pike") == "飓风长戟"
    assert dota_zh.item_call("dragon_lance") == "魔龙枪"
    assert dota_zh.item_call("witch_blade") == "巫师之刃"
    assert dota_zh.item_call("parasma") == "圣斧"
    assert dota_zh.item_call("devastator") == "圣斧"
    assert dota_zh.item_call("kaya_and_sange") == "散慧"
    assert dota_zh.item_call("sange_and_yasha") == "散夜"
    assert dota_zh.item_call("black_king_bar") == "黑皇杖"
    assert dota_zh.item_call("blink") == "跳刀"
    assert dota_zh.item_call("power_treads") == "动力鞋"
    items = {row["key"]: row for row in dota_zh.load()["items"]}
    assert items["moon_shard"]["official"] == "银月之晶"
    assert items["hurricane_pike"]["official"] == "飓风长戟"
    assert items["dragon_lance"]["official"] == "魔龙枪"
    assert items["witch_blade"]["official"] == "巫师之刃"
    assert items["devastator"]["official"] == "圣斧"
    assert items["kaya_and_sange"]["official"] == "散慧对剑"
    assert items["sange_and_yasha"]["official"] == "散夜对剑"


def test_traps_are_documented() -> None:
    bads = {row["bad"] for row in dota_zh.load()["dont"]}
    assert "月圆" in bads
    assert "巫妖刀" in bads
    assert any("魔龙枪" in row["bad"] for row in dota_zh.load()["dont"])
    assert any("猛犸" in row["bad"] for row in dota_zh.load()["dont"])


if __name__ == "__main__":
    test_hero_calls()
    test_item_calls()
    test_traps_are_documented()
    print("test_dota_zh ok")
