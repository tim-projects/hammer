"""User tests for task 366 and 374: 'tasks show --all' outputs all data, scoped to one task.

These drive the hammer CLI the way a user does, in the --dev fixture repo:
'tasks show <id> --all' must dump that task's metadata beside every .md file,
'-j' must emit the same record as JSON, a bare 'tasks show --all' must list
every task, and plain 'tasks show <id>' must keep focusing on a single task.
"""

import json
import subprocess

from tests.hammer_test_base import HammerTestBase

STORY = "Sufficiently long story content here to pass validation"
TECH = "Sufficiently long technical description here to pass validation"
CRITERIA = "Sufficiently long acceptance criteria here to pass validation"
PLAN = "Sufficiently long planning details here to pass validation"


class ShowAllTest(HammerTestBase):
    def create_task(self, title):
        result = self.run_tasks(
            [
                "create",
                title,
                "--story",
                STORY,
                "--tech",
                TECH,
                "--criteria",
                CRITERIA,
                "--plan",
                PLAN,
            ]
        )
        self.assertEqual(result.returncode, 0, f"create failed: {result.stdout}")
        return json.loads(result.stdout)["data"]["file"]

    def test_all_with_an_id_dumps_that_task_only(self):
        name = self.create_task("Show all flag json test task one")
        self.create_task("Show all flag json test task two")

        result = self.run_tasks(["show", name.split("-")[0], "--all"])
        self.assertEqual(result.returncode, 0, result.stderr)
        record = json.loads(result.stdout)["data"]

        self.assertEqual(record["name"], name)
        self.assertEqual(record["state"], "BACKLOG")
        self.assertEqual(
            record["metadata"]["Title"], "Show all flag json test task one"
        )
        for part in ("story", "tech", "criteria", "plan"):
            self.assertIn(part, record["files"])
        self.assertEqual(record["files"]["story"].strip(), STORY)
        self.assertNotIn("verification_proof.log", record["files"])

    def test_all_with_an_id_text_lists_every_md_file(self):
        name = self.create_task("Show all flag text test task")

        result = subprocess.run(
            [self.script_path, "tasks", "--dev", "show", name.split("-")[0], "--all"],
            cwd=self.repo_path,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

        self.assertIn(name, result.stdout)
        self.assertIn(STORY, result.stdout)
        for part in ("story", "tech", "criteria", "plan"):
            self.assertIn(f"## {part}", result.stdout)

    def test_all_without_an_id_still_lists_every_task(self):
        first = self.create_task("Show all flag every task one")
        second = self.create_task("Show all flag every task two")

        result = self.run_tasks(["show", "--all"])
        self.assertEqual(result.returncode, 0, result.stderr)
        names = {r["name"] for r in json.loads(result.stdout)["data"]}

        self.assertIn(first, names)
        self.assertIn(second, names)

    def test_single_task_still_focuses_on_one_task(self):
        name = self.create_task("Show all flag single task test")

        result = subprocess.run(
            [self.script_path, "tasks", "--dev", "show", name.split("-")[0]],
            cwd=self.repo_path,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

        self.assertIn(name, result.stdout)
        self.assertIn(STORY, result.stdout)

    def test_help_documents_all(self):
        result = subprocess.run(
            [self.script_path, "tasks", "show", "--help"],
            cwd=self.repo_path,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("--all", result.stdout)
