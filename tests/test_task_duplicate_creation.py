"""Task 501: duplicate task IDs are rejected before another ref is created."""

import json
import os
import subprocess

from tests.hammer_test_base import HammerTestBase, ensure_dev_repo

STORY = "Sufficiently long story content here to pass validation"
TECH = "Sufficiently long technical description here to pass validation"
CRITERIA = "Sufficiently long acceptance criteria here to pass validation"
PLAN = "Sufficiently long planning details here to pass validation"


class TaskDuplicateCreationTest(HammerTestBase):
    BASE_ID = 9200

    @property
    def dev_repo_dir(self):
        return ensure_dev_repo(self.dev_tasks_dir)

    def git(self, *args):
        return subprocess.run(
            ["git", *args],
            cwd=self.dev_repo_dir,
            capture_output=True,
            text=True,
            check=False,
        )

    def create_task(self):
        self.seed_task_id_floor(self.BASE_ID)
        result = self.run_tasks(
            [
                "create",
                "Duplicate task ID creation verification",
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
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return json.loads(result.stdout)["data"]

    def test_two_branches_one_id_are_refused_before_ref_creation(self):
        task = self.create_task()
        task_id = str(task["id"])
        first = f"{task_id}-task-alpha"
        second = f"{task_id}-issue-beta"
        self.git("branch", first)
        self.git("branch", second)

        mounted = self.run_tasks(["mount", task_id])

        self.assertEqual(mounted.returncode, 1, mounted.stdout + mounted.stderr)
        payload = json.loads(mounted.stdout)
        self.assertEqual(payload["error_code"], "TASK_ID_REF_EXISTS")
        self.assertIn(first, payload["error"])
        self.assertIn(second, payload["error"])
        self.assertFalse(
            os.path.exists(
                os.path.join(self.dev_repo_dir, ".task-worktrees", task["branch"])
            )
        )

        moved = self.run_tasks(["move", task_id, "READY"])
        self.assertEqual(moved.returncode, 1, moved.stdout + moved.stderr)
        gate_payload = json.loads(moved.stdout)
        self.assertIn("GUARD", gate_payload["error"])
        self.assertIn("duplicate", gate_payload["error"].lower())


if __name__ == "__main__":
    import unittest

    unittest.main()
