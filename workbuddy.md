# WorkBuddy 导出格式的对话上下文（示例，需替换为真实记录）

> 本文件用于核验项目是否真实使用 WorkBuddy 开发。
> **提交前请替换为你自己 WorkBuddy 会话导出的 Markdown**，保留以下结构即可。

## 会话 1 · 选题

**用户**：榜单上省钱、热量这两类已经很卷了，我不想做第 9 个减脂工具。有没有没人做又真有人要的方向？

**WorkBuddy**：先看榜单结构再决定……

## 会话 2 · 架构定调

**用户**：价格能不能在本地先算个大概？

**WorkBuddy**：不建议。理由：……

## 会话 3 · 排错

**用户**：跑起来报 TypeError: can only concatenate tuple (not "list") to tuple

**WorkBuddy**：定位在 `mcsc_plan.py` 的 `chosen + [ex]`，`chosen` 来自 `itertools.product`，是 tuple。改 `list(chosen) + [ex]`。

## 会话 4 · 测试

**用户**：把"绝不超预算"写成断言。

**WorkBuddy**：加了 5 个预算 × 3 种人数的组合遍历……最终 127 条断言。
