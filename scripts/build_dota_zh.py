#!/usr/bin/env python3
"""Build data/dota-zh.json from Valve schinese datafeeds + CN player slang."""
from __future__ import annotations

import json
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "dota-zh.json"
UA = {"User-Agent": "TI15PlayoffAnalyzer/dota-zh"}

HERO_CALL = {
    1: "敌法",
    2: "斧王",
    3: "祸乱",
    4: "血魔",
    5: "冰女",
    6: "小黑",
    7: "小牛",
    8: "剑圣",
    9: "白虎",
    10: "水人",
    11: "影魔",
    12: "PL",
    13: "帕克",
    14: "屠夫",
    15: "剃刀",
    16: "沙王",
    17: "蓝猫",
    18: "流浪",
    19: "小小",
    20: "复仇",
    21: "风行",
    22: "宙斯",
    23: "船长",
    25: "火女",
    26: "莱恩",
    27: "小Y",
    28: "大鱼人",
    29: "潮汐",
    30: "巫医",
    31: "巫妖",
    32: "隐刺",
    33: "谜团",
    34: "TK",
    35: "火枪",
    36: "NEC",
    37: "术士",
    38: "兽王",
    39: "女王",
    40: "剧毒",
    41: "虚空",
    42: "骷髅王",
    43: "DP",
    44: "PA",
    45: "骨法",
    46: "TA",
    47: "毒龙",
    48: "月骑",
    49: "龙骑",
    50: "暗牧",
    51: "发条",
    52: "老鹿",
    53: "先知",
    54: "小狗",
    55: "黑贤",
    56: "小骷髅",
    57: "全能",
    58: "小鹿",
    59: "神灵",
    60: "夜魔",
    61: "蜘蛛",
    62: "赏金",
    63: "蚂蚁",
    64: "双头龙",
    65: "蝙蝠",
    66: "陈",
    67: "幽鬼",
    68: "冰魂",
    69: "末日",
    70: "拍拍",
    71: "白牛",
    72: "飞机",
    73: "炼金",
    74: "卡尔",
    75: "沉默",
    76: "黑鸟",
    77: "狼人",
    78: "熊猫",
    79: "毒狗",
    80: "德鲁伊",
    81: "CK",
    82: "米波",
    83: "大树",
    84: "蓝胖",
    85: "尸王",
    86: "拉比克",
    87: "萨尔",
    88: "小强",
    89: "小娜迦",
    90: "光法",
    91: "小精灵",
    92: "死灵龙",
    93: "小鱼人",
    94: "美杜莎",
    95: "巨魔",
    96: "人马",
    97: "猛犸",
    98: "伐木机",
    99: "刚背",
    100: "海民",
    101: "天怒",
    102: "亚巴顿",
    103: "大牛",
    104: "军团",
    105: "炸弹人",
    106: "火猫",
    107: "土猫",
    108: "孽主",
    109: "TB",
    110: "凤凰",
    111: "神谕",
    112: "冰龙",
    113: "电狗",
    114: "大圣",
    119: "小仙女",
    120: "滚滚",
    121: "墨客",
    123: "松鼠",
    126: "紫猫",
    128: "老奶奶",
    129: "玛尔斯",
    131: "百戏",
    135: "破晓",
    136: "玛西",
    137: "一护",
    138: "琼英",
    145: "凯",
    155: "朗戈",
}

ITEM_CALL = {
    "blink": "跳刀",
    "overwhelming_blink": "力量跳",
    "swift_blink": "敏捷跳",
    "arcane_blink": "智力跳",
    "moon_shard": "银月",
    "power_treads": "动力鞋",
    "phase_boots": "相位鞋",
    "arcane_boots": "秘法鞋",
    "tranquil_boots": "绿鞋",
    "travel_boots": "飞鞋",
    "travel_boots_2": "飞鞋",
    "boots": "草鞋",
    "hurricane_pike": "飓风长戟",
    "dragon_lance": "魔龙枪",
    "force_staff": "推推",
    "witch_blade": "巫师之刃",
    "devastator": "圣斧",
    "black_king_bar": "黑皇杖",
    "ultimate_scepter": "神杖",
    "aghanims_shard": "魔晶",
    "kaya_and_sange": "散慧",
    "sange_and_yasha": "散夜",
    "yasha_and_kaya": "慧夜",
    "kaya": "慧光",
    "sange": "散华",
    "yasha": "夜叉",
    "shivas_guard": "冰甲",
    "armlet": "臂章",
    "manta": "幻影斧",
    "desolator": "黯灭",
    "harpoon": "鱼叉",
    "soul_ring": "魂戒",
    "bracer": "护腕",
    "cyclone": "吹风",
    "sheepstick": "羊刀",
    "orchid": "紫怨",
    "bloodthorn": "血棘",
    "assault": "强袭",
    "heart": "龙心",
    "bfury": "狂战",
    "radiance": "辉耀",
    "butterfly": "蝴蝶",
    "greater_crit": "大炮",
    "lesser_crit": "小炮",
    "invis_sword": "隐刀",
    "silver_edge": "大隐刀",
    "basher": "晕锤",
    "abyssal_blade": "大晕锤",
    "mjollnir": "雷锤",
    "maelstrom": "漩涡",
    "skadi": "冰眼",
    "satanic": "撒旦",
    "mask_of_madness": "疯脸",
    "echo_sabre": "回音",
    "octarine_core": "玲珑心",
    "aether_lens": "以太",
    "glimmer_cape": "微光",
    "ghost": "绿杖",
    "ethereal_blade": "虚灵刀",
    "sphere": "林肯",
    "aeon_disk": "盘子",
    "refresher": "刷新",
    "bloodstone": "血精石",
    "pipe": "笛子",
    "crimson_guard": "赤红甲",
    "vanguard": "先锋盾",
    "blade_mail": "刃甲",
    "heavens_halberd": "天堂戟",
    "guardian_greaves": "大鞋",
    "mekansm": "梅肯",
    "urn_of_shadows": "骨灰",
    "spirit_vessel": "大骨灰",
    "hand_of_midas": "点金",
    "magic_wand": "魔杖",
    "magic_stick": "魔棒",
    "bottle": "瓶子",
    "tpscroll": "回城",
    "ward_observer": "真眼",
    "ward_sentry": "假眼",
    "dust": "粉",
    "smoke_of_deceit": "雾",
    "rapier": "圣剑",
    "monkey_king_bar": "金箍棒",
    "nullifier": "否决",
    "disperser": "散魂",
    "diffusal_blade": "散失",
    "gungir": "缚灵索",
    "phylactery": "灵匣",
    "angels_demise": "绝刃",
    "meteor_hammer": "陨星锤",
    "veil_of_discord": "纷争",
    "rod_of_atos": "阿托斯",
    "wind_waker": "大吹风",
    "lotus_orb": "莲花",
    "eternal_shroud": "法衣",
    "falcon_blade": "猎鹰",
    "mage_slayer": "法师克星",
    "enchanters_bauble": "附魔师之椟",
}

# OpenDota purchase_log key → Valve item name when they differ
KEY_ALIASES = {
    "parasma": "devastator",
    "scepter": "ultimate_scepter",
    "aghs": "ultimate_scepter",
    "aghanims_scepter": "ultimate_scepter",
    "bkb": "black_king_bar",
    "pike": "hurricane_pike",
    "treads": "power_treads",
    "phase": "phase_boots",
    "arcane": "arcane_boots",
    "shiva": "shivas_guard",
    "shivas": "shivas_guard",
    "manta_style": "manta",
}

DONT = [
    {"bad": "月圆", "use": "银月 / 银月之晶", "en": "Moon Shard", "why": "国服没有月圆这件装备"},
    {"bad": "巫妖刀", "use": "巫师之刃", "en": "Witch Blade", "why": "巫妖是英雄 Lich；这件装备是巫师之刃，升级成圣斧"},
    {"bad": "帕拉斯玛", "use": "圣斧", "en": "Parasma", "why": "客户端正式名是圣斧，不要音译英文"},
    {"bad": "用魔龙枪称呼飓风长戟", "use": "飓风长戟 / 大推推", "en": "Hurricane Pike", "why": "魔龙枪是 Dragon Lance，合成材料"},
    {"bad": "散夜称呼 Kaya and Sange", "use": "散慧 / 散慧对剑", "en": "Kaya and Sange", "why": "散夜是散华+夜叉；散慧是散华+慧光"},
    {"bad": "小精灵称呼 Hoodwink", "use": "松鼠 / 森海飞霞", "en": "Hoodwink", "why": "小精灵是艾欧 Io"},
    {"bad": "猛犸称呼玛尔斯或潮汐", "use": "玛尔斯；潮汐", "en": "Mars / Tidehunter", "why": "猛犸只等于马格纳斯 Magnus"},
    {"bad": "黑鸟称呼夜魔", "use": "夜魔 = 暗夜魔王；黑鸟 = 殁境神蚀者", "en": "Night Stalker vs Outworld Destroyer", "why": "Dota1 黑鸟是 OD，不是 NS"},
]


def get_json(url: str):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=45) as resp:
        return json.loads(resp.read().decode())


def main() -> None:
    heroes_raw = get_json("https://www.dota2.com/datafeed/herolist?language=schinese")
    items_raw = get_json("https://www.dota2.com/datafeed/itemlist?language=schinese")
    heroes = []
    for row in heroes_raw["result"]["data"]["heroes"]:
        hid = int(row["id"])
        npc = str(row["name"]).replace("npc_dota_hero_", "", 1)
        official = row["name_loc"]
        heroes.append(
            {
                "id": hid,
                "en": row["name_english_loc"],
                "npc": npc,
                "official": official,
                "call": HERO_CALL.get(hid) or official,
            }
        )
    items = []
    seen = set()
    for row in items_raw["result"]["data"]["itemabilities"]:
        name = str(row.get("name") or "")
        if not name.startswith("item_") or "recipe" in name:
            continue
        key = name.replace("item_", "", 1)
        if key in seen:
            continue
        seen.add(key)
        official = (row.get("name_loc") or "").strip()
        en = (row.get("name_english_loc") or "").strip()
        if not official or not en:
            continue
        items.append(
            {
                "key": key,
                "en": en,
                "official": official,
                "call": ITEM_CALL.get(key) or official,
            }
        )
    blob = {
        "asOf": "2026-09-07",
        "source": "Valve datafeed language=schinese + 国服玩家口头",
        "note": "写中文复盘只用 call 或 official。禁止英文直译、禁止自创译名。",
        "heroes": sorted(heroes, key=lambda h: h["id"]),
        "items": sorted(items, key=lambda it: it["key"]),
        "itemAliases": KEY_ALIASES,
        "dont": DONT,
    }
    OUT.write_text(json.dumps(blob, ensure_ascii=False, indent=2) + "\n")
    print("wrote", OUT, "heroes", len(heroes), "items", len(items))


if __name__ == "__main__":
    main()
