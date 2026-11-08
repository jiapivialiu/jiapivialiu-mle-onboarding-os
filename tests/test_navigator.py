from pathlib import Path
from tempfile import TemporaryDirectory
import json
import unittest
from hub.store import init_workspace, list_tasks
from hub.templates import REPO
from navigator.pipeline import import_file, list_review, decide, digest
from navigator.sync import get_state, retry_transient


class NavigatorTests(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.ws = Path(self.tmp.name) / "ws"
        init_workspace(self.ws, REPO)
        self.file = REPO / "examples" / "synthetic-source-records.json"

    def tearDown(self):
        self.tmp.cleanup()

    def test_intake_review_idempotent(self):
        first = import_file(self.ws, self.file, "mock")
        self.assertEqual(first["new"], 3)
        self.assertEqual(len(list_tasks(self.ws)), 0)  # Never auto-write from untrusted mock input.
        second = import_file(self.ws, self.file, "mock")
        self.assertEqual(second["unchanged"], 3)
        self.assertEqual(len(list_review(self.ws)), 3)
        task_item = next(x for x in list_review(self.ws) if x["kind"] == "task")
        action = decide(self.ws, task_item["id"], True)
        self.assertEqual(action["status"], "approved")
        self.assertEqual(len(list_tasks(self.ws)), 1)
        self.assertEqual(get_state(self.ws)["sources"]["mock"]["status"], "success")
        out = digest(self.ws)
        self.assertTrue(Path(out["path"]).exists())

    def test_retry_limited(self):
        count = 0
        def temporary_failure():
            nonlocal count
            count += 1
            if count < 3:
                raise TimeoutError("temporary")
            return "recovered"
        self.assertEqual(retry_transient(temporary_failure, sleep=lambda _: None), "recovered")
        self.assertEqual(count, 3)

    def test_invalid_input_does_not_advance_checkpoint(self):
        broken = self.ws / "broken.json"
        broken.write_text(json.dumps([{"source_id": "x", "kind": "task"}]), encoding="utf-8")
        with self.assertRaises(Exception):
            import_file(self.ws, broken, "broken")
        source = get_state(self.ws)["sources"]["broken"]
        self.assertEqual(source["status"], "failed")
        self.assertNotIn("checkpoint", source)
