"""Local data contract for the Hub. No network calls or model dependencies."""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
import fcntl
import json
import os
from pathlib import Path
import re
import tempfile
import uuid

SCHEMA_VERSION = "1.0"
STATUSES = {"todo", "in_progress", "blocked", "done", "cancelled"}
PRIORITIES = {"low", "medium", "high"}


class HubError(Exception):
    """Expected input/data error; suitable for a CLI error response."""


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def valid_time(value: str | None) -> bool:
    if value is None:
        return True
    try:
        if not isinstance(value, str) or not re.search(r"(Z|[+-]\d\d:\d\d)$", value):
            return False
        datetime.fromisoformat(value.replace("Z", "+00:00"))
        return True
    except ValueError:
        return False


def read_json(path: Path, default=None):
    if not path.exists():
        if default is not None:
            return default
        raise HubError(f"缺少数据文件: {path}")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise HubError(f"文件无法读取或不是合法 JSON: {path}: {exc}") from exc


def atomic_json(path: Path, value: object):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".new-", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(value, f, ensure_ascii=False, indent=2, sort_keys=True)
            f.write("\n")
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


@contextmanager
def lock(workspace: Path):
    workspace.mkdir(parents=True, exist_ok=True)
    with (workspace / ".store.lock").open("a+") as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)


def workspace_path(path: str | Path | None = None) -> Path:
    raw = path or os.environ.get("ONBOARD_WORKSPACE")
    if not raw:
        raise HubError("请用 --workspace PATH 或 ONBOARD_WORKSPACE 指定独立 Workspace")
    return Path(raw).expanduser().resolve()


def init_workspace(workspace: Path, repo: Path):
    if workspace == repo.resolve() or repo.resolve() in workspace.parents:
        raise HubError("Workspace 不能位于代码 Repo 内，请选择独立的安全目录")
    with lock(workspace):
        defaults = {
            "tasks.json": {"schema_version": SCHEMA_VERSION, "updated_at": now(), "tasks": {}},
            "people.json": {"schema_version": SCHEMA_VERSION, "updated_at": now(), "people": {}},
            "review_queue.json": {"schema_version": SCHEMA_VERSION, "items": {}},
            "sync_state.json": {"schema_version": SCHEMA_VERSION, "sources": {}, "seen": {}},
            "config.json": {"schema_version": SCHEMA_VERSION, "timezone": "UTC", "schedules_enabled": False, "notifications_enabled": False},
        }
        for filename, contents in defaults.items():
            if not (workspace / filename).exists():
                atomic_json(workspace / filename, contents)
        (workspace / "events.jsonl").touch(exist_ok=True)
        for directory in ("logs", "meetings", "preps", "people", "digests", "templates"):
            (workspace / directory).mkdir(exist_ok=True)
    return {"workspace": str(workspace), "initialized": True, "scheduled_tasks_enabled": False}


def validate_task(task: dict):
    if not isinstance(task, dict) or not isinstance(task.get("title"), str) or not task["title"].strip():
        raise HubError("Task title 不能为空")
    if task.get("status") not in STATUSES or task.get("priority") not in PRIORITIES:
        raise HubError("Task status 或 priority 非法")
    if not isinstance(task.get("tags"), list) or any(not isinstance(t, str) for t in task["tags"]):
        raise HubError("tags 必须为字符串数组")
    for key in ("created_at", "updated_at", "started_at", "completed_at", "due_at"):
        if not valid_time(task.get(key)):
            raise HubError(f"{key} 需要带时区的 RFC3339 Timestamp")
    for key in ("created_at", "updated_at"):
        if task.get(key) is None:
            raise HubError(f"Task 缺少 {key}")


def task_data(workspace: Path) -> dict:
    data = read_json(workspace / "tasks.json")
    if data.get("schema_version") != SCHEMA_VERSION or not isinstance(data.get("tasks"), dict):
        raise HubError("tasks.json 版本或结构错误")
    for key, task in data["tasks"].items():
        if not re.fullmatch(r"TASK-\d{4,}", key):
            raise HubError(f"非法 Task ID: {key}")
        validate_task(task)
    return data


def events(workspace: Path) -> list[dict]:
    result = []
    path = workspace / "events.jsonl"
    if not path.exists():
        raise HubError("缺少 events.jsonl")
    for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if line.strip():
            try:
                entry = json.loads(line)
                if not isinstance(entry, dict) or not entry.get("event_id") or not entry.get("task_id"):
                    raise ValueError("event 缺少必需字段")
                result.append(entry)
            except (json.JSONDecodeError, ValueError) as exc:
                raise HubError(f"events.jsonl 第 {i} 行非法: {exc}") from exc
    return result


def _commit_task(workspace: Path, state: dict, entry: dict):
    """Crash-recoverable two-file write, serialized by lock."""
    journal = workspace / ".pending-task.json"
    if journal.exists():
        raise HubError("发现未完成的 Task 写入；请先运行 onboard doctor --repair")
    atomic_json(journal, {"state": state, "event": entry})
    atomic_json(workspace / "tasks.json", state)
    _append_event_if_missing(workspace, entry)
    journal.unlink()


def _append_event_if_missing(workspace: Path, entry: dict):
    if any(e["event_id"] == entry["event_id"] for e in events(workspace)):
        return
    with (workspace / "events.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False, sort_keys=True) + "\n")
        f.flush()
        os.fsync(f.fileno())


def _event(task_id: str, kind: str, before, after) -> dict:
    return {"event_id": "EVT-" + uuid.uuid4().hex[:16], "task_id": task_id, "type": kind,
            "occurred_at": now(), "from_status": before, "to_status": after}


def add_task(workspace: Path, title: str, **kwargs) -> dict:
    with lock(workspace):
        data = task_data(workspace)
        nums = [int(x[5:]) for x in data["tasks"]]
        key = f"TASK-{max(nums, default=0) + 1:04d}"
        ts = now()
        task = {"title": title, "status": "todo", "priority": "medium", "tags": [],
                "created_at": ts, "updated_at": ts, "started_at": None, "completed_at": None,
                "due_at": None, "challenge": None, "approach": None, "rationale": None,
                "notes": "", "source_ref": None}
        for field, value in kwargs.items():
            if field not in task or field in {"created_at", "updated_at", "started_at", "completed_at"}:
                raise HubError(f"不可设置 Task 字段: {field}")
            task[field] = value
        validate_task(task)
        if task["source_ref"] and any(t.get("source_ref") == task["source_ref"] for t in data["tasks"].values()):
            raise HubError("该来源已创建过 Task，拒绝重复导入")
        data["tasks"][key] = task
        data["updated_at"] = ts
        _commit_task(workspace, data, _event(key, "task_created", None, "todo"))
        return {"id": key, **task}


def update_task(workspace: Path, task_id: str, changes: dict) -> dict:
    ALLOWED = {"title", "status", "priority", "tags", "due_at", "challenge", "approach", "rationale", "notes"}
    if not changes or not set(changes) <= ALLOWED:
        raise HubError("更新字段为空或包含不可更新字段")
    with lock(workspace):
        data = task_data(workspace)
        if task_id not in data["tasks"]:
            raise HubError(f"Task 不存在: {task_id}")
        task = data["tasks"][task_id]
        before = task["status"]
        for k, value in changes.items():
            task[k] = value
        after = task["status"]
        if after != before:
            if after == "in_progress" and task["started_at"] is None:
                task["started_at"] = now()
            task["completed_at"] = now() if after == "done" else None
        task["updated_at"] = now()
        validate_task(task)
        data["updated_at"] = task["updated_at"]
        if after != before:
            kind = "task_reopened" if before == "done" else ("task_completed" if after == "done" else "status_changed")
            _commit_task(workspace, data, _event(task_id, kind, before, after))
        else:
            atomic_json(workspace / "tasks.json", data)
        return {"id": task_id, **task}


def list_tasks(workspace: Path, status=None, tag=None, overdue=False) -> list[dict]:
    current = datetime.now(timezone.utc)
    result = []
    for key, task in task_data(workspace)["tasks"].items():
        if status and task["status"] != status:
            continue
        if tag and tag not in task.get("tags", []):
            continue
        if overdue:
            due = task.get("due_at")
            if task["status"] in ("done", "cancelled") or not due or datetime.fromisoformat(due.replace("Z", "+00:00")) >= current:
                continue
        result.append({"id": key, **task})
    return sorted(result, key=lambda x: (x.get("due_at") or "9999", x["id"]))


def people_data(workspace: Path):
    data = read_json(workspace / "people.json")
    if data.get("schema_version") != SCHEMA_VERSION or not isinstance(data.get("people"), dict):
        raise HubError("people.json 结构或版本错误")
    return data


def upsert_person(workspace: Path, *, display_name: str, email=None, role=None, team=None, external_id=None, source_ref=None) -> dict:
    if not display_name.strip():
        raise HubError("display_name 不能为空")
    with lock(workspace):
        data = people_data(workspace)
        people = data["people"]
        if external_id:
            matches = [k for k, p in people.items() if external_id in p.get("external_ids", [])]
        elif email:
            matches = [k for k, p in people.items() if p.get("email") == email]
        else:
            matches = []  # Do not merge on names alone.
        if len(matches) > 1:
            raise HubError("联系人身份冲突，请人工确认")
        if matches:
            key = matches[0]
            record = people[key]
            if external_id and record.get("email") and email and record["email"] != email:
                raise HubError("稳定 ID 的邮箱冲突，请人工确认")
        else:
            nums = [int(k[7:]) for k in people if re.fullmatch(r"PERSON-\d+", k)]
            key = f"PERSON-{max(nums, default=0) + 1:04d}"
            record = {"display_name": display_name, "email": None, "role": None, "team": None,
                      "external_ids": [], "related_projects": [], "source_refs": [],
                      "last_interaction_at": None, "updated_at": now()}
        record["display_name"] = display_name
        for k, v in (("email", email), ("role", role), ("team", team)):
            if v is not None:
                record[k] = v
        if external_id and external_id not in record["external_ids"]:
            record["external_ids"].append(external_id)
        if source_ref and source_ref not in record["source_refs"]:
            record["source_refs"].append(source_ref)
        record["updated_at"] = now()
        people[key] = record
        data["updated_at"] = now()
        atomic_json(workspace / "people.json", data)
        return {"id": key, **record}


def doctor(workspace: Path, repair=False) -> dict:
    problems = []
    with lock(workspace):
        journal = workspace / ".pending-task.json"
        if journal.exists():
            if repair:
                pending = read_json(journal)
                atomic_json(workspace / "tasks.json", pending["state"])
                _append_event_if_missing(workspace, pending["event"])
                journal.unlink()
            else:
                problems.append("有未完成的 Task 写入，执行 doctor --repair 恢复")
        for filename in ("config.json", "review_queue.json", "sync_state.json"):
            try:
                read_json(workspace / filename)
            except HubError as exc:
                problems.append(str(exc))
        for fn in (lambda: task_data(workspace), lambda: people_data(workspace), lambda: events(workspace)):
            try:
                fn()
            except HubError as exc:
                problems.append(str(exc))
        try:
            history = events(workspace)
            ids = [e["event_id"] for e in history]
            if len(ids) != len(set(ids)):
                problems.append("events.jsonl 中有重复 Event ID")
            latest = {}
            for event in history:
                latest[event["task_id"]] = event
            for task_id, task in task_data(workspace)["tasks"].items():
                last = latest.get(task_id)
                if last is None or last.get("to_status") != task["status"]:
                    problems.append(f"{task_id}: Task Status 与 Event History 不一致")
        except HubError:
            pass
    return {"ok": not problems, "problems": problems, "workspace": str(workspace)}
