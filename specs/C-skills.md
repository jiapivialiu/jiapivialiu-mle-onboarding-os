# Project C — Minimal Skills Library

只保留 3 个符合通用 Agent Skills 格式的 `SKILL.md`，不开发 Skill Framework，不调用固定厂商 API。每个文件尽量简短，仅写 `Inputs`、`Workflow`、`Output`、`Rules`；**输出格式引用 Project A 当前 Template，而非复制一套格式**。

| Skill | 输入 | 输出 / 约束 |
|---|---|---|
| `meeting-notes` | 手动 Notes、可选 Transcript | Decisions、Action Items、Open Questions；不编造 Owner/Deadline；生成 Draft，审核后才导入 Tasks |
| `meeting-prep` | Tasks、Events、过去 Meeting Notes | Progress、Challenges、Approach & Rationale、Next Steps、Questions；不能把推断当事实 |
| `weekly-update` | Tasks、Events、可选 Logs | 个人每周 Progress、Learnings、Challenges、Next Week；Impact 必须有证据 |

没有 AI 时，A 仍能从事实数据填充模板；有批准的 AI 后由 C 进行摘要与润色。30/60/90-day Review 先使用可编辑 Template，不新增第四个 Skill。
