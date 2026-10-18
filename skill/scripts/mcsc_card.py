"""结果卡生成器：把配餐方案 + 心意卡渲染成一张可截图/可分享的单文件 HTML。

设计约束：
- 单文件、内联样式、无外部资源、手机宽度友好——截图直接能发朋友圈。
- 数据来源是演示（SIMULATED）还是真实核价（MCP），必须在卡上写明白，不能混。
- 不做营销排版，信息密度优先：钱、热量、为什么这么配，一眼看到。
- 视觉：暖色小票风 + 书信风祝福卡。金色渐变头图，虚线价格引导线，
  三款方案各有专属色标（心意橙 / 均衡蓝 / 省钱绿）。
"""

from __future__ import annotations

import html
import json
import pathlib
import sys
from typing import Optional

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from mcsc_plan import (  # noqa: E402
    Constraints, Plan, _load_items, build_plans, explain, occasion_reason,
    policy_of, select_showcase, tradeoff_text,
)

OCCASION_EMOJI = {
    "birthday": "🎂", "celebrate": "🎉", "anniversary": "💞", "confession": "💌",
    "proposal_soft": "🌷", "apology": "🙇", "cheer_up": "🫂", "overtime": "🌙",
    "thanks": "🙏", "farewell": "🍂", "kid": "🎈", "self": "✨", "just_because": "🌻",
}

_CSS = """
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: -apple-system, "PingFang SC", "Microsoft YaHei", sans-serif;
       background: #f3ede1;
       background-image: radial-gradient(#e8dfcd 1px, transparent 1px);
       background-size: 18px 18px;
       color: #33281e; padding: 14px; max-width: 400px; margin: 0 auto; }

.hero { position: relative; border-radius: 18px 18px 14px 14px; overflow: hidden;
        background: linear-gradient(135deg, #ffd75e 0%, #ffab2e 60%, #ff9024 100%);
        padding: 20px 18px 16px; color: #4a2c00;
        box-shadow: 0 4px 14px rgba(217,119,6,.25); }
.hero .emoji { font-size: 34px; line-height: 1; }
.hero h1 { font-size: 22px; margin: 6px 0 2px; letter-spacing: 1px; }
.chips { margin-top: 10px; display: flex; flex-wrap: wrap; gap: 6px; }
.chip { background: rgba(255,255,255,.75); color: #7a4a00; font-size: 12px;
        padding: 3px 10px; border-radius: 20px; font-weight: 600; }

.greeting { position: relative; background: #fffdf8; border-radius: 14px;
            padding: 18px 16px 14px; margin: 12px 0;
            border: 1px solid #f0e2c8; }
.greeting::before { content: "\\201C"; position: absolute; top: -2px; left: 10px;
            font-size: 52px; color: #ffd75e; font-family: Georgia, serif;
            line-height: 1; }
.greeting .line { font-size: 15px; line-height: 1.9; padding-left: 26px; }
.greeting .line + .line { margin-top: 2px; }

.plan-tab { display: inline-flex; align-items: center; gap: 5px; font-size: 12px;
            font-weight: 800; color: #fff; border-radius: 8px 8px 8px 2px;
            padding: 4px 12px; letter-spacing: 2px; }
.tab-xinyi { background: linear-gradient(135deg, #ff8a3d, #e8590c); }
.tab-bal    { background: linear-gradient(135deg, #4dabf7, #1971c2); }
.tab-save   { background: linear-gradient(135deg, #51cf66, #2f9e44); }

.card { background: #fffdf8; border-radius: 14px; padding: 16px;
        margin: 12px 0; box-shadow: 0 2px 8px rgba(90,60,20,.08); }

ul.items { list-style: none; margin-top: 10px; }
ul.items li { display: flex; align-items: baseline; font-size: 14px; padding: 6px 0; }
ul.items .name { color: #3d3225; }
ul.items .dots { flex: 1; border-bottom: 2px dotted #e5d9c3; margin: 0 8px 4px; }
ul.items .price { font-weight: 700; font-variant-numeric: tabular-nums; }

.total { display: flex; align-items: baseline; margin-top: 10px; padding-top: 10px;
         border-top: 2px dashed #eadfc8; }
.total .label { font-size: 13px; color: #8a7a60; }
.total .amount { margin-left: auto; font-size: 22px; font-weight: 800;
                 font-variant-numeric: tabular-nums; }
.save-chip { margin-left: auto; font-size: 11px; font-weight: 700; color: #2f9e44;
             background: #e6f7eb; border-radius: 12px; padding: 2px 8px; }
.total .amount.with-chip { margin-left: 8px; }

.meta { display: flex; align-items: flex-start; gap: 6px; font-size: 12px;
        color: #8a7a60; margin-top: 8px; line-height: 1.6; }
.why { font-size: 12px; color: #a08c6a; margin-top: 8px; padding: 8px 10px;
       background: #faf5e9; border-radius: 8px; line-height: 1.6; }
.compare { font-size: 12px; color: #8a7a60; margin: 2px 4px 12px; line-height: 1.7; }

.footer { text-align: center; font-size: 11px; color: #a89a80; margin: 16px 0 8px;
          line-height: 1.8; }
.divider { text-align: center; font-size: 12px; letter-spacing: 8px; margin: 2px 0;
           color: #d4b96a; }
"""


def _esc(s: str) -> str:
    return html.escape(s, quote=True)


def _plan_block(label: str, plan: Plan, why: str, final: Optional[float] = None) -> str:
    tab_cls = {"心意款": "tab-xinyi", "均衡款": "tab-bal", "省钱款": "tab-save"}.get(label, "tab-xinyi")
    tab_icon = {"心意款": "💝", "均衡款": "⚖️", "省钱款": "🪙"}.get(label, "💝")
    rows = "".join(
        f'<li><span class="name">{_esc(i.name)}</span>'
        f'<span class="dots"></span><span class="price">¥{i.price:.2f}</span></li>'
        for i in plan.items
    )
    amount = f"¥{final:.2f}" if final is not None else f"¥{plan.total:.2f}"
    chip = ""
    amount_cls = "amount"
    if final is not None and plan.total - final > 0.005:
        chip = f'<span class="save-chip">自动省 ¥{plan.total - final:.2f}</span>'
        amount_cls = "amount with-chip"
    return f"""
<div class="card">
  <span class="plan-tab {tab_cls}">{tab_icon} {label}</span>
  <ul class="items">{rows}</ul>
  <div class="total"><span class="label">小计</span>{chip}
    <span class="{amount_cls}">{amount}</span></div>
  <div class="meta">🔥 {_esc(plan.kcal_text)}</div>
  <div class="why">💡 {_esc(why)}</div>
</div>"""


def render_card(
    occasion: str,
    relationship: str,
    headcount: int,
    greeting_lines: list[str],
    plans: list[tuple[str, Plan, str]],
    store_note: str,
    simulated: bool = True,
    final_price_note: str = "",
    finals: Optional[dict] = None,
) -> str:
    """渲染一张完整的结果卡 HTML。

    greeting_lines: 心意卡文案（3 段）。调用前应已过 mcsc_copyguard。
    plans: select_showcase 的返回。
    finals: {label: 最终核价金额}。给了就用真实核价展示，并自动算"自动省"。
    store_note: 门店说明（真实场景是"已选门店名"，演示场景标注模拟）。
    """
    pol = policy_of(occasion)
    emoji = OCCASION_EMOJI.get(occasion, "🌻")
    badge_cls = "real" if not simulated else "sim"
    badge_txt = "✓ 已用 MCP 实时核价" if not simulated else "SIMULATED 演示数据"
    greet = "".join(f'<div class="line">{_esc(line)}</div>' for line in greeting_lines)
    finals = finals or {}
    plan_html = "".join(
        _plan_block(label, p, why, finals.get(label))
        for label, p, why in plans
    )
    price_note = final_price_note or "最终金额以 calculate-price 实时返回为准，下单前需你确认。"

    compare = ""
    if len(plans) >= 2:
        base = plans[0][1]
        lines = [f"{label}：{tradeoff_text(base, p)}" for label, p, _ in plans[1:]]
        compare = f'<div class="compare">↔ {"；".join(_esc(x) for x in lines)}</div>'

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>麦事 · {_esc(pol["label"])}结果卡</title>
<style>{_CSS}</style>
</head>
<body>

<div class="hero">
  <span class="badge {badge_cls}">{badge_txt}</span>
  <div class="emoji">{emoji}</div>
  <h1>麦事 · {_esc(pol["label"])}</h1>
  <div class="chips">
    <span class="chip">💌 给{_esc(relationship)}</span>
    <span class="chip">👥 {_esc(str(headcount))} 人份</span>
  </div>
</div>

<div class="greeting">{greet}</div>
<div class="divider">🍟 🍟 🍟</div>
{plan_html}
{compare}

<div class="card">
  <div class="meta">📍 {_esc(store_note)}</div>
  <div class="meta">🧾 {_esc(price_note)}</div>
</div>

<div class="footer">
  本卡由 mcscene 生成 · 非麦当劳官方产品<br>
  支付永远由你自己完成
</div>
</body>
</html>"""


def demo() -> str:
    """用 SIMULATED 夹具数据渲染一张演示卡（不配 Token 也能看）。"""
    items, simulated = _load_items(
        str(pathlib.Path(__file__).resolve().parents[1] / "fixtures" / "meals.sample.json")
    )
    c = Constraints(budget=100, headcount=2, occasion="birthday")
    plans_pool = build_plans(items, c)
    showcase = select_showcase(plans_pool, c)
    greeting = [
        "不知道说什么，就先给你点了一份你爱吃的。",
        "今天不用赶时间，慢慢吃。",
        "吃完记得拍照给我看。",
    ]
    return render_card(
        occasion="birthday",
        relationship="恋人",
        headcount=2,
        greeting_lines=greeting,
        plans=showcase,
        store_note="门店由你选择（演示卡为模拟门店）",
        simulated=True,
    )


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser(description="生成可分享的结果卡 HTML")
    ap.add_argument("--out", default="result-card.html", help="输出路径")
    ap.add_argument("--demo", action="store_true", help="用 SIMULATED 数据出演示卡")
    args = ap.parse_args()

    page = demo()  # 真实卡由 SKILL.md 工作流在 S3 核价后调用 render_card 生成
    pathlib.Path(args.out).write_text(page, encoding="utf-8")
    print(f"已生成：{pathlib.Path(args.out).resolve()}")
