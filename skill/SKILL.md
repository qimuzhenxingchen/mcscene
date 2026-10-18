---
name: mcscene
description: 用一句话把"要给谁、花多少钱、为什么请"变成一份可执行的麦当劳配餐方案——包含按对象调语气的祝福卡、预算内实时核价的套餐组合、以及必须用户确认才下单的安全闸门。当用户说"帮我给谁点麦当劳""生日/道歉/纪念日/加班慰问想请他吃饭""预算 100 配一桌""写个祝福语配餐"时使用。不用于单纯查菜单、查券、查门店。
---

# 麦事 mcscene

把"心意"翻译成一单能下得去的手的麦当劳。

## 它不做什么（先说清楚，避免误用）

- 不做单纯的菜单查询、优惠券查询、订单查询 —— 那些直接用麦当劳 MCP 就够了，不需要这个 Skill。
- 不做营养/医疗建议。热量只做量级参考，且明确标注数据可能缺失。
- 不替用户付款。**任何情况下都不自动调用 `create-order`**，必须由用户在看到金额后逐字确认。

## 输入：一句话就够

用户通常只说一句话，例如：

- 「女朋友这周日生日，预算 100，想有点仪式感」
- 「跟同事闹僵了，想请他吃个午饭缓和一下，50 块以内」
- 「我爸不爱吃辣的，一百块，随便点」

从这句话里抽取四个槽位（缺的可以追问，但**最多问两个问题**）：

| 槽位 | 说明 | 缺省值 |
|---|---|---|
| relationship | lover / spouse / parent / child / friend / colleague / boss / client / self / team | 追问 |
| occasion | birthday / anniversary / apology / thanks / cheer_up / overtime / celebrate / confession / farewell / just_because | `just_because` |
| budget | 总预算（元） | 追问 |
| constraints | 忌口、辣度、人数、店内还是外送 | 人数 1，口味不限 |

## 工作流

### S0 补齐场景（无网络）
读 `data/personas.json`，按 relationship + occasion 推出 tone（语气）。
若 `tone_switch_rules` 命中，以规则为准。把推出来的 tone 和理由用一句话告诉用户，让他有机会推翻——**语气判断错了，后面全白做**。

**场合同时决定组合，不只是文案**（见 S2）。`occasion` 判定出来后要传给配餐引擎，不能只用在 S4。

### S1 摸清现实（调 MCP）

严格按这个顺序，不要跳步：

1. `now-time-info` → 拿到当前时间。判断餐段（早餐 / 正餐 / 下午茶 / 夜宵）。
2. `query-nearby-stores`（到店）或 `delivery-query-addresses` + `delivery-query-stores`（外送）→ 拿 `storeCode` / `beCode`，**必须让用户确认门店**，不要自己猜。
3. `query-meals` → 当次实时菜单。记住：`query-meals` 没有 `daypart` 参数，要查某个餐段就传 `reservationDate` 为该餐段的代表时刻。
4. `query-store-coupons` → 只做**标注**（哪些券能用、能减多少），不要擅自用券改变用户预算。

把菜单里可用的单品（含套餐）灌进 `scripts/mcsc_plan.py` 的 `Item` 结构。

### S2 算方案（本地，不联网）

调 `scripts/mcsc_plan.py`，**务必传 `--occasion`**——场合会改变组合本身：

```bash
python skill/scripts/mcsc_plan.py --items fixtures/meals.sample.json \
    --budget 100 --headcount 2 --occasion birthday
```

引擎内部的场合策略（`OCCASION_POLICY`，可审计）：

| 场合 | 组合约束（不是文案，是硬过滤） |
|---|---|
| 生日/庆祝/纪念日/表白/求和好 | 甜品必须在场，优先可分享 |
| 道歉 | 甜品在场 + **强制单人份**——摆一大桌反而像应付 |
| 加班慰问 | 必须有饮品，优先热饮，同分偏热量低 |
| 安慰 | 饮品 + 甜品双必须 |
| 给孩子 | 自动儿童模式（排辣与咖啡因）+ 甜品 |
| 自己吃 | 实惠优先，不摆排场 |

输出展示层固定三个**有名字**的方案，每个都带"为什么"：
- **心意款**：场合契合分最高（预算利用率只是次级因素，不再花满优先）
- **均衡款**：心意与预算之间取中
- **省钱款**：**硬承诺**——满足同样场合要求的前提下最便宜的组合。省的是钱，不是心意（甜品等必须项一样不少）

如果连省钱款都凑不出来，直接说"这个预算在这家店配不出满足场合要求的组合"，并给出最低可行预算。**不要为了凑单偷偷加价。**

### S3 核价（调 MCP，必须做）

对用户选中的方案调 `calculate-price`，参数：
- `storeCode`、`beCode`（外送时还要 `addressId`）
- `items`：对象数组，形如 `[{"productCode":"9900013722","quantity":1}]`
- 有券时传 `couponId`

**展示给用户的一定是 `calculate-price` 的返回金额，不是 S2 算出来的预估价。** 两者不一致时，以 MCP 为准并说明差额原因。

### S4 写卡（本地 + 红线检查）

按 S0 定下的 tone 从 `data/personas.json` 里取句式骨架，生成：
1. 一句开场（不说客套话）
2. 一句正题（说清楚为什么请他吃这顿）
3. 一句收尾（不索取回应）

生成后**必须**过一遍红线检查：

```bash
python skill/scripts/mcsc_copyguard.py "生成的文案"
```

或批量：`from mcsc_copyguard import check_copy; check_copy(text, relationship="lover")`

任何 `BLOCK` 命中都要重写，不能"忽略继续"。`warn` 可以保留但要向用户提示。
同时必须提供一个"换语气"选项 —— 至少能出 3 种（温润 / 损友 / 克制），让用户挑。

### S5 交付

**生成结果卡**：调 `scripts/mcsc_card.py --out result-card.html`（或在会话内 import `render_card`），产出一张单文件 HTML：内联样式、无外部资源、手机宽度友好，可直接截图分享。卡上必须带来源徽章——演示数据标 `SIMULATED`，真实核价标 `价格已用 MCP 核价`，两者不能混。

输出卡片（Markdown），到这一步**还不下单**：

```
🎂 {occasion} · for {relationship}
📅 {日期} · {人数} 人份 · {到店/外送}
💌 卡片
   {三句话文案}
🍔 搭配（合计 ¥xx.x，预算 ¥xx，剩 ¥x.x）
   - {菜名} ×1 ¥xx.x
💰 核价：¥xx.x（已用券：{券名}，减 ¥x.x）
📍 {门店全名}（{地址，营业时间}）
```

然后问一句：「要我现在下单吗？」
用户明确说"下"之后，才调 `create-order`，并把支付链接原样给用户，提醒**支付由你自己完成**。

## 边界与失败处理

- **门店必须用户确认**。默认给最近 3 家让他选，绝不自动选。
- **价格必须实时**。`fixtures/` 里的价格带 `SIMULATED` 标记，只能用于离线演示，不能出现在正式方案里。
- **热量数据可能缺失**。麦当劳营养表未收录的商品，一律标"热量未知"，合计改口"≥ N kcal"。
- **过敏原与忌口只能粗筛**。菜单数据没有配料表，涉及过敏时必须提示"以门店确认为准"。
- **订单失败**（库存、门店休息、限流 429）：如实告知，不要重试到刷屏。429 时退避 30 秒以上。
- **Token 不进对话**。MCP Token 只存在客户端配置里，任何时候不要在输出中出现。

## 文件

| 路径 | 作用 |
|---|---|
| `data/personas.json` | 语气与文案素材（只放词句，不放价格和菜名） |
| `docs/COPY-GUARD.md` | 文案红线，`scripts/mcsc_copyguard.py` 是它的可执行版本 |
| `scripts/mcsc_plan.py` | 预算配餐引擎：场合驱动组合 + 心意/均衡/省钱三方案，纯本地、零依赖 |
| `scripts/mcsc_copyguard.py` | 文案红线检测，纯本地、零依赖 |
| `scripts/mcsc_card.py` | 结果卡生成器：单文件 HTML，可截图分享 |
| `fixtures/` | 离线演示数据，全部标记 SIMULATED |
