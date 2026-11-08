from pathlib import Path
from tempfile import TemporaryDirectory
import json
import unittest
from hub.store import (HubError, init_workspace, add_task, update_task, list_tasks, task_data,
                       events, upsert_person, people_data, doctor, atomic_json, now)
from hub.templates import render, save_draft, meeting_actions, prep_values, REPO


class HubTests(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.ws = Path(self.tmp.name) / "workspace"
        init_workspace(self.ws, REPO)

    def tearDown(self):
        self.tmp.cleanup()

    def test_init_is_idempotent_and_schedules_off(self):
        init_workspace(self.ws, REPO)
        config = json.loads((self.ws / "config.json").read_text())
        self.assertFalse(config["schedules_enabled"])
        self.assertFalse(config["notifications_enabled"])
        self.assertTrue(doctor(self.ws)["ok"])

    def test_tasks_json_and_event_history(self):
        task = add_task(self.ws, "Write sample notes", challenge="Need access")
        self.assertEqual(task["id"], "TASK-0001")
        update_task(self.ws, task["id"], {"status": "blocked"})
        update_task(self.ws, task["id"], {"status": "done"})
        self.assertEqual(len(events(self.ws)), 3)
        self.assertEqual(list_tasks(self.ws)[0]["status"], "done")
        update_task(self.ws, task["id"], {"status": "in_progress"})
        self.assertEqual(events(self.ws)[-1]["type"], "task_reopened")
        self.assertIsNone(list_tasks(self.ws)[0]["completed_at"])
        self.assertTrue(doctor(self.ws)["ok"])

    def test_reject_invalid_date(self):
        with self.assertRaises(HubError):
            add_task(self.ws, "Bad due", due_at="tomorrow")

    def test_template_override_no_overwrite(self):
        custom = self.ws / "templates" / "meeting-prep.md"
        custom.write_text("# Updated {{meeting_title}}\n{{progress}}", encoding="utf-8")
        self.assertTrue(render(self.ws, "meeting-prep", prep_values(self.ws, 7, "Demo")).startswith("# Updated Demo"))
        f = save_draft(self.ws, "preps", "snapshot", "old")
        with self.assertRaises(HubError):
            save_draft(self.ws, "preps", "snapshot", "new")
        self.assertEqual(f.read_text(), "old")
        custom.write_text("{{unexpected}}", encoding="utf-8")
        with self.assertRaises(HubError):
            render(self.ws, "meeting-prep", {})

    def test_meeting_actions_and_source_dedup(self):
        meeting = self.ws / "meetings" / "mock.md"
        meeting.write_text("# Meeting\n## Action Items\n- [ ] Prepare report\n- [x] Already done\n- [ ] Ask question\n## Other\n- [ ] Not parsed\n")
        self.assertEqual(meeting_actions(meeting), ["Prepare report", "Ask question"])
        add_task(self.ws, meeting_actions(meeting)[0], source_ref="meetings/mock.md#action-1")
        with self.assertRaises(HubError):
            add_task(self.ws, "duplicated", source_ref="meetings/mock.md#action-1")

    def test_people_stable_identifier(self):
        a = upsert_person(self.ws, display_name="Example Colleague", email="colleague@example.org", external_id="mock:42")
        b = upsert_person(self.ws, display_name="Example Colleague", email="colleague@example.org", external_id="mock:42", team="Sample Team")
        self.assertEqual(a["id"], b["id"])
        with self.assertRaises(HubError):
            upsert_person(self.ws, display_name="Example Colleague", email="conflict@example.org", external_id="mock:42")

    def test_pending_transaction_repair(self):
        task = add_task(self.ws, "recovery test")
        state = task_data(self.ws)
        state["tasks"][task["id"]]["status"] = "done"
        state["tasks"][task["id"]]["completed_at"] = now()
        entry = {"event_id": "EVT-simulated", "task_id": task["id"], "type": "task_completed", "occurred_at": now(), "to_status": "done"}
        atomic_json(self.ws / ".pending-task.json", {"state": state, "event": entry})
        self.assertFalse(doctor(self.ws)["ok"])
        self.assertTrue(doctor(self.ws, repair=True)["ok"])
        self.assertTrue(doctor(self.ws, repair=True)["ok"])
        self.assertEqual([x for x in events(self.ws) if x["event_id"] == "EVT-simulated"].__len__(), 1)
