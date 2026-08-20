#!/usr/bin/env python3
"""Gold-lead label orientation: teamA lead is positive."""


def gold_lead_label(lead_a: float, tag_a: str, tag_b: str) -> str:
    v = round(lead_a or 0)
    mag = abs(v)
    if mag < 50:
        return "经济持平"
    lab = f"{mag / 1000:.1f}k" if mag >= 1000 else str(mag)
    who = tag_a if v > 0 else tag_b
    return f"{who} +{lab}"


def gold_bar_pct(lead_a: float) -> float:
    tilt = max(-0.42, min(0.42, (lead_a or 0) / 6000))
    return 50 + tilt * 50


def test_spirit_ahead_when_iw_is_left() -> None:
    # IW is teamA / dire, Spirit radiant_lead +1846 → leadA = -1846
    assert gold_lead_label(-1846, "IW", "Spirit") == "Spirit +1.8k"
    assert gold_lead_label(1846, "IW", "Spirit") == "IW +1.8k"
    assert gold_lead_label(0, "IW", "Spirit") == "经济持平"
    pct = gold_bar_pct(-1846)
    assert 30 < pct < 50
    assert gold_bar_pct(0) == 50


if __name__ == "__main__":
    test_spirit_ahead_when_iw_is_left()
    print("test_gold_lead ok")
