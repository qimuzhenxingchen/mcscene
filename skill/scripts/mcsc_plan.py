"""预算配餐引擎：把「场合」变成组合约束，而不只是文案前缀。

三条硬边界（写死，不开放）：
1. 价格只接受 MCP 的返回值；本模块自己不做定价。
2. 价格未知的项直接排除（宁可少一个方案，也不给算不准的价）。
3. 热量缺项标 UNKNOWN，合计改口 ">= N kcal"，绝不按 0 算。

排序哲学（对应评审/用户最常见的质疑）：
- 不再"把预算花满"优先。改为：先满足人数（每人有主食），再满足场合
  的必须项（如庆生必须有甜品），最后才看预算利用率。
- 展示层永远给三个有名字的方案：心意款 / 均衡款 / 省钱款。
  省钱款是硬保证——只要存在合规组合，就一定有一个最省的。
"""

from __future__ import annotations

from dataclasses import dataclass
from itertools import product
from typing import Iterable


# ---------- 数据模型 ----------

@dataclass(frozen=True)
class Item:
    """一个可点单品。code 必须是 MCP 返回的真实 productCode。"""
    code: str
    name: str
    category: str            # burger / side / drink / dessert / chicken / breakfast
    price: float | None      # None = 价格未知，本引擎会直接排除
    kcal: float | None = None
    tags: tuple[str, ...] = ()   # spicy / caffeine / cold / hot / shareable

    @property
    def priced(self) -> bool:
        return self.price is not None


@dataclass
class Plan:
    items: tuple[Item, ...]
    total: float
    kcal: float
    kcal_unknown: int = 0
    fit: int = 0             # 场合契合分，越高越贴合场合

    @property
    def kcal_text(self) -> str:
        if self.kcal_unknown == 0:
            return f"约 {self.kcal:.0f} kcal"
        return f">={self.kcal:.0f} kcal（其中 {self.kcal_unknown} 项热量未知，未计入）"

    @property
    def signature(self) -> tuple[str, ...]:
        return tuple(sorted(i.code for i in self.items))

    @property
    def main_count(self) -> int:
        return sum(1 for i in self.items if i.category in MAIN_CATS)


@dataclass
class Constraints:
    budget: float
    headcount: int = 1
    occasion: str = "just_because"
    exclude_tags: tuple[str, ...] = ()   # ('spicy',) = 不吃辣
    kid_mode: bool = False
    forbid: tuple[str, ...] = ()         # 不允许出现的 category


# ---------- 场合策略：让场合真的改变组合 ----------

# must        : 合规方案必须包含的 category（不满足直接淘汰）
# prefer      : 有这些 tag 的方案加分
# single_main : 强制单人份（道歉是一对一的事，摆一大桌反而像应付）
# light       : 同分时热量更低者优先（加班慰问别点太重）
# value       : 同分时总价更低者优先（自己吃没必要摆排场）
# kid         : 自动开儿童模式（排除辣与咖啡因）
OCCASION_POLICY: dict[str, dict] = {
    "birthday":     {"label": "庆生",     "must": ("dessert",), "prefer": ("shareable",)},
    "celebrate":    {"label": "庆祝",     "must": ("dessert",), "prefer": ("shareable",)},
    "anniversary":  {"label": "纪念日",   "must": ("dessert",)},
    "confession":   {"label": "表白",     "must": ("dessert",)},
    "proposal_soft": {"label": "求和好",  "must": ("dessert",)},
    "apology":      {"label": "道歉",     "must": ("dessert",), "single_main": True},
    "cheer_up":     {"label": "安慰",     "must": ("drink", "dessert"), "prefer": ("hot",)},
    "overtime":     {"label": "加班慰问", "must": ("drink",), "prefer": ("hot",), "light": True},
    "thanks":       {"label": "答谢",     "must": ()},
    "farewell":     {"label": "送别",     "must": ()},
    "kid":          {"label": "给孩子",   "must": ("dessert",), "kid": True},
    "self":         {"label": "自己吃",   "value": True},
    "just_because": {"label": "没理由",   "must": ()},
}

CATEGORY_ZH = {
    "burger": "汉堡", "breakfast": "早餐主食", "side": "小食", "drink": "饮品",
    "dessert": "甜品", "chicken": "小食",
}
TAG_ZH = {"shareable": "可分享", "hot": "热食/热饮"}

MAIN_CATS = ("burger", "breakfast")


def policy_of(occasion: str) -> dict:
    return OCCASION_POLICY.get(occasion, OCCASION_POLICY["just_because"])


def occasion_reason(occasion: str) -> str:
    """把场合策略翻译成人话，放在方案卡上，让'为什么这么配'可审计。"""
    p = policy_of(occasion)
    parts = []
    if p.get("must"):
        need = "、".join(CATEGORY_ZH.get(c, c) for c in p["must"])
        parts.append(f"{p['label']}场合，{need}是标配")
    if p.get("prefer"):
        want = "、".join(TAG_ZH.get(t, t) for t in p["prefer"])
        parts.append(f"优先{want}")
    if p.get("single_main"):
        parts.append("一对一的场合，不摆大桌")
    if p.get("light"):
        parts.append("慰问场景偏轻，不点太重")
    if p.get("value"):
        parts.append("自己吃，实惠优先")
    if p.get("kid"):
        parts.append("儿童模式：排除辣与含咖啡因")
    return "；".join(parts) if parts else "无特殊组合约束，按预算与口味排"


# ---------- 内部工具 ----------

def _allowed(item: Item, c: Constraints, pol: dict) -> bool:
    if item.price is None:
        return False
    if any(t in item.tags for t in c.exclude_tags):
        return False
    if (c.kid_mode or pol.get("kid")) and ("caffeine" in item.tags or "spicy" in item.tags):
        return False
    if c.forbid and item.category in c.forbid:
        return False
    return True


def _make_plan(items: Iterable[Item], fit: int = 0) -> Plan:
    its = tuple(items)
    return Plan(
        items=its,
        total=round(sum(i.price or 0 for i in its), 2),
        kcal=sum(i.kcal or 0 for i in its),
        kcal_unknown=sum(1 for i in its if i.kcal is None),
        fit=fit,
    )


def _fit_of(items: tuple[Item, ...], must: tuple[str, ...], prefer: tuple[str, ...],
            headcount: int) -> int:
    cats = {i.category for i in items}
    tags = {t for i in items for t in i.tags}
    mains = sum(1 for i in items if i.category in MAIN_CATS)
    return (2 * len([m for m in must if m in cats])
            + len([p for p in prefer if p in tags])
            + (1 if mains >= headcount else 0))


def _mains_for(headcount: int, mains_pool: list[Item]) -> list[list[Item]]:
    """几种主食选择策略：各不相同的 N 份 / 最便宜的 N 份 / 最贵的 N 份。"""
    n = max(1, min(headcount, 5))
    distinct: list[Item] = []
    for it in mains_pool:
        if it.code not in {x.code for x in distinct}:
            distinct.append(it)
        if len(distinct) >= n:
            break
    cheapest = sorted(mains_pool, key=lambda x: (x.price or 0))[:n]
    dearest = sorted(mains_pool, key=lambda x: -(x.price or 0))[:n]
    out = []
    seen: set[tuple[str, ...]] = set()
    for base in (distinct, cheapest, dearest):
        if base and len(base) >= n:
            sig = tuple(sorted(i.code for i in base))
            if sig not in seen:
                seen.add(sig)
                out.append(base)
    return out


# ---------- 主入口 ----------

def build_plans(
    items: Iterable[Item],
    c: Constraints,
    *,
    top: int = 6,
) -> list[Plan]:
    """返回按场合契合度排序的候选方案（去重后）。

    硬过滤：总价 <= 预算；场合 must 项全部在场；人数被主食覆盖。
    """
    pol = policy_of(c.occasion)
    if pol.get("single_main"):
        c.headcount = 1
    if pol.get("kid"):
        c.kid_mode = True
    must = tuple(pol.get("must", ()))
    prefer = tuple(pol.get("prefer", ()))

    pool = [i for i in items if _allowed(i, c, pol)]
    mains_pool = [i for i in pool if i.category in MAIN_CATS]
    companions = sorted([i for i in pool if i.category not in MAIN_CATS],
                        key=lambda x: -(x.price or 0))[:10]
    if not mains_pool:
        return []

    cands: dict[tuple[str, ...], Plan] = {}
    for base in _mains_for(c.headcount, mains_pool):
        base_cost = sum(i.price or 0 for i in base)
        if base_cost > c.budget:
            continue
        for r in range(0, min(4, len(companions) + 1)):
            for extra in product(companions, repeat=r):
                codes = [i.code for i in extra]
                if len(set(codes)) != len(codes):
                    continue
                if len(extra) >= 2 and len({i.category for i in extra}) < len(extra) - 1:
                    continue  # 配餐至少有点搭配感，不允许 3 杯可乐
                chosen = tuple(base) + extra
                plan = _make_plan(chosen)
                if plan.total > c.budget:
                    continue
                cats = {i.category for i in chosen}
                if any(m not in cats for m in must):
                    continue
                if plan.main_count < c.headcount:
                    continue
                plan.fit = _fit_of(chosen, must, prefer, c.headcount)
                cands.setdefault(plan.signature, plan)

    plans = sorted(cands.values(), key=lambda p: (
        -p.fit,
        p.total if pol.get("value") else -p.total,
        p.kcal if (pol.get("light") or pol.get("value")) else -p.kcal,
    ))
    return plans[:top]


def select_showcase(plans: list[Plan], c: Constraints) -> list[tuple[str, Plan, str]]:
    """从候选里挑三个有名字的方案：心意款 / 均衡款 / 省钱款。

    省钱款是硬承诺：只要候选非空，就一定有（除非与心意款同组合同价）。
    每个方案带一句"为什么"。
    """
    if not plans:
        return []
    pol = policy_of(c.occasion)
    must = tuple(pol.get("must", ()))

    def full_fit(p: Plan) -> bool:
        cats = {i.category for i in p.items}
        return all(m in cats for m in must) and p.main_count >= c.headcount

    xinyi = plans[0]
    picks: list[tuple[str, Plan, str]] = [("心意款", xinyi, occasion_reason(c.occasion))]

    qualified = [p for p in plans if full_fit(p)]
    if qualified:
        save = min(qualified, key=lambda p: (p.total, p.kcal))
        if save.signature != xinyi.signature:
            picks.append(("省钱款", save, "同样的场合要求，花最少的钱办到"))

        hi = max(p.total for p in qualified)
        lo = save.total
        mid = (hi + lo) / 2
        used = {xinyi.signature} | ({save.signature} if save.signature != xinyi.signature else set())
        bal_candidates = [p for p in qualified if p.signature not in used]
        if bal_candidates:
            bal = min(bal_candidates, key=lambda p: (abs(p.total - mid), p.kcal))
            picks.append(("均衡款", bal, "在心意和预算之间取中，覆盖两边诉求"))
    return picks


# ---------- 解释 ----------

def explain(plan: Plan, c: Constraints) -> str:
    left = c.budget - plan.total
    return f"合计 ¥{plan.total:.2f}（预算 ¥{c.budget:.0f}，剩 ¥{left:.2f}） · {plan.kcal_text}"


def tradeoff_text(a: Plan, b: Plan) -> str:
    d_price = round(b.total - a.total, 2)
    d_kcal = b.kcal - a.kcal
    if d_price == 0:
        return f"与心意款同价，热量 {d_kcal:+.0f} kcal"
    if d_price < 0:
        return f"比心意款省 ¥{abs(d_price):.2f}，热量 {d_kcal:+.0f} kcal"
    return f"比心意款多 ¥{d_price:.2f}，热量 {d_kcal:+.0f} kcal"


# ---------- CLI ----------

def _load_items(path: str) -> tuple[list[Item], bool]:
    import json
    import pathlib

    raw = json.loads(pathlib.Path(path).read_text(encoding="utf-8"))
    pool = [
        Item(
            code=i["code"],
            name=i["name"],
            category=i["category"],
            price=i.get("price"),
            kcal=i.get("kcal"),
            tags=tuple(i.get("tags", [])),
        )
        for i in raw.get("items", [])
    ]
    return pool, bool(raw.get("SIMULATED"))


def main() -> int:
    import argparse
    import sys

    ap = argparse.ArgumentParser(description="预算配餐引擎（价格必须来自 MCP calculate-price）")
    ap.add_argument("--items", required=True, help="菜单 JSON（MCP query-meals 结果或 fixtures）")
    ap.add_argument("--budget", type=float, required=True)
    ap.add_argument("--headcount", type=int, default=1)
    ap.add_argument("--occasion", default="just_because",
                    choices=sorted(OCCASION_POLICY), help="场合，影响组合约束")
    ap.add_argument("--exclude", default="", help="排除的 tags，逗号分隔，如 spicy")
    ap.add_argument("--top", type=int, default=6)
    args = ap.parse_args()

    pool, simulated = _load_items(args.items)
    if simulated:
        print("⚠ 使用 SIMULATED 演示数据，菜品与价格均为模拟，不可用于真实下单\n")

    c = Constraints(
        budget=args.budget,
        headcount=args.headcount,
        occasion=args.occasion,
        exclude_tags=tuple(t for t in args.exclude.split(",") if t),
    )
    print(f"场合「{policy_of(args.occasion)['label']}」的组合逻辑：{occasion_reason(args.occasion)}\n")

    plans = build_plans(pool, c, top=args.top)
    if not plans:
        cheapest = min((i.price or 0) for i in pool) if pool else 0
        print(f"这个预算（¥{args.budget:.0f}）配不出满足场合要求的组合；"
              f"本店最便宜单品 ¥{cheapest:.2f}")
        return 0

    showcase = select_showcase(plans, c)
    for label, p, why in showcase:
        names = " + ".join(f"{x.name} ¥{x.price:.2f}" for x in p.items)
        print(f"[{label}] {names}")
        print(f"        {explain(p, c)}")
        print(f"        为什么：{why}")

    if len(showcase) >= 2:
        base = showcase[0][1]
        print()
        for label, p, _ in showcase[1:]:
            print(f"        {label}对比：{tradeoff_text(base, p)}")
    print("\n注：本次为预排，最终金额以 calculate-price 返回为准。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
