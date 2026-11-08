import contextlib
import io
from pathlib import Path
from tempfile import TemporaryDirectory
import json
import unittest
from hub.cli import main


class CLITests(unittest.TestCase):
    def test_cli_roundtrip(self):
        with TemporaryDirectory() as folder:
            ws = str(Path(folder) / "ws")
            def run(*args):
                out, err = io.StringIO(), io.StringIO()
                with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                    code = main(["--workspace", ws, *args])
                return code, json.loads(out.getvalue() or err.getvalue())
            self.assertEqual(run("init")[0], 0)
            code, added = run("task", "add", "Review mock notes", "--json")
            self.assertEqual(code, 0)
            id_ = added["data"]["id"]
            self.assertEqual(run("task", "update", id_, "--status", "blocked")[0], 0)
            self.assertEqual(run("task", "done", id_)[0], 0)
            self.assertEqual(run("task", "list", "--json")[1]["data"][0]["status"], "done")
            self.assertEqual(run("doctor")[1]["data"]["ok"], True)
            self.assertEqual(run("task", "show", "TASK-9999")[0], 2)
