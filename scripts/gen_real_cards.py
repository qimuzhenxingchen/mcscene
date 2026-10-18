"""一次性脚本：用 2026-10-18 龙洞第二餐厅真实菜单快照 + MCP 真实核价，生成三张演示结果卡。

真实核价记录（calculate-price 返回，单位分）：
- 庆生 2人100元：9640 分 = ¥96.40（无券）
- 加班慰问 60元：5880 分 = ¥58.80（奶铁促销自动减 ¥7.10）
- 道歉 45元：   4490 分 = ¥44.90（无券）
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "skill" / "scripts"))

from mcsc_plan import Constraints, _load_items, build_plans, select_showcase  # noqa: E402
from mcsc_card import render_card  # noqa: E402
from mcsc_copyguard import check_copy  # noqa: E402

snapshot = ROOT / "skill" / "fixtures" / "meals.1400242.dinein.20261018.json"
pool, simulated = _load_items(str(snapshot))
assert not simulated, "快照应为真实数据"

STORE_NOTE = "麦当劳广州龙洞第二餐厅（龙洞购物中心首层）· 已用 MCP calculate-price 核价"
PRICE_NOTE = ("金额来自 2026-10-18 麦当劳 MCP calculate-price 实时核价；"
              "价格随门店与时段变动，下单前以当次核价为准。")

CASES = [
    {
        "out": "card-birthday.html",
        "occasion": "birthday",
        "relationship": "恋人",
        "budget": 100,
        "headcount": 2,
        "final": 96.40,
        "greeting": [
            "不知道说什么，就先给你点了一份你爱吃的 🍔",
            "今天不用赶时间，慢慢吃，我陪你 (´꒳`)♡",
            "吃完记得拍照给我看看呀 ✨",
        ],
    },
    {
        "out": "card-overtime.html",
        "occasion": "overtime",
        "relationship": "同事",
        "budget": 60,
        "headcount": 1,
        "final": 58.80,
        "discount_note": "麦咖啡奶铁促销：¥21.00 → ¥13.90，自动减 ¥7.10",
        "greeting": [
            "加班辛苦啦，加个餐 ☕",
            "咖啡趁热喝，别空着肚子硬撑 💪",
            "不用回消息，吃就行 🫡",
        ],
    },
    {
        "out": "card-apology.html",
        "occasion": "apology",
        "relationship": "朋友",
        "budget": 45,
        "headcount": 1,
        "final": 44.90,
        "greeting": [
            "上次是我没做好，这顿算我的 🙇",
            "不用说什么，吃完就好 (っ- ‸ - ς)",
            "以后我注意！麦旋风赔罪 🍦",
        ],
    },
]

for case in CASES:
    # 文案先过红线
    rel = {"恋人": "lover", "同事": "colleague", "朋友": "friend"}[case["relationship"]]
    rep = check_copy(" ".join(case["greeting"]), relationship=rel)
    if rep.blocked:
        raise SystemExit(f"{case['out']} 文案命中红线：\n{rep.summary()}")

    c = Constraints(budget=case["budget"], headcount=case["headcount"],
                    occasion=case["occasion"])
    plans = build_plans(pool, c)
    showcase = select_showcase(plans, c)

    # 真实核价：心意款用 calculate-price 的返回值，其余方案用预排价
    finals = {"心意款": case["final"]}

    note = PRICE_NOTE
    if case.get("discount_note"):
        note = case["discount_note"] + "。" + PRICE_NOTE
    page = render_card(
        occasion=case["occasion"],
        relationship=case["relationship"],
        headcount=case["headcount"],
        greeting_lines=case["greeting"],
        plans=showcase,
        store_note=STORE_NOTE,
        simulated=False,
        final_price_note=note,
        finals=finals,
    )
    out = ROOT / case["out"]
    out.write_text(page, encoding="utf-8")
    print(f"✓ {case['out']}  心意款核价 ¥{case['final']:.2f}  文案红线 PASS")
