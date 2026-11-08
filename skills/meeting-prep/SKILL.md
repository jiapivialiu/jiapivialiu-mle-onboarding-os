---
name: meeting-prep
description: 基于当前 Tasks、Event Log 与历史 Meeting Notes，准备简洁、有依据的会议讨论提纲（尤其是 1:1）。
---

# Meeting Prep

## 何时使用
用户要求准备即将参加的会议；这是会前讨论提纲，不是个人 Weekly Update。

## 输入
- 必需：会议目标或类型，以及可用的近期工作记录（Task、Log 或用户说明之一）。
- 可选：会议时间、参会角色、上次 Meeting Notes、待确认问题。
- 优先使用 Project A 的 `tasks.json` 当前状态及 `events.jsonl` 事件；按会议相关性和用户指定时间范围过滤。
- 模板：每次读取当前 Workspace 的 `templates/meeting-prep.md`，或填充 Project A 已生成的空白 Draft。

## 流程
1. 从 Task 的**当前状态**识别 Blockers 和未完成项；从 Event Log 识别时间窗口内的真实进展。
2. 提取 Progress、Challenges、已有的 `approach` / `rationale`；不得根据状态自行推测动机。
3. 根据 Due Date 与已记录的计划提出 Next Week 候选；长期目标只使用明确提供的信息。
4. 参考上次会议的 Decisions / Follow-ups，列出本次需要讨论的问题或决策。
5. 按最新模板生成一份**新的** Draft；用 Task ID / Meeting Reference 支持关键事实。

## 默认讨论维度（模板可修改）
- Progress / Accomplishments
- Challenges / Blockers
- Proposed Approach & Rationale
- Next Week Priorities
- Longer-term Expectations / Goals
- Questions / Decisions Needed

## 约束与失败处理
- 只写有依据的进展；缺失的 Approach、Rationale、目标或会议时间标 `待补充`。
- 不把 Planned 写成 Done，不从过期记录覆盖最新 Task Status。
- 不修改原始 Tasks、历史 Notes 或会议邀请；不自行安排 Reminder。
- 必需输入缺失、数据冲突无法消解或模板缺失时，说明问题并给出可人工补充的最小提纲。
- 默认中文 + 英文专有名词；保持简洁、适合会议中快速查看。
