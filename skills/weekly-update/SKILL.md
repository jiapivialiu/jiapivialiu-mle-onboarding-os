---
name: weekly-update
description: 根据 Tasks、Task Events 与可选 Daily Logs 生成个人每周工作总结，区分完成事项、学习、阻塞与下周计划。
---

# Weekly Update

## 何时使用
用户要求个人周总结或周复盘；默认**不等于**给 Manager 发送的状态汇报。

## 输入
- 必需：报告周期，以及至少一份工作记录（Task State、Events、Daily Log 或用户提供的事实）。
- 推荐：Project A 的 `tasks.json`（当前状态）、`events.jsonl`（历史事件）；Daily Logs 可选。
- 时间范围未给出时，使用 Workspace 时区中的最近一个完整工作周；时区未知时先确认或标注假设。
- 模板：每次读取当前 Workspace 的 `templates/weekly-update.md`；已生成的空白 Draft 则直接填充。

## 流程
1. 按周期从 Event Log 提取创建、完成、重新打开和 Blocked 等关键变化，避免重复计数。
2. 与当前 Task Status 交叉核对；本周标记完成但之后重新打开的任务不得作为当前已完成成果。
3. 合并 Daily Log 中已记录的 Learnings、Challenges 和决定；区分事实、计划与待验证的推断。
4. 选择最重要的 Progress、Learnings、Blockers、Next Week 项；使用 Task ID / 来源链接支持关键结论。
5. 读取**最新模板**，生成精简的 Markdown Draft；无内容的 Section 不强行凑字数。

## 输出与边界
- 一份新的个人 Weekly Update；默认模板含 Progress、Learnings、Challenges、Next Week。
- Project A 负责持久化与事件查询；本 Skill 只整理内容，不创建/更新 Task、不发送报告、不设置 Reminder。
- 可日后改用面向 Manager 的模板，但必须由用户选择，不自动改变受众。

## 约束与失败处理
- 不把 `todo` / `in_progress` 写为 `done`，不把 Task 数量当成业务 Impact。
- 缺少任务历史时明确说明覆盖范围；缺少数据不编造数字、成果或原因。
- Template 缺失、数据损坏或周期不明确时，明确报告并请求必要信息，不输出虚假的完整周报。
- 默认中文 + 英文专有名词；优先具体事实、短句和可执行下一步。
