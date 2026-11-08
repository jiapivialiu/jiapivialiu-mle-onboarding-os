# Project A — Personal Onboarding Hub

### 3.1 固定决定

- **Markdown + CLI**；结构化数据采用 **JSON**；历史事件采用 **JSONL**。
- 独立 Workspace，与工具 Repo 分离。
- **Flat Task List**，不强制 Project / Goal 层级；`tags` 可选。
- **Task-first + Lightweight Daily Log**：任务状态变化自动产生 Event；Daily Log 可按需填写。
- Core MVP：Tasks、Events、Meeting Notes、Meeting Prep、People Directory、Templates、Diagnostics。
- 30/60/90 Goals 初期仅用 Markdown Template，不另建复杂追踪系统。

### 3.2 Workspace 与最小数据契约

```text
<workspace>/
  tasks.json
  events.jsonl
  people.json
  logs/YYYY-MM-DD.md
  meetings/*.md
  preps/*.md
  people/*.md                 # 可选的互动笔记
  digests/*.md                # B 生成
  review_queue.json          # B 的建议队列
  sync_state.json            # B 的每源状态
  templates/*.md             # 用户自定义覆盖版本
  config.json                # 不含 Secret
```

`tasks.json` 顶层为 `schema_version`、`updated_at`、`tasks`（以 Task ID 为 Key 的 Dictionary）。每个 Task 支持：

- 必需：`title`、`status` (`todo|in_progress|blocked|done|cancelled`)、`priority`、`created_at`、`updated_at`。
- 自动/可选：`started_at`、`completed_at`、`due_at`、`tags`、`challenge`、`approach`、`rationale`、`notes`、`source_ref`。
- `id` 由 Dictionary Key 唯一标识。时间使用带时区的 RFC 3339，落盘统一 UTC；空值使用对应类型的 `null`、`""`、`[]`，并通过 Schema 校验。
- `due_at` 不要求每项 Task 都填写；Overdue 由当前时间计算，不新增状态。

`events.jsonl` 仅自动记录关键事件：`task_created`、`status_changed`、`task_completed`、`task_reopened`；至少含 `event_id`、`task_id`、`type`、`occurred_at` 和必要状态差异。文本编辑不要求完整审计日志。

Agent 通过 CLI 修改数据，不直接编辑 JSON。写入使用 Schema Validation + 原子替换；跨 `tasks.json` / `events.jsonl` 不假设天然事务，失败需显式报告且 `doctor` 能发现并指导恢复。单 Writer 或 File Lock 防止并发覆盖。

### 3.3 People Directory

`people.json` 以稳定 Person ID 为 Key，支持：`display_name`、`email`、`role`、`team`、`external_ids`、`related_projects`、`source_refs`、`last_interaction_at`、`updated_at`；均允许适当缺省。详细互动笔记可存放在 `people/*.md`。

- 可靠、稳定 User ID 对应的基本信息允许自动同步；同名不自动合并。
- 推断的 Project 关系、身份冲突和不可靠的 Role 变化进入 Review Queue。
- 不自动覆盖人工备注与 Feedback；保留来源和更新时间。

### 3.4 Meeting ↔ Task 与 Templates

- Meeting Notes 默认包含 `## Action Items`，使用 `- [ ]` Checklist；这是与 CLI 的**稳定解析契约**。其他 Section 可随时增删、重排。
- CLI 列出 Action Items 序号，并支持从指定 Meeting 的第 N 项**显式创建** Task，填充 `source_ref`，防止重复导入。
- **Meeting → Task 单向**：完成 Task 不改原 Meeting。
- **Task/Event → Meeting Prep 单向**：根据最新状态生成**新的 Draft Snapshot**，不反向改 Task、不覆盖历史 Prep。
- Project A 只能确定性收集 Progress / Blockers / Draft Candidates；对 Challenge、Approach、Rationale 等缺失字段输出空白或 TODO，不能编造。Project C 负责 AI 组织表达。
- 所有重复文件使用**运行时读取的 Markdown Template**；先找 Workspace 自定义版本，缺失时回退 Repo 默认版本。修改 Template **下一次生成生效**，不批量重写已生成文件。

推荐的 `meeting-prep.md` Section：Progress；Challenges；Proposed Approach & Rationale；Next Steps；Longer-term Expectations；Questions / Decisions Needed。Section 可配置。

### 3.5 CLI 最小接口（命令命名为目标契约）

```bash
onboard init
onboard today
onboard task add "..."
onboard task list --json
onboard task show TASK-001 --json
onboard task update TASK-001 --status blocked
onboard task done TASK-001
onboard log today
onboard meeting new
onboard meeting actions <file>
onboard task add --from-meeting <file> --item 2
onboard meeting prep --days 7
onboard people list --json
onboard doctor
```

JSON 模式使用稳定字段、可机器读取的结构和非零失败 Exit Code；普通模式面向人工阅读。使用者不必手写 JSON。
