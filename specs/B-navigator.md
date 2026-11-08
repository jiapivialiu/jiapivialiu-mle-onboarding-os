# Project B — Onboarding Navigator

### 4.1 已确定的处理策略

- **Scheduled + On-demand**；但所有 Schedule 初始均**关闭**。
- **MCP-first**：先调查可用的企业批准 MCP / AI Client；Public Repo 不绑定 App、模型或 Provider。初期只提供通用 JSON Contract 和 Mock/File Intake，不预装真实 Connector。
- **Tiered Auto-processing**：确定性且可信的结构化事实可更新 A；自然语言推断、冲突、身份不确定项进入 Review Queue。
- **Metadata + Short Summary + Source Reference**，不默认归档全文或音频。
- **Action + Context Digest**，简洁且只显示非空 Section；附 Source Links 与数据新鲜度。
- **Digest + Important Alerts**，不对所有普通消息发通知。

### 4.2 Source 与 Review 数据契约

MVP Mock/File Source Record 至少包含 `source_id`、`source_type`、`source_ref`、`observed_at`、`summary`、`kind` 和可选的 `data`。未来 Connector 可补充 `connector_type`、`external_id`、`retrieved_at`、`related_ids`；需附可审计来源，不把模型猜测伪装成原始事实。来自 File Input 的记录均作为未验证建议进入 Review Queue。

`review_queue.json` 记录待审信息的 ID、类别、变更建议、来源、理由、状态（`pending|approved|dismissed`）和时间。人工确认后通过 A 的 CLI 写入；重复输入只产生同一建议。

正式待办、明确 Calendar Metadata 和稳定人员基础资料可在规则和权限允许时自动同步。潜在 Task、推断 Deadline / Priority、Project 合作关系和冲突数据需要确认。外部消息发送、删除、更新 HR 系统等写操作默认禁止。

### 4.3 Lightweight Schedule 与 Sync Health

安装后**仅考虑**两项默认候选：

1. Email 新邮件/重要变化的 Delta Check。
2. Messaging Direct Messages 的 Delta Check。

其余 Docs、Calendar、Issue Tracker 等初期以 On-demand 为主；需要持续性且获批准时才添加独立轻量任务。无全量历史反复扫描、无 Always-on 进程、无自动扩大数据源范围；每次运行应有数量/时间上限。

各数据源独立保存 Checkpoint、`last_success_at`、状态、错误摘要和待补同步窗口。Checkpoint 仅在处理结果可靠落盘后推进。电脑关机/断网后在下一次运行时有限 Catch-up；重复数据按稳定 Source ID 与版本去重。

**Limited Retry + Catch-up**：网络超时/短暂服务端错误最多额外重试 2 次；429 遵守 `Retry-After`；Auth/Permission Error 不无意义重试；Partial Failure 需逐源报告。即使通知渠道失效，也应在 Sync Health 中显示未送达错误，不能声称已通知。

### 4.4 Digest、Alerts、Transcript

`daily-digest.md` 默认仅 3 个 Section：**Actions**（任务、Deadline、待确认）、**Context**（重要讨论/文档/联系人，附来源）、**System Status**（同步情况/异常）。成功且无变化时简短表示；同步失败时必须注明结果不完整。

重要 Alert 由规则决定（可信 Deadline、必要人工审核、连续 Sync Failure、Auth Required 等），而不是仅凭 LLM 的主观紧急程度。去重及通知冷却时间在部署配置中确认。

会议资料可来自人工笔记、获授权的原生 Transcript 或批准的本地 ASR；不自行绕过录音限制。B 仅接收/验证输入，C 生成 Notes Draft，A 保存经确认的 Notes 与 Tasks。音频/Transcript 的采集、储存、转录和删除遵守部署环境政策。
