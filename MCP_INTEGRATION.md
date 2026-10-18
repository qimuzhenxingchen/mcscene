# MCP_INTEGRATION

本文件说明麦事（mcscene）实际使用哪些麦当劳 MCP 工具、按什么顺序调用、以及每个调用为什么必须存在。

- MCP Server：麦当劳中国官方 MCP，接入地址 `https://mcp.mcd.cn`（Streamable HTTP + `Authorization: Bearer <TOKEN>`）
- 官方文档：<https://github.com/M-China/mcd-mcp-server>
- 协议：本 Skill 不使用任何非官方接口，不抓取页面，不破解。所有菜品、价格、券、门店信息全部来自上述 MCP 的实时返回。

---

## 1. 工具使用清单

| 阶段 | 工具 | 为什么必须用它 | 不用的后果 |
|---|---|---|---|
| 定餐段 | `now-time-info` | 早餐/正餐/下午茶/夜宵的菜单不同，用本地时间会受时区与用户设备影响 | 给出该时段已经售完或不供应的餐品 |
| 选门店 | `query-nearby-stores` | 拿到 `storeCode` / `beCode`，且门店决定菜单与价格 | 无法取菜单，或取到别家店的菜单 |
| 选门店（外送） | `delivery-query-addresses` → `delivery-query-stores` | 外送场景的 `addressId` 决定可配送门店与配送费 | 报价缺 `addressId`，`calculate-price` 直接报错 |
| 取菜单 | `query-meals` | 当次可售餐品、价格、标签的唯一来源 | 任何"记忆里的菜单"都可能过期或错价 |
| 取详情 | `query-meal-detail` | 套餐内可选替换项，决定"要不要换更便宜的饮料" | 无法做同价替换，方案质量下降 |
| 可用券 | `query-store-coupons` | 只做标注：告诉用户"这张券能用，能减 X" | 用户不知道自己少了优惠 |
| 核价 | `calculate-price` | **唯一**的金额来源，含券后应付 | 展示的金额与真实应付不一致，属于严重误导 |
| 下单 | `create-order` | 仅在用户逐字确认后调用 | —— |
| 营养 | `list-nutrition-foods` | 热量数据来源，用于"这顿大概多少卡" | 无法给出热量或只能瞎猜 |

**明确不用的工具**：`draw-lottery`、`mall-create-order`、`party-order-create`、`auto-bind-coupons`。
前三个属于用户账户的其他操作，超出本 Skill 职责；`auto-bind-coupons` 会改变用户账户状态，属于"未经允许的副作用"，一律不调。

---

## 2. 调用流程

### 2.1 到店取餐（主流程）

```
now-time-info
  → query-nearby-stores(searchType=2, beType=1, city, keyword)
  → [用户确认门店] storeCode + beCode
  → query-meals(storeCode, beCode, orderType=1, reservationDate=餐段代表时刻)
  → query-meal-detail(productCode)  ← 仅对候选套餐调用，不必全量
  → query-store-coupons(storeCode, beCode, orderType=1)
  → calculate-price(storeCode, beCode, orderType=1, items[], couponId?)
  → [展示金额，用户确认]
  → create-order(...)
```

### 2.2 麦乐送外送

```
delivery-query-addresses(beType=2)
  → [已有 addressId] 或 delivery-create-address（需用户提供地址，不代填）
  → delivery-query-stores
  → query-meals(storeCode, beCode, orderType=2)
  → query-store-coupons / calculate-price / create-order  ← 均带 addressId
```

### 2.3 关键参数陷阱（已实测踩过）

1. **`query-meals` 没有 `daypart` 参数。** 要查某个餐段，传 `reservationDate` 为该餐段的代表时刻（例如要午市菜单就传当天 12:00 附近的时间）。否则返回的是"当前时刻"的菜单。
2. **`calculate-price` / `create-order` 的 `items` 是对象数组**，形如 `[{"productCode":"...","quantity":1}]`；写成字符串或 `productList` / `products` 都会报"缺少参数"。
3. **到店场景的 `beCode` 可能为 `null`**，但外送场景必须同时带 `storeCode`、`beCode`、`addressId`。
4. **限流 600 次/分钟**，超限返回 429。本 Skill 在对话层对菜单结果做进程内缓存（同一门店同一餐段 10 分钟内不重复请求），并对 429 退避 30 秒以上再试，不刷屏重试。

---

## 3. 本地计算与 MCP 的边界

| 环节 | 在哪算 | 说明 |
|---|---|---|
| 价格 | **只在 MCP** | `scripts/mcsc_plan.py` 接受的价格字段必须来自 `query-meals` / `calculate-price`，引擎自己不做定价 |
| 预算筛选、组合枚举 | 本地 | 纯筛选，不产生新价格 |
| 热量合计 | 本地 | 数据来自 `list-nutrition-foods`；缺项标 UNKNOWN，不按 0 计 |
| 文案生成 | 本地 + 模型 | 只用 `data/personas.json` 的词句骨架，不引入菜品名与价格 |
| 文案合规 | 本地 | `scripts/mcsc_copyguard.py`，命中 block 必须重写 |

这个边界的意义：**任何金额出现的地方，都能追溯到一次真实的 MCP 返回**。评审或用户只要看对话记录就能核实。

---

## 4. 业务价值

一句话：**把"想请他吃个饭"这个 0.5 秒的念头，变成一笔真的能下、也知道为什么这么点的订单。**

- 对用户：不用在几十个 SKU 里挑，不用自己算预算，不用纠结"这样点会不会显得没诚意"。
- 对麦当劳：把"节日/情绪驱动的低频点餐"拉成可运营的场景，同时把券真正用出去（本 Skill 会主动查门店可用券并标注）。
- 对 Agent 生态：展示了"调接口"之外的第二层价值——**约束求解 + 语气判断 + 合规检查**，这三件事都不是单次工具调用能完成的。

---

## 5. 安全与合规

- Token 只出现在客户端 MCP 配置中，仓库内 `mcp-config.example.json` 仅使用环境变量占位符 `${MCD_MCP_TOKEN}`。
- 不落盘任何订单原始响应；如需演示，只用 `fixtures/` 下的模拟数据，并标 `SIMULATED`。
- `create-order` 前必须有明确的人工确认，且不代付。
- 不采集、不上传用户个人信息；地址由用户在 McDonald's 官方流程中自行填写。
