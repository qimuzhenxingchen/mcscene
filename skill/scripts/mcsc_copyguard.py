"""文案红线检测：把 docs/COPY-GUARD.md 变成可执行的检查。

设计原则：
- 只做"能确定的"判断。宁可漏报，不要误报打断用户。
- 每条命中都给出 rule_id、原文、以及一句人话的修改建议。
- 不依赖任何第三方库，纯标准库，可在离线环境跑通。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Iterable


@dataclass
class Hit:
    rule: str
    level: str          # "block" 必须改 / "warn" 建议改
    text: str
    advice: str


@dataclass
class Report:
    hits: list[Hit] = field(default_factory=list)

    @property
    def blocked(self) -> bool:
        return any(h.level == "block" for h in self.hits)

    def add(self, rule: str, level: str, text: str, advice: str) -> None:
        self.hits.append(Hit(rule=rule, level=level, text=text, advice=advice))

    def summary(self) -> str:
        if not self.hits:
            return "PASS：未命中任何红线"
        blocks = [h for h in self.hits if h.level == "block"]
        warns = [h for h in self.hits if h.level == "warn"]
        lines = [f"{'BLOCK' if blocks else 'PASS(with warn)'}：block {len(blocks)} 条 / warn {len(warns)} 条"]
        for h in self.hits:
            lines.append(f"  [{h.level.upper()}] {h.rule} :: 「{h.text}」 → {h.advice}")
        return "\n".join(lines)


# ---- 事实编造：具体年份/日期/数字断言 ----
FABRICATION_PATTERNS = [
    (re.compile(r"去年|前年|上个月|上个星期|上周[一二三四五六日天]"), "FAB-01", "block",
     "不要假设共同记忆，改成不带时间的事实描述"),
    (re.compile(r"连续\s*\d+\s*[天个]"), "FAB-02", "warn",
     "用户没给的数字不要自己算，改成「最近」"),
    (re.compile(r"第\s*\d+\s*[次年周天]"), "FAB-03", "block",
     "纪念日次数属于用户私有事实，不要编"),
    (re.compile(r"[（(]?\d{4}\s*[年]\s*\d{1,2}\s*[月]"), "FAB-04", "warn",
     "具体年月若不是用户给的，删掉"),
]

# ---- 超范围承诺：把食物说成关系解药或疗效 ----
PROMISE_PATTERNS = [
    (re.compile(r"就和好|一定原谅|肯定会原谅|担保"), "PRM-01", "block",
     "一顿饭不能承诺关系结果，改成表达心意不带条件"),
    (re.compile(r"治[疗愈好]|包治|药效|抗氧化|排毒|养生功效"), "PRM-02", "block",
     "不得暗示食品具有医疗或保健功效"),
    (re.compile(r"吃了就(会)?(开心|快乐|忘掉|不想)"), "PRM-03", "block",
     "不要承诺情绪效果"),
    (re.compile(r"保证.{0,6}(瘦|减|掉秤)"), "PRM-04", "block",
     "不得承诺减重效果"),
]

# ---- 不健康饮食 / 浪费 ----
HEALTH_PATTERNS = [
    (re.compile(r"扶墙|报复性(进食|消费|吃)|暴(食|吃)一?顿|热量刺客|罪恶感"), "HLT-01", "block",
     "删除暴食/罪恶感类表达，改为「点得刚好」"),
    (re.compile(r"吃不完(就)?[扔掉倒]|点满一桌|越多越有诚意"), "HLT-02", "block",
     "避免浪费倾向，强调按需点单"),
    (re.compile(r"通宵|熬夜到|不睡觉"), "HLT-03", "warn",
     "避免美化熬夜，改成「最近辛苦」"),
]

# ---- 品牌对比 / 贬损 ----
BRAND_PATTERNS = [
    (re.compile(r"肯德基|KFC|汉堡王|德克士|华莱士|必胜客", re.I), "BRD-01", "block",
     "不得出现其他餐饮品牌，删除对比"),
    (re.compile(r"比.{0,8}(好吃|便宜|值)多了"), "BRD-02", "block",
     "禁止品牌间比较"),
    (re.compile(r"垃圾食品|毒|不健康的东西"), "BRD-03", "block",
     "不得贬损自有产品"),
]

# ---- 人身边界 ----
BOUNDARY_PATTERNS = [
    (re.compile(r"胖了|胖成|减肥失败|该减肥|少吃点你"), "BND-01", "block",
     "禁止身材评价，删除这类句子"),
    (re.compile(r"(三十|四十|奔三|奔四|年纪不(小|轻)了)"), "BND-02", "warn",
     "避免年龄调侃，除非用户明确要求"),
    (re.compile(r"剩女|单身狗|没人要|结婚了吗|催婚"), "BND-03", "block",
     "禁止婚恋状况调侃"),
    (re.compile(r"你们(东北|南方|上海|北京|河南)人"), "BND-04", "block",
     "禁止地域刻板印象"),
    (re.compile(r"(男|女)的就(应该|该)"), "BND-05", "block",
     "禁止性别刻板印象"),
    (re.compile(r"抑郁症|焦虑症|病了|确诊"), "BND-06", "block",
     "不得推断或提及身心健康状况"),
]

# ---- 称呼不当（需结合关系判断） ----
INTIMATE = re.compile(r"宝贝|宝子|亲爱的|老婆|老公|老铁|兄弟|集美|家人们")
FORMAL_RELATIONSHIPS = {"boss", "client", "colleague", "team"}

# ---- 硬编码价格（数字 + 元） ----
PRICE_PATTERN = re.compile(r"[¥￥]\s*\d+(\.\d{1,2})?|\d+(\.\d{1,2})?\s*元")

# ---- emoji / 颜文字纪律 ----
EMOJI_RE = re.compile(
    "[\U0001F300-\U0001FAFF\U00002700-\U000027BF\U0001F000-\U0001F0FF\u2600-\u26FF\uFE0F♡✨]"
)
KAOMOJI_RE = re.compile(r"[（(][^()（）\n]{1,12}[)）]\s*[♡✧☆｀´ﾉ丿]?")


def emoji_discipline(text: str, relationship: str, report: Report) -> None:
    """emoji 每句至多一个（超过按 warn）；颜文字对正式关系直接拦截。"""
    lines = [ln for ln in re.split(r"[。！？\n]", text) if ln.strip()]
    total = len(EMOJI_RE.findall(text))
    if total > max(len(lines), 1):
        report.add("EMO-01", "warn", f"全文 {total} 个 emoji / {len(lines)} 句",
                   "emoji 每句最多一个，多余的删掉")
    if relationship in FORMAL_RELATIONSHIPS and KAOMOJI_RE.search(text):
        report.add("CAL-02", "block", KAOMOJI_RE.search(text).group(0),
                   "对上级/客户/同事不要用颜文字")


ALL_RULES: list[tuple[re.Pattern, str, str, str]] = (
    FABRICATION_PATTERNS + PROMISE_PATTERNS + HEALTH_PATTERNS + BRAND_PATTERNS + BOUNDARY_PATTERNS
)


def check_copy(text: str, relationship: str = "", price_from_mcp: bool = True) -> Report:
    """检查一段生成的文案。

    relationship: lover / parent / boss / client ... 用于称呼判断
    price_from_mcp: 文案里的价格是否来自 calculate-price 的真实返回
    """
    report = Report()
    if not text:
        return report

    for pattern, rule, level, advice in ALL_RULES:
        for m in pattern.finditer(text):
            report.add(rule, level, m.group(0), advice)

    if relationship in FORMAL_RELATIONSHIPS:
        for m in INTIMATE.finditer(text):
            report.add("CAL-01", "block", m.group(0), "对上级/客户/同事不要用亲昵称呼")

    emoji_discipline(text, relationship, report)

    if not price_from_mcp:
        for m in PRICE_PATTERN.finditer(text):
            report.add("PRC-01", "block", m.group(0), "价格必须来自 calculate-price 实时返回，禁止硬编码")

    return report


def check_many(texts: Iterable[str], **kw) -> Report:
    merged = Report()
    for t in texts:
        r = check_copy(t, **kw)
        merged.hits.extend(r.hits)
    return merged


if __name__ == "__main__":
    import sys

    sample = sys.argv[1] if len(sys.argv) > 1 else ""
    if not sample:
        samples = [
            ("生日快乐！吃了就会开心起来的，比肯德基好吃多了", "friend", True),
            ("上次是我没做好，这顿算我的。吃完就好，不用回我。", "lover", True),
            ("", "parent", True),
        ]
        for t, rel, pm in samples:
            print(f"--- {rel} :: {t!r}")
            print(check_copy(t, rel, pm).summary())
    else:
        print(check_copy(sample).summary())
