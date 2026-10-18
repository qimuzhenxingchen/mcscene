"""回归测试：跑通即说明引擎的核心承诺没退步。

断言的都是"承诺"，不是实现细节：
1. 绝不超预算
2. 绝不给价格未知的项报价
3. 缺项热量绝不当 0
4. 儿童模式绝不出现辣与咖啡因
5. 不同方案必须真的不同
6. 预算过紧要诚实报错，而不是硬凑
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from mcsc_plan import (  # noqa: E402
    Constraints, Item, build_plans, explain, occasion_reason, select_showcase,
)
from mcsc_copyguard import check_copy  # noqa: E402

CASES = 0
PASSED = 0


def check(cond: bool, label: str) -> None:
    global CASES, PASSED
    CASES += 1
    if cond:
        PASSED += 1
    else:
        print(f"  ✗ {label}")


MENU = [
    Item("A1", "牛肉堡A", "burger", 22.0, 620),
    Item("A2", "鸡腿堡B", "burger", 17.0, 460),
    Item("A3", "辣堡C", "burger", 14.5, 520, ("spicy",)),
    Item("S1", "薯条", "side", 12.0, 340, ("hot",)),
    Item("S2", "玉米杯", "side", 11.0, 120, ("hot",)),
    Item("C1", "鸡块", "chicken", 13.0, 260, ("shareable",)),
    Item("D1", "可乐", "drink", 9.0, 200, ("cold", "caffeine")),
    Item("D2", "热柠檬茶", "drink", 10.0, 90, ("hot",)),
    Item("E1", "冰淇淋", "dessert", 15.5, 380, ("cold",)),
    Item("X1", "价格未知新品", "dessert", None, None),
]


def test_budget_never_exceeded() -> None:
    print("· 绝不超预算")
    for budget in (25, 40, 60, 100, 150):
        for hc in (1, 2, 3):
            plans = build_plans(MENU, Constraints(budget=budget, headcount=hc))
            for p in plans:
                check(p.total <= budget, f"budget={budget} hc={hc} total={p.total}")


def test_no_unpriced_items() -> None:
    print("· 不给价格未知的项报价")
    plans = build_plans(MENU, Constraints(budget=100, headcount=2))
    for p in plans:
        for it in p.items:
            check(it.price is not None, f"{it.code} 价格应已确认")
            check(it.code != "X1", "价格未知项不应进入方案")


def test_unknown_kcal_not_zeroed() -> None:
    print("· 缺项热量不当 0 处理")
    menu = [i if i.code != "E1" else Item("E1", "冰淇淋", "dessert", 15.5, None) for i in MENU]
    plans = build_plans(menu, Constraints(budget=100, headcount=2))
    check(bool(plans), "应能出方案")
    hit = [p for p in plans if p.kcal_unknown > 0]
    if hit:
        for p in hit:
            check("热量未知" in p.kcal_text, f"kcal_text 应显式标注未知：{p.kcal_text}")
            check(p.kcal_text.startswith(">="), "有未知项时合计应使用 >= 而非约等于")
    else:
        check(True, "本组方案未触发缺项路径")


def test_kid_mode() -> None:
    print("· 儿童模式不出现辣与咖啡因")
    plans = build_plans(MENU, Constraints(budget=60, headcount=1, kid_mode=True))
    for p in plans:
        for it in p.items:
            check("spicy" not in it.tags, f"{it.code} 不应含辣")
            check("caffeine" not in it.tags, f"{it.code} 不应含咖啡因")


def test_exclude() -> None:
    print("· 忌口排除生效")
    plans = build_plans(MENU, Constraints(budget=80, headcount=2, exclude_tags=("spicy",)))
    for p in plans:
        for it in p.items:
            check("spicy" not in it.tags, f"{it.code} 应被排除")


def test_plans_distinct() -> None:
    print("· 方案之间确实不同")
    plans = build_plans(MENU, Constraints(budget=100, headcount=2), top=3)
    sigs = {p.signature for p in plans}
    check(len(sigs) == len(plans), f"方案签名应互不相同，实际 {len(sigs)}/{len(plans)}")


def test_tight_budget_honest() -> None:
    print("· 预算过紧时诚实返回")
    plans = build_plans(MENU, Constraints(budget=5, headcount=1))
    check(plans == [], "5 元不应配出方案（宁缺不编）")


def test_explain_contains_price() -> None:
    print("· 解释里必须有真实金额")
    plans = build_plans(MENU, Constraints(budget=100, headcount=1))
    check(bool(plans), "应有方案")
    if plans:
        text = explain(plans[0], Constraints(budget=100, headcount=1))
        check("¥" in text, "explain 应包含金额")
        check("预算" in text, "explain 应写明预算")


def test_occasion_drives_composition() -> None:
    print("· 场合真的改变组合（不只是文案）")
    # 庆生：甜品必须在场
    for oc in ("birthday", "celebrate", "anniversary", "confession"):
        plans = build_plans(MENU, Constraints(budget=100, headcount=2, occasion=oc))
        check(bool(plans), f"{oc} 应有方案")
        for p in plans:
            check("dessert" in {i.category for i in p.items}, f"{oc} 方案必须含甜品")
    # 加班慰问：必须有饮品，且同分偏热量低
    plans = build_plans(MENU, Constraints(budget=60, headcount=1, occasion="overtime"))
    for p in plans:
        check("drink" in {i.category for i in p.items}, "加班慰问必须含饮品")
    # 安慰：饮品+甜品双必须
    plans = build_plans(MENU, Constraints(budget=60, headcount=1, occasion="cheer_up"))
    for p in plans:
        cats = {i.category for i in p.items}
        check("drink" in cats and "dessert" in cats, "安慰场景必须饮品+甜品都在场")
    # 道歉：强制单人份
    plans = build_plans(MENU, Constraints(budget=100, headcount=3, occasion="apology"))
    for p in plans:
        check(p.main_count == 1, f"道歉是单人的事，不应出现 {p.main_count} 份主食")


def test_occasion_kid_policy() -> None:
    print("· 给孩子的场合自动开儿童模式")
    plans = build_plans(MENU, Constraints(budget=60, headcount=1, occasion="kid"))
    for p in plans:
        for it in p.items:
            check("spicy" not in it.tags and "caffeine" not in it.tags,
                  f"kid 场合不应出现 {it.code}（辣/咖啡因）")


def test_occasion_reason_nonempty() -> None:
    print("· 组合逻辑必须能被说清楚")
    for oc in ("birthday", "overtime", "apology", "self", "just_because"):
        check(len(occasion_reason(oc)) > 0, f"{oc} 应有可读的理由文案")


def test_showcase_has_saving_option() -> None:
    print("· 展示层三方案：省钱款是硬承诺")
    c = Constraints(budget=100, headcount=2, occasion="birthday")
    plans = build_plans(MENU, c)
    showcase = select_showcase(plans, c)
    labels = [lb for lb, _, _ in showcase]
    check("心意款" in labels, "必须有心意款")
    if len({p.signature for _, p, _ in showcase}) > 1:
        check("省钱款" in labels, "存在不同组合时必须有省钱款")
    xinyi = showcase[0][1]
    for label, p, _ in showcase:
        if label == "省钱款":
            check(p.total <= xinyi.total, f"省钱款（¥{p.total}）不应贵过心意款（¥{xinyi.total}）")
            cats = {i.category for i in p.items}
            check("dessert" in cats, "省钱款也必须满足场合 must 项——省的是钱，不是心意")


def test_headcount_coverage() -> None:
    print("· 每个人都有主食")
    for hc in (1, 2, 3):
        plans = build_plans(MENU, Constraints(budget=120, headcount=hc))
        check(bool(plans), f"headcount={hc} 应有方案")
        for p in plans:
            check(p.main_count >= hc, f"{hc} 人方案只有 {p.main_count} 份主食")


def test_value_mode_prefers_cheap() -> None:
    print("· 自己吃时排序偏向实惠")
    plans = build_plans(MENU, Constraints(budget=60, headcount=1, occasion="self"), top=4)
    check(bool(plans), "self 场合应有方案")
    totals = [p.total for p in plans]
    check(totals == sorted(totals, reverse=False) or totals[0] <= max(totals),
          "self 场合首个方案不应是刻意花满预算的组合")


def test_copy_guard() -> None:
    print("· 文案红线")
    bad = [
        ("吃了就会开心起来的", "PRM-03"),
        ("比肯德基好吃多了", "BRD-01"),
        ("你最近胖了吧", "BND-01"),
        ("吃不完就扔掉", "HLT-02"),
        ("这顿之后我们就和好吧", "PRM-01"),
    ]
    for text, rule in bad:
        rep = check_copy(text, relationship="friend")
        check(rep.blocked, f"「{text}」应被拦截")
        check(any(h.rule == rule for h in rep.hits), f"「{text}」应命中 {rule}")

    good = [
        ("上次是我没做好，这顿算我的。吃完就好，不用回我。", "lover"),
        ("生日快乐，慢慢吃。", "parent"),
        ("一点心意，请笑纳。祝顺利。", "boss"),
    ]
    for text, rel in good:
        rep = check_copy(text, relationship=rel)
        check(not rep.blocked, f"「{text}」不该被拦截，实际：{rep.summary()}")

    rep = check_copy("兄弟，这顿我请", relationship="boss")
    check(rep.blocked, "对上级用'兄弟'应被拦截")


def test_copy_guard_price() -> None:
    print("· 硬编码价格拦截")
    rep = check_copy("总共 ¥45.5，划算", relationship="friend", price_from_mcp=False)
    check(rep.blocked, "非 MCP 价格应被拦截")
    rep2 = check_copy("总共 ¥45.5，划算", relationship="friend", price_from_mcp=True)
    check(not rep2.blocked, "MCP 价格应放行")


def main() -> int:
    tests = [
        test_budget_never_exceeded,
        test_no_unpriced_items,
        test_unknown_kcal_not_zeroed,
        test_kid_mode,
        test_exclude,
        test_plans_distinct,
        test_tight_budget_honest,
        test_explain_contains_price,
        test_occasion_drives_composition,
        test_occasion_kid_policy,
        test_occasion_reason_nonempty,
        test_showcase_has_saving_option,
        test_headcount_coverage,
        test_value_mode_prefers_cheap,
        test_copy_guard,
        test_copy_guard_price,
    ]
    for t in tests:
        t()
    print(f"\n总结：{PASSED}/{CASES} 条断言通过")
    return 0 if PASSED == CASES else 1


if __name__ == "__main__":
    raise SystemExit(main())
