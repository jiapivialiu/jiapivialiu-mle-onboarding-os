# Onboarding OS — Minimal Public Starter

轻量、可迁移的个人工作信息系统：**Project A**（本地 Tasks / People / Notes）、**Project B**（Mock Intake / Review Queue / Digest）、**Project C**（3 个通用 Agent Skills）。默认中文，保留英文专有名词。

> 重要：本 Public Repo 只能包含通用代码、模板和 Synthetic Data。真实 Workspace 必须位于组织批准的**独立目录**；禁止把工作资料、真实人员信息、内部链接、凭证、录音或 Transcript 提交到公开仓库。

## Agent 快速开始

将 Repo 迁移到获批准的内部环境后，告诉 Agent：

> Read `AGENTS.md`, inspect this repository and my current environment, and propose a minimal safe setup. Do not install integrations, create reminders or enable schedules without asking me.

Agent 应优先阅读 [AGENTS.md](AGENTS.md)、[Setup / Safety](specs/setup-and-safety.md) 和对应 Project Spec。不要假设公司提供任何特定 LLM、MCP 或 App。

## 无 AI / 无联网也能运行

需求：Python 3.10+；macOS 或 Linux（使用系统文件锁），不依赖外部 Python Package。

```bash
# 选一个独立于 Repo 的目录，演示请使用临时目录。
export ONBOARD_WORKSPACE="$(mktemp -d)/onboard-demo"
python3 onboard.py init
python3 onboard.py task add "Review mock documentation" --json
python3 onboard.py task list --json
python3 onboard.py log today
python3 onboard.py meeting new --title "Sample 1on1"
python3 onboard.py meeting prep --days 7
python3 onboard.py doctor

# 只用 Synthetic Data 测试 Project B
python3 onboard.py sync import --file examples/synthetic-source-records.json --source sample
python3 onboard.py review list
python3 onboard.py sync digest
python3 onboard.py sync status
```

可选：在公司批准的 Python 环境里执行 `python3 -m pip install -e .`，之后可直接使用 `onboard` 命令。没安装时用 `python3 onboard.py` 功能相同。CLI 在正常或失败情况下输出 JSON Envelope：`{"status": "success|failed", "data|error": ...}`；失败有非零 Exit Code。

## 常见操作

| 目的 | 示例命令 |
|---|---|
| 新建 Task | `python3 onboard.py task add "Read guide"` |
| 更新 Task | `python3 onboard.py task update TASK-0001 --status blocked --challenge "Access pending"` |
| 完成 Task | `python3 onboard.py task done TASK-0001` |
| 获取 Machine-readable Tasks | `python3 onboard.py task list --json` |
| 查看 Meeting Action Items | `python3 onboard.py meeting actions 2026-01-01-sample-1on1.md` |
| 导入指定 Action Item | `python3 onboard.py task add --from-meeting 2026-01-01-sample-1on1.md --item 1` |
| 创建 Meeting Prep | `python3 onboard.py meeting prep --days 7` |
| 更新 Person | `python3 onboard.py people upsert --name "Example Person" --external-id "mock:p1"` |
| 检查并恢复中断写入 | `python3 onboard.py doctor` / `doctor --repair` |

将 `ONBOARD_WORKSPACE` 配置为真正允许的 Workspace 路径后，以上命令才会处理你自己的工作数据。`init` **不会**启用 Scheduler、Reminder、发送消息或外部 Connector。

## 三个 Skills 与 Templates

- [meeting-notes](skills/meeting-notes/SKILL.md)：手写 Notes / 合规 Transcript → 会后 Draft。
- [meeting-prep](skills/meeting-prep/SKILL.md)：Tasks / Events → 会前讨论提纲。
- [weekly-update](skills/weekly-update/SKILL.md)：Tasks / Events / Logs → 个人周复盘。

所有重复生成内容以 `templates/` 中的默认模板为基础。安装时可以在 Workspace 的 `templates/` 中放置同名文件来**覆盖默认版本**。下一次生成读最新模板，旧文档不覆盖。`## Action Items` 和 `- [ ]` 是 Meeting → Task 的稳定格式约定。

**注：** 三个 `SKILL.md` 是供获批准的 AI Agent 阅读的操作指令，并非本地 CLI 内置 LLM。CLI 的 Meeting Prep 只有确定性事实提取，不会编造未记录的理由或影响。

## Project B 的当前边界

`sync import` 只读取用户明确给出的 Mock/JSON 文件，把建议放入本地 Review Queue，**不会自动访问真实 Email/DM，也不会根据文件中自称的可信度直接修改 Tasks/People**。执行 `review approve` 才会写入 Project A。其他外部 MCP、轻量定时增量检查和重要 Alerts 留给内部 Setup；默认全部禁用。

## Specs 与验证

- [Project A](specs/A-hub.md) · [Project B](specs/B-navigator.md) · [Project C](specs/C-skills.md)
- [安全与首次配置](specs/setup-and-safety.md)
- 测试：`python3 -m unittest discover -s tests -v`

MVP 不包含真实 Connectors、Always-on Agent、Dashboard、录音采集、企业授权或通知派送。这些不是缺失的安装步骤，而是刻意留到内部部署确认的 Extension Points。
