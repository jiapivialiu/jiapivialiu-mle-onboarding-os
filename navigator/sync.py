"""Per-source sync state and transient retry; scheduling is external and disabled."""
from __future__ import annotations
from datetime import datetime, timezone
from pathlib import Path
import time
from hub.store import HubError, atomic_json, now, read_json


def get_state(workspace: Path):
    data = read_json(workspace / "sync_state.json")
    if not isinstance(data.get("seen"), dict) or not isinstance(data.get("sources"), dict):
        raise HubError("sync_state.json 结构错误")
    return data


def retry_transient(call, attempts=3, sleep=time.sleep):
    if attempts < 1 or attempts > 3:
        raise HubError("Retry 总尝试次数必须在 1–3 次范围")
    for attempt in range(attempts):
        try:
            return call()
        except (TimeoutError, ConnectionError):
            if attempt == attempts - 1:
                raise
            sleep(0.2 * (2 ** attempt))


def record_status(workspace: Path, source: str, status: str, error=None, checkpoint=None):
    state = get_state(workspace)
    previous = state["sources"].get(source, {})
    previous.update({"last_attempt_at": now(), "status": status, "error": error})
    if status == "success":
        previous["last_success_at"] = now()
        if checkpoint is not None:
            previous["checkpoint"] = checkpoint
    state["sources"][source] = previous
    atomic_json(workspace / "sync_state.json", state)
    return previous


def stale_sources(workspace: Path, max_age_hours=48):
    result = []
    for name, source in get_state(workspace)["sources"].items():
        last = source.get("last_success_at")
        if not last or (datetime.now(timezone.utc) - datetime.fromisoformat(last.replace("Z", "+00:00"))).total_seconds() > max_age_hours * 3600:
            result.append(name)
    return result
