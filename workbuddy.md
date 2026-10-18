# WorkBuddy 开发对话上下文 · 麦事 mcscene

> 本文件用于核验项目真实使用腾讯 WorkBuddy 开发（WorkBuddy 专项奖励）。
> 内容为 2026-10-18 单日会话的关键对话片段与时间线，敏感凭证已脱敏。
> 完整过程可对照 commit 历史（224291c → fe1b753）与 `scripts/gen_real_cards.py` 等产物核验。

## 会话信息

- 开发工具：腾讯 WorkBuddy（桌面端，Agent 模式）
- 会话日期：2026-10-18 16:02 — 19:46（GMT+8）
- 产出：本项目全部代码、文档、测试与真实链路验证

## 时间线（与 git 历史、WorkBuddy 对话可交叉核验）

| 时间 | 事件 |
|---|---|
| 16:02 | 发起会话，调研麦当劳 M-CODE 大赛 |
| 16:05 | 检索官方仓库、活动规则（activityGuidelines.md）、MCP 工具清单 |
| 16:20 | 榜单分析：榜首 531 Star / 第 100 名约 14 Star，定两层目标 |
| 16:30 | 选题确定：场景化心意配餐（mcscene），搭建项目骨架 |
| 16:35–16:45 | 引擎首版开发，修复 tuple 拼接 TypeError，回归测试全绿 |
| 17:10 | 吸收外部评审三点意见：场合驱动组合（OCCASION_POLICY）、排序改版（心意/均衡/省钱三方案）、新增结果卡生成器 |
| 17:20 | 修正选题论证：检索证实情感赛道已有竞品，差异化改为"场合作为配餐一等输入" |
| 17:25 | 测试扩至 335 条断言，全绿 |
| 17:37 | 用户接入麦当劳 MCP，`now-time-info` 冒烟测试通过 |
| 17:41 | 真实链路：门店搜索（发现全称关键词报 internal_error 的坑）→ 实时菜单 → 营养表 → 券查询 |
| 17:43–17:44 | 三次 `calculate-price` 真实核价，与本地预排 100% 一致 |
| 18:49 | 用户反馈文案"人机味"，新增 emoji/颜文字语气资源与纪律规则（EMO-01/CAL-02） |
| 18:57 | 用户反馈 UI，结果卡视觉全面改版 |
| 19:09 | 仓库创建并公开，匿名访问验证通过 |
| 19:15 | 互动演示页（单文件 HTML，零依赖）上线 GitHub Pages |

## 关键对话片段（节选，凭证已脱敏）

### 1. 选题与现状判断

**用户**：workbuddy 是不是和麦当劳最近有什么合作活动

**WorkBuddy**：（检索后）有，麦当劳程序员创意开发大赛（M-CODE），2026-10-09 至 10-25，按 GitHub Star 排名，前 100 名有奖励……当前第 100 名门槛约 14 Star。

**用户**：我决定要参与

**WorkBuddy**：（给出四个选题方向供选择，用户选定"情感/场景策划"）……

### 2. 架构红线

**WorkBuddy**：价格只能来自 MCP `calculate-price`，本地引擎只做筛选不定价——这样任何金额都能追溯到一次真实接口调用。热量缺项标 UNKNOWN，合计用 `>= N kcal`，绝不按 0 算。

### 3. 排错实录一：tuple 拼接

**WorkBuddy**：`TypeError: can only concatenate tuple (not "list") to tuple`——定位在 `chosen + [ex]`，`chosen` 来自 `itertools.product` 是 tuple，改 `list(chosen) + [ex]`。修复后回归测试全绿。

### 4. 排错实录二：门店搜索关键词

**WorkBuddy**：`query-nearby-stores` 传全称"广东工业大学龙洞校区"返回 `internal_error`；换短词"龙洞"成功，返回 5 家门店。已记入踩坑文档。

### 5. 外部评审吸收（用户转述 Codex 意见后）

**WorkBuddy**：三点意见核实后全部落地：①场合影响组合本身（OCCASION_POLICY：庆生必含甜品/道歉强制单人份/加班必含热饮偏轻）；②排序弃用"花满预算优先"，改为场合契合分优先 + 省钱款硬承诺；③新增结果卡生成器。同时修正选题论证——情感赛道非空白，差异化改口为"场合作为配餐一等输入"。

### 6. 文案红线的自证

**WorkBuddy**：加班卡第一版给"同事"用了颜文字，被自建的 CAL-02 规则（正式关系禁颜文字）拦截。处理方式是改文案而不是放宽规则——红线真的在跑。

### 7. 真实核价一致性

**WorkBuddy**：三次 `calculate-price`（¥96.40 / ¥58.80 / ¥44.90）与本地预排完全一致；加班款奶铁咖啡被 MCP 自动应用 ¥7.10 促销（原价 21 → 13.9），验证了"菜单现价已含促销、核价返回拆分明细"的机制。

## 产物核验清单

| 产物 | 位置 |
|---|---|
| 配餐引擎（场合驱动 + 三方案） | `skill/scripts/mcsc_plan.py` |
| 文案红线检测（30 规则） | `skill/scripts/mcsc_copyguard.py` |
| 结果卡生成器 | `skill/scripts/mcsc_card.py` |
| 回归测试（335 断言） | `skill/tests/test_engine.py` |
| 真实菜单+营养快照 | `skill/fixtures/meals.1400242.dinein.20261018.json` |
| 互动演示页 | `index.html`（GitHub Pages 已上线） |
| 真实结果卡 ×3 | `card-birthday.html` / `card-overtime.html` / `card-apology.html` |

## 凭证说明

- MCP Token 在本会话中出现，已全文脱敏为 `REDACTED`；仓库内仅允许 `${MCD_MCP_TOKEN}` 环境变量占位符（见 `mcp-config.example.json`）。
- 配套截图：`docs/screenshots/`（WorkBuddy 会话界面截图，由项目作者补充上传）。
