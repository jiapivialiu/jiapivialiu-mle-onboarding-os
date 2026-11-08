"""CLI and machine-readable interface. Usage: onboard --workspace PATH <command>."""
from __future__ import annotations
import argparse
from datetime import date, datetime, timezone, timedelta
import json
import os
from pathlib import Path
import sys
from .store import (HubError, init_workspace, workspace_path, add_task, update_task,
                    task_data, list_tasks, events, upsert_person, people_data, doctor)
from .templates import (REPO, render, save_draft, meeting_actions, prep_values, slug)
from navigator.pipeline import import_file, list_review, decide, digest
from navigator.sync import get_state, stale_sources


def parser():
    p = argparse.ArgumentParser(prog="onboard", description="Local-first Onboarding OS")
    p.add_argument("--workspace", help="独立 Workspace 目录，或设置 ONBOARD_WORKSPACE")
    sub = p.add_subparsers(dest="command", required=True)
    sub.add_parser("init")
    sub.add_parser("today")
    doc = sub.add_parser("doctor")
    doc.add_argument("--repair", action="store_true", help="修复未完成的 Task 双文件写入")
    t = sub.add_parser("task")
    ts = t.add_subparsers(dest="task_command", required=True)
    add = ts.add_parser("add")
    add.add_argument("title", nargs="?")
    add.add_argument("--from-meeting")
    add.add_argument("--item", type=int)
    add.add_argument("--priority", choices=["low", "medium", "high"], default="medium")
    add.add_argument("--due-at")
    add.add_argument("--json", action="store_true")
    show = ts.add_parser("show")
    show.add_argument("id")
    show.add_argument("--json", action="store_true")
    ls = ts.add_parser("list")
    ls.add_argument("--status", choices=["todo", "in_progress", "blocked", "done", "cancelled"])
    ls.add_argument("--tag")
    ls.add_argument("--overdue", action="store_true")
    ls.add_argument("--json", action="store_true")
    up = ts.add_parser("update")
    up.add_argument("id")
    up.add_argument("--status", choices=["todo", "in_progress", "blocked", "done", "cancelled"])
    up.add_argument("--priority", choices=["low", "medium", "high"])
    up.add_argument("--title")
    up.add_argument("--due-at")
    up.add_argument("--clear-due", action="store_true")
    for key in ("challenge", "approach", "rationale", "notes"):
        up.add_argument("--" + key)
    up.add_argument("--json", action="store_true")
    done = ts.add_parser("done")
    done.add_argument("id")
    done.add_argument("--json", action="store_true")
    l = sub.add_parser("log")
    l.add_argument("which", choices=["today"])
    m = sub.add_parser("meeting")
    ms = m.add_subparsers(dest="meeting_command", required=True)
    new = ms.add_parser("new")
    new.add_argument("--title", default="New Meeting")
    new.add_argument("--date", default=None)
    acts = ms.add_parser("actions")
    acts.add_argument("file")
    acts.add_argument("--json", action="store_true")
    prep = ms.add_parser("prep")
    prep.add_argument("--title", default="Weekly 1:1")
    prep.add_argument("--days", type=int, default=7)
    pe = sub.add_parser("people")
    pes = pe.add_subparsers(dest="people_command", required=True)
    pel = pes.add_parser("list")
    pel.add_argument("--json", action="store_true")
    peu = pes.add_parser("upsert")
    peu.add_argument("--name", required=True)
    for key in ("email", "role", "team", "external-id", "source-ref"):
        peu.add_argument("--" + key)
    peu.add_argument("--json", action="store_true")
    sy = sub.add_parser("sync")
    sys = sy.add_subparsers(dest="sync_command", required=True)
    imp = sys.add_parser("import")
    imp.add_argument("--file", required=True)
    imp.add_argument("--source", required=True)
    sys.add_parser("status")
    sys.add_parser("digest")
    re = sub.add_parser("review")
    res = re.add_subparsers(dest="review_command", required=True)
    rel = res.add_parser("list")
    rel.add_argument("--status", choices=["pending", "approved", "dismissed"], default="pending")
    for c in ("approve", "dismiss"):
        rs = res.add_parser(c)
        rs.add_argument("id")
    return p


def safe_meeting_path(workspace: Path, raw: str) -> Path:
    candidate = Path(raw)
    candidate = (candidate if candidate.is_absolute() else workspace / "meetings" / candidate).resolve()
    if (workspace / "meetings").resolve() not in candidate.parents:
        raise HubError("Meeting Notes 必须位于 Workspace/meetings")
    return candidate


def execute(args):
    workspace = workspace_path(args.workspace)
    if args.command == "init":
        return init_workspace(workspace, REPO)
    if args.command == "doctor":
        output = doctor(workspace, repair=args.repair)
        if not output["ok"]:
            raise HubError("; ".join(output["problems"]))
        return output
    if args.command == "today":
        return {"open_tasks": [t for t in list_tasks(workspace) if t["status"] not in ("done", "cancelled")],
                "overdue": list_tasks(workspace, overdue=True)}
    if args.command == "task":
        cmd = args.task_command
        if cmd == "add":
            title, source_ref = args.title, None
            if args.from_meeting:
                if args.item is None:
                    raise HubError("--from-meeting 必须同时指定 --item N")
                file = safe_meeting_path(workspace, args.from_meeting)
                choices = meeting_actions(file)
                if args.item < 1 or args.item > len(choices):
                    raise HubError("Action Item 序号超出范围")
                title = title or choices[args.item - 1]
                source_ref = f"meetings/{file.name}#action-{args.item}"
            elif args.item is not None:
                raise HubError("--item 只能与 --from-meeting 一起使用")
            if not title:
                raise HubError("请提供 Task Title 或 Meeting Action Item")
            return add_task(workspace, title, source_ref=source_ref, priority=args.priority, due_at=args.due_at)
        if cmd == "list":
            return list_tasks(workspace, status=args.status, tag=args.tag, overdue=args.overdue)
        if cmd == "show":
            task = task_data(workspace)["tasks"].get(args.id)
            if task is None:
                raise HubError(f"Task 不存在: {args.id}")
            return {"id": args.id, **task}
        if cmd == "update":
            fields = ("status", "priority", "title", "challenge", "approach", "rationale", "notes")
            changes = {k: getattr(args, k) for k in fields if getattr(args, k) is not None}
            if args.clear_due and args.due_at:
                raise HubError("--due-at 和 --clear-due 不能同时使用")
            if args.clear_due:
                changes["due_at"] = None
            elif args.due_at:
                changes["due_at"] = args.due_at
            return update_task(workspace, args.id, changes)
        if cmd == "done":
            return update_task(workspace, args.id, {"status": "done"})
    if args.command == "log":
        today = date.today().isoformat()
        return {"path": str(save_draft(workspace, "logs", today, render(workspace, "daily-log", {"date": today})))}
    if args.command == "meeting":
        cmd = args.meeting_command
        if cmd == "new":
            day = args.date or date.today().isoformat()
            try:
                date.fromisoformat(day)
            except ValueError as exc:
                raise HubError("--date 必须为 YYYY-MM-DD") from exc
            body = render(workspace, "meeting-notes", {"meeting_title": args.title,
                "meeting_date": day, "participants": "待填写", "source_ref": "待填写"})
            return {"path": str(save_draft(workspace, "meetings", day + "-" + slug(args.title), body))}
        if cmd == "actions":
            file = safe_meeting_path(workspace, args.file)
            return [{"index": i, "title": t} for i, t in enumerate(meeting_actions(file), 1)]
        if cmd == "prep":
            body = render(workspace, "meeting-prep", prep_values(workspace, args.days, args.title))
            stem = date.today().isoformat() + "-" + slug(args.title) + "-" + datetime.now(timezone.utc).strftime("%H%M%S%f")
            return {"path": str(save_draft(workspace, "preps", stem, body))}
    if args.command == "people":
        if args.people_command == "list":
            return [{"id": k, **p} for k, p in people_data(workspace)["people"].items()]
        if args.people_command == "upsert":
            return upsert_person(workspace, display_name=args.name, email=args.email,
                role=args.role, team=args.team, external_id=args.external_id, source_ref=args.source_ref)
    if args.command == "sync":
        if args.sync_command == "import":
            return import_file(workspace, Path(args.file).expanduser(), args.source)
        if args.sync_command == "status":
            return {"sources": get_state(workspace)["sources"], "stale_sources": stale_sources(workspace)}
        if args.sync_command == "digest":
            return digest(workspace)
    if args.command == "review":
        if args.review_command == "list":
            return list_review(workspace, status=args.status)
        return decide(workspace, args.id, args.review_command == "approve")
    raise HubError("不支持的命令")


def main(argv=None) -> int:
    args = parser().parse_args(argv)
    json_output = getattr(args, "json", False)
    try:
        result = execute(args)
        if json_output or isinstance(result, (dict, list)):
            print(json.dumps({"status": "success", "data": result}, ensure_ascii=False, indent=2))
        else:
            print(result)
        return 0
    except (HubError, OSError, ValueError) as exc:
        print(json.dumps({"status": "failed", "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
