# 麦事 mcscene

> 说一句「给谁、花多少、为什么请」，它给你一份**能直接下单**的麦当劳方案：按对象调过语气的祝福卡、预算内实时核过的餐、以及一张说明为什么这么配的账单。

一个跑在 WorkBuddy 上的 Agent Skill，所有菜品、价格、优惠券来自麦当劳中国官方 MCP 实时返回。

---

## 它解决什么问题

给恋人过生日，你想的不是"哪个汉堡便宜"，而是：

- 100 块能点出"有仪式感"吗？
- 甜点的钱该不该花？
- 卡片上写什么才不像群发祝福？

这三件事以前要开三个 App。现在一句话：

```
女朋友这周日生日，预算 100，想有点仪式感
```

```
🎂 生日 · for 恋人
💌 卡片
   不知道说什么，就先给你点一份你爱吃的。
   今天不用上班打卡，只要好好吃一顿。
   吃完记得拍照给我看。

🍔 搭配（2 人份 · 到店外带）
   - 双层吉士汉堡 ×1
   - 板烧鸡腿堡 ×1
   - 中薯条 ×1
   - 麦旋风 ×1
💰 核价 ¥95.80（已用券：满 60 减 8，减 ¥8.00）
📍 门店名称由你选（见下方 3 家候选）

要我现在下单吗？
```

---

## 三个不一样的地方

### 1. 语气是算出来的，不是猜的

`data/personas.json` 里有 10 类对象 × 12 类场合，内置切换规则：

- 对上级/客户/同事 → 自动切"克制"，禁用"兄弟""老铁"
- 道歉场景 → 自动压掉甜言蜜语，改用"诚恳"
- 用户自己说了"不知道说什么" → **不覆盖**他的情绪基调

生成后还能一键换 3 种语气（温润 / 损友 / 克制）。语气判断错了后面全白做，所以这一步会先说理由，让你有机会推翻。

### 2. 文案有红线，而且是可执行的

`docs/COPY-GUARD.md` 写了 8 组红线，`scripts/mcsc_copyguard.py` 把它变成代码：

| 类别 | 拦截示例 |
|---|---|
| 不编造事实 | ~~"还记得去年我们在外滩那家店"~~ |
| 不做超范围承诺 | ~~"吃了就会开心起来"~~、~~"这顿之后我们就和好吧"~~ |
| 不美化暴食 | ~~"扶墙出"~~、~~"吃不完就扔"~~ |
| 不做品牌对比 | ~~"比肯德基好吃多了"~~ |
| 不评价人 | ~~"你最近胖了吧"~~、~~"三十了还没对象"~~ |
| 称呼得体 | 对上级说"兄弟"直接拦截 |
| 价格必须可溯源 | 非 MCP 返回的价格，一律拦截 |

命中 `BLOCK` 必须重写，不允许"忽略继续"。

### 3. 价格只有 MCP 说了算

本地引擎只做**筛选与排序**，不做定价。任何出现在方案里的金额，都能追溯到一次真实的 `calculate-price`。预排价格和核价不一致时，以核价为准并说明差额——不会"先报个好看的数再说"。

同理，热量缺项一律标"热量未知"，合计写成 `>= N kcal`，**绝不按 0 算**。

---

## 安装

### 前置：申请麦当劳 MCP Token

1. 打开 <https://open.mcd.cn/mcp>，手机号登录
2. 右上角「控制台」→「激活」→ 同意协议 → 复制 Token

### 接入 WorkBuddy

在 WorkBuddy 左侧「专家 · 技能 · 连接器」→「连接器」→ 右上「自定义连接器」→「配置 MCP」，填入（详见 `mcp-config.example.json`）：

```json
{
  "mcpServers": {
    "mcd-mcp": {
      "type": "streamablehttp",
      "url": "https://mcp.mcd.cn",
      "headers": { "Authorization": "Bearer 你的Token" }
    }
  }
}
```

保存后回到连接器列表**启用** `mcd-mcp`。

### 安装 Skill

把 `skill/` 目录复制到 `~/.workbuddy/skills/mcscene/`，重启会话即生效。

> ⚠️ Token 只放在客户端配置里。仓库中的示例配置只使用 `${MCD_MCP_TOKEN}` 占位符。

---

## 离线试用（不需要 Token）

引擎是纯标准库、零依赖，可以直接跑：

```bash
# 单人要 60 元，看三个方案
python skill/scripts/mcsc_plan.py --items skill/fixtures/meals.sample.json --budget 60

# 两个人 100 元，看边际取舍
python skill/scripts/mcsc_plan.py --items skill/fixtures/meals.sample.json --budget 100 --headcount 2

# 儿童模式：自动排除辣与含咖啡因
python skill/scripts/mcsc_plan.py --items skill/fixtures/meals.sample.json --budget 40 --kid

# 文案红线检测
python skill/scripts/mcsc_copyguard.py "生日快乐，吃了就会开心起来的"

# 回归测试（127 条断言）
python skill/tests/test_engine.py
```

`fixtures/` 里的数据带 `SIMULATED` 标记，脚本会主动打警告——**演示数据不会伪装成真实菜单**。

---

## 目标用户

| 用户 | 场景 | 他最怕的事 |
|---|---|---|
| 恋爱中的年轻人 | 生日、纪念日、道歉 | 点得没诚意，文案像群发 |
| 职场人 | 请同事吃饭、加班慰问、缓和关系 | 花多花少都不合适 |
| 离家子女 | 给父母点一份 | 口味不清、点太多浪费 |
| 自己 | 想好好吃一顿 | 选择困难、预算失控 |

---

## 项目结构

```
mcscene/
├── README.md                     本文件
├── CONTEST_DECLARATION.md        参赛声明（官方原文，未改动）
├── MCP_INTEGRATION.md            MCP 工具清单、调用流程、参数陷阱
├── mcp-config.example.json       脱敏配置示例（仅环境变量占位符）
├── workbuddy.md                  WorkBuddy 开发对话上下文（专项奖励用）
└── skill/
    ├── SKILL.md                  技能定义：槽位、工作流 S0-S5、边界
    ├── data/personas.json         10 类对象 × 12 类场合 × 5 种语气
    ├── docs/COPY-GUARD.md         文案红线（人读版）
    ├── scripts/
    │   ├── mcsc_plan.py           预算配餐引擎（零依赖）
    │   └── mcsc_copyguard.py      文案红线检测（零依赖）
    ├── fixtures/meals.sample.json 离线演示数据（SIMULATED）
    └── tests/test_engine.py       127 条断言
```

---

## 互动演示（无需 Token，打开即玩）

**在线版**：开启 GitHub Pages 后访问 <https://qimuzhenxingchen.github.io/mcscene/>（仓库 Settings → Pages → 选 main 分支即可）

**本地版**：直接用浏览器打开 [`demo/index.html`](demo/index.html)

Demo 内嵌龙洞第二餐厅 2026-10-18 真实菜单快照，可以：
- 切换 10 种场合（庆生 / 道歉 / 加班慰问 / 给孩子……），看组合约束实时变化——庆生必有甜品、道歉强制单人份、加班必配热饮
- 拖动预算 25–150 元，方案实时重排
- 勾"不吃辣"，含辣项即时消失
- 三个方案（心意 / 均衡 / 省钱）带"为什么这么配"的可审计理由

演示数据已标注 `SIMULATED` 口径说明；真实版接 MCP 后价格实时、可核价、可下单。

---

## 真实链路验证（2026-10-18）

以下全部来自 McDonald's China MCP 实时调用，可用 `workbuddy.md` 中的对话记录核验：

| 环节 | 结果 |
|---|---|
| `now-time-info` | ✓ 200，服务器时间 2026-10-18 17:37 GMT+8 |
| `query-nearby-stores` | ✓ 广州龙洞 5 家门店（130m/224m/401m…） |
| `query-meals` | ✓ 龙洞第二餐厅（storeCode 1400242）当次菜单 100+ SKU，快照存于 `skill/fixtures/` |
| `list-nutrition-foods` | ✓ 160 项营养数据；快照中 22/29 项已映射热量，口味歧义项（麦旋风/派/新地）保持 UNKNOWN |
| `query-store-coupons` | ✓ 返回空——该门店当前无可用券，如实展示 |
| `calculate-price` ×3 | ✓ 庆生 ¥96.40 / 加班 ¥58.80 / 道歉 ¥44.90，与本地预排 100% 一致 |
| `create-order` | **未调用**——全程无真实订单 |

踩坑记录（评审可复核）：
- `query-nearby-stores` 关键词传全称"广东工业大学龙洞校区"返回 `internal_error`，短词"龙洞"正常——门店搜索关键词需要短地标。
- 加班慰问方案中的麦咖啡奶铁，菜单现价 ¥13.9，`calculate-price` 返回原价 ¥21 + 自动优惠 ¥7.10：预排引擎取菜单现价、核价返回拆分明细，两者天然一致。
- 修正记录：早期宣传"情感场景没人做"不成立（麦门树洞、mcdinner-mate 等已在赛道内），本项目的差异化在"场合作为配餐引擎的一等输入"，见 `PLAN.md`。

三张真实结果卡：`card-birthday.html` / `card-overtime.html` / `card-apology.html`（单文件、无外部资源、手机宽度，可直接打开预览）。

---

## 已知边界（诚实版）

1. **热量覆盖率取决于营养表**。`list-nutrition-foods` 未收录的餐品会标"未知"，方案里可能出现"≥ 1150 kcal"这类表述。
2. **过敏原与忌口只能按名称/标签粗筛**。菜单接口没有配料表，涉及过敏时一律提示"以门店确认为准"。
3. **儿童模式**只排除辣与含咖啡因项，不构成营养建议。
4. **预算极紧时宁可不出方案**。5 元配不出完整一餐，脚本会直接说"配不出"，而不是硬凑一个三件套。
5. **不代付**。下单后返回的支付链接由用户自己完成支付。

---

## 关于本次比赛

麦当劳程序员创意开发大赛（M-CODE）参赛作品，由个人独立开发，非麦当劳官方产品。
菜品信息、价格及供应状态以麦当劳官方渠道实时结果为准。

## License

MIT（`CONTEST_DECLARATION.md` 按赛事要求原样保留）
