"""Mock/file intake: no external connectors, network calls or scheduled jobs."""
from __future__ import annotations
from datetime import date
import hashlib
import json
from pathlib import Path
import uuid
from hub.store import HubError, atomic_json, now, read_json, add_task, upsert_person, list_tasks, valid_time
from hub.templates import render, save_draft
from .sync import get_state, record_status

VALID_KINDS = {"task", "person", "context"}


def validate_record(record: dict):
    fields = ("source_id", "source_type", "source_ref", "observed_at", "summary", "kind")
    if not isinstance(record, dict) or any(not isinstance(record.get(k), str) or not record[k].strip() for k in fields):
        raise HubError("Source Record 缺少必需字符串字段")
    if not valid_time(record["observed_at"]):
        raise HubError("Source Record observed_at 必须是带时区 Timestamp")
    if record["kind"] not in VALID_KINDS:
        raise HubError("未知 Source Record kind")
    if not isinstance(record.get("data", {}), dict):
        raise HubError("Source Record data 必须为 Object")
    if record["kind"] == "task" and not record["data"].get("title"):
        raise HubError("Task Suggestion 缺少 title")
    if record["kind"] == "person" and not record["data"].get("display_name"):
        raise HubError("Person Suggestion 缺少 display_name")


def queue_data(workspace: Path):
    data = read_json(workspace / "review_queue.json")
    if not isinstance(data.get("items"), dict):
        raise HubError("review_queue.json 结构错误")
    return data


def import_file(workspace: Path, file: Path, source: str) -> dict:
    """Untrusted file input only creates local review suggestions, never writes A records."""
    if not source.strip():
        raise HubError("必须提供非空 --source")
    payload = read_json(file)
    if not isinstance(payload, list):
        raise HubError("Mock Input 必须是 JSON Array")
    state = get_state(workspace)
    queue = queue_data(workspace)
    counts = {"new": 0, "unchanged": 0, "changed": 0}
    try:
        # Validate entire batch before modifying state.
        for record in payload:
            validate_record(record)
        for record in payload:
            identity = source + ":" + record["source_id"]
            digest = hashlib.sha256(json.dumps(record, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()
            if state["seen"].get(identity) == digest:
                counts["unchanged"] += 1
                continue
            previous = identity in state["seen"]
            item_id = "REVIEW-" + hashlib.sha256(identity.encode()).hexdigest()[:12]
            queue["items"][item_id] = {"id": item_id, "kind": record["kind"],
                "status": "pending", "source": source, "source_id": record["source_id"],
                "source_ref": record["source_ref"], "summary": record["summary"],
                "observed_at": record["observed_at"], "proposal": record.get("data", {}),
                "updated_at": now()}
            state["seen"][identity] = digest
            counts["changed" if previous else "new"] += 1
        # Checkpoint moves only once the queue and state are committed.
        atomic_json(workspace / "review_queue.json", queue)
        atomic_json(workspace / "sync_state.json", state)
        record_status(workspace, source, "success", checkpoint=now())
        return {"source": source, "status": "success", **counts, "pending": len([x for x in queue["items"].values() if x["status"] == "pending"])}
    except Exception as exc:
        record_status(workspace, source, "failed", error=str(exc))
        raise


def list_review(workspace: Path, status=None):
    items = list(queue_data(workspace)["items"].values())
    return [x for x in items if status is None or x["status"] == status]


def decide(workspace: Path, item_id: str, approve: bool):
    queue = queue_data(workspace)
    item = queue["items"].get(item_id)
    if not item:
        raise HubError(f"Review Item 不存在: {item_id}")
    if item["status"] != "pending":
        raise HubError(f"Review Item 已处理: {item_id}")
    action = None
    if approve:
        data = item["proposal"]
        if item["kind"] == "task":
            ref = f"{item['source']}:{item['source_id']}"
            prior = next((t for t in list_tasks(workspace) if t.get("source_ref") == ref), None)
            action = prior or add_task(workspace, data["title"], source_ref=ref,
                                       notes=item.get("summary", ""))
        elif item["kind"] == "person":
            action = upsert_person(workspace, display_name=data["display_name"], email=data.get("email"),
                                   role=data.get("role"), team=data.get("team"),
                                   external_id=data.get("external_id"), source_ref=item["source_ref"])
        item["status"] = "approved"
    else:
        item["status"] = "dismissed"
    item["decided_at"] = now()
    queue["items"][item_id] = item
    atomic_json(workspace / "review_queue.json", queue)
    return {"id": item_id, "status": item["status"], "result": action}


def digest(workspace: Path):
    pending = list_review(workspace, "pending")
    source_state = get_state(workspace)["sources"]
    actions = [f"- [{item['kind']}] {item['summary']} ({item['id']})" for item in pending if item["kind"] != "context"]
    context = [f"- {item['summary']} ({item['source_ref']})" for item in pending if item["kind"] == "context"]
    status = [f"- {name}: {info.get('status', 'unknown')}" for name, info in sorted(source_state.items())]
    content = render(workspace, "daily-digest", {
        "date": date.today().isoformat(),
        "actions": "\n".join(actions) or "- No important updates",
        "context": "\n".join(context) or "- 无新增重要 Context",
        "system_status": "\n".join(status) or "- 尚未配置任何数据源",
    })
    stem = date.today().isoformat() + "-" + uuid.uuid4().hex[:8]
    return {"path": str(save_draft(workspace, "digests", stem, content)), "pending": len(pending)}
