"""Small safe Markdown template renderer. Unknown variables are errors."""
from __future__ import annotations
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
import re
from .store import HubError, events, list_tasks

REPO = Path(__file__).resolve().parents[1]
VARIABLES = re.compile(r"{{\s*([a-z][a-z0-9_]*)\s*}}")


def render(workspace: Path, name: str, values: dict) -> str:
    if not re.fullmatch(r"[a-z0-9-]+", name):
        raise HubError("无效 Template 名称")
    custom = workspace / "templates" / f"{name}.md"
    default = REPO / "templates" / f"{name}.md"
    path = custom if custom.exists() else default
    if not path.exists():
        raise HubError(f"未找到 Template: {name}")
    content = path.read_text(encoding="utf-8")
    missing = set(VARIABLES.findall(content)) - values.keys()
    if missing:
        raise HubError("Template 缺少变量: " + ", ".join(sorted(missing)))
    return VARIABLES.sub(lambda match: str(values[match.group(1)]), content)


def save_draft(workspace: Path, directory: str, stem: str, content: str) -> Path:
    if directory not in {"meetings", "preps", "logs", "digests"}:
        raise HubError("不允许的输出目录")
    output = (workspace / directory / f"{stem}.md").resolve()
    if workspace.resolve() not in output.parents:
        raise HubError("输出文件必须在 Workspace 内")
    output.parent.mkdir(parents=True, exist_ok=True)
    try:
        with output.open("x", encoding="utf-8") as f:
            f.write(content)
    except FileExistsError as exc:
        raise HubError(f"文件已存在，拒绝覆盖: {output}") from exc
    return output


def slug(value: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9]+", "-", value.lower()).strip("-")
    return s[:42] or "meeting"


def meeting_actions(path: Path) -> list[str]:
    if not path.exists():
        raise HubError(f"Meeting Note 不存在: {path}")
    text = path.read_text(encoding="utf-8")
    result, active = [], False
    for line in text.splitlines():
        if re.match(r"^#{1,6}\s+", line):
            active = bool(re.match(r"^##\s+Action Items\s*$", line.strip(), re.I))
            continue
        if active:
            m = re.match(r"^\s*-\s*\[\s\]\s+(.+?)\s*$", line)
            if m:
                result.append(m.group(1))
    return result


def prep_values(workspace: Path, days: int, title: str) -> dict:
    if days < 1 or days > 366:
        raise HubError("--days 需要在 1–366 范围内")
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=days)
    tasks = list_tasks(workspace)
    done_ids = {e["task_id"] for e in events(workspace) if e.get("type") == "task_completed" and
                datetime.fromisoformat(e["occurred_at"].replace("Z", "+00:00")) >= start}
    progress = [f"- {t['title']} ({t['id']})" for t in tasks if t["id"] in done_ids and t["status"] == "done"]
    challenges = [f"- {t['title']} ({t['id']}): {t.get('challenge') or '原因待补充'}" for t in tasks if t["status"] == "blocked"]
    approach = [f"- {t['title']} ({t['id']}): {t.get('approach') or '方法待补充'}；原因：{t.get('rationale') or '待补充'}"
                for t in tasks if t.get("approach") or t.get("rationale")]
    next_steps = [f"- {t['title']} ({t['id']})" for t in tasks if t["status"] in {"todo", "in_progress"}][:12]
    return {"meeting_title": title, "meeting_date": date.today().isoformat(),
            "date_range": f"最近 {days} 天", "progress": "\n".join(progress) or "- 待补充",
            "challenges": "\n".join(challenges) or "- 无已记录 Blocker",
            "approaches": "\n".join(approach) or "- 待补充",
            "next_steps": "\n".join(next_steps) or "- 待补充",
            "long_term": "- 待补充", "questions": "- 待补充"}
