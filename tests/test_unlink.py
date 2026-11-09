#!/usr/bin/env python3
"""User tests for `hammer tasks unlink` (task 316).

`unlink` is the removal counterpart of `link`: it must drop a blocker
relationship from the task's `Bl` metadata list without touching any task
data, no-op when the pair is not linked, and reject the same invalid inputs
`link` rejects. These tests drive the tool through the hammer CLI the way a
user does (HammerTestBase fixture with `--dev` storage).
"""

import json
import os
import shutil
import unittest

from tests.hammer_test_base import HammerTestBase

STORY = "Sufficiently long story content here to pass validation"
TECH = "Sufficiently long technical description here to pass validation"
CRITERIA = "Sufficiently long acceptance criteria here to pass validation"
PLAN = "Sufficiently long planning details here to pass validation"

# IDs above the real repo's highest task id -> no collision with fixture data.
BASE_ID = 9101


class UnlinkTestBase(HammerTestBase):
    def setUp(self):
        super().setUp()
        self._install_unlink_into_fixture()

    def _install_unlink_into_fixture(self):
        """The harness checks out `main`; install the branch's code as a whole.

        Copying individual files let the fixture mix main's commands with the
        branch's utils (ImportError: resolve_content), so the whole package and
        its data files move together or not at all.
        """
        for rel in ("hammer", "tasks.py"):
            shutil.copy2(
                os.path.join(os.getcwd(), rel), os.path.join(self.repo_path, rel)
            )
        for rel in ("tasks_ai", "data"):
            src = os.path.join(os.getcwd(), rel)
            dst = os.path.join(self.repo_path, rel)
            shutil.rmtree(dst, ignore_errors=True)
            shutil.copytree(src, dst, ignore=shutil.ignore_patterns("__pycache__"))
        self.script_path = os.path.join(self.repo_path, "hammer")

    def seed_counter(self, value):
        counter = os.path.join(self.dev_tasks_dir, ".task_counter")
        if os.path.exists(counter):
            os.remove(counter)
        with open(counter, "w") as handle:
            handle.write(str(value))

    def create_task(self, counter_value, title):
        self.seed_counter(counter_value)
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
        self.assertEqual(
            result.returncode, 0, f"create failed: {result.stdout} {result.stderr}"
        )
        payload = json.loads(result.stdout)
        return payload["data"]

    def metadata(self, task_file):
        """Load a task's meta.json from the dev storage, across all states."""
        tasks_root = self.dev_tasks_dir
        for dirpath, _, filenames in os.walk(tasks_root):
            if os.path.basename(dirpath) == task_file and "meta.json" in filenames:
                with open(os.path.join(dirpath, "meta.json")) as handle:
                    return json.load(handle)
        raise AssertionError(f"meta.json not found for {task_file} under {tasks_root}")


class TestTasksUnlink(UnlinkTestBase):
    def test_unlink_shows_in_help(self):
        result = self.run_tasks(["--help"])
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("unlink", result.stdout)

    def test_link_then_unlink_removes_blocker(self):
        blocked = self.create_task(BASE_ID, "Unlink Blocked Task Alpha")
        blocker = self.create_task(BASE_ID + 1, "Unlink Blocker Task Beta")
        blocked_file, blocker_file = blocked["file"], blocker["file"]

        link_res = json.loads(
            self.run_tasks(["link", blocked_file, blocker_file]).stdout
        )
        self.assertTrue(link_res["success"], link_res)
        blockers = self.metadata(blocked_file).get("Bl", [])
        self.assertIn(blocker_file, blockers)

        unlink_res = json.loads(
            self.run_tasks(["unlink", blocked_file, blocker_file]).stdout
        )
        self.assertTrue(unlink_res["success"], unlink_res)
        blockers = self.metadata(blocked_file).get("Bl", [])
        self.assertNotIn(blocker_file, blockers)

    def test_unlink_without_existing_link_is_noop(self):
        blocked = self.create_task(BASE_ID + 10, "Unlink Unlinked Task Alpha")
        blocker = self.create_task(BASE_ID + 11, "Unlink Unlinked Task Beta")

        result = json.loads(
            self.run_tasks(["unlink", blocked["file"], blocker["file"]]).stdout
        )
        self.assertTrue(result["success"], result)
        self.assertFalse(result["data"]["changed"], result)
        self.assertIn("Not linked", " ".join(result["messages"]), result["messages"])
        # The blocked task gains no phantom blocker entry.
        self.assertEqual(self.metadata(blocked["file"]).get("Bl", []), [])

    def test_double_unlink_is_noop(self):
        blocked = self.create_task(BASE_ID + 20, "Unlink Twice Task Alpha")
        blocker = self.create_task(BASE_ID + 21, "Unlink Twice Task Beta")
        blocked_file, blocker_file = blocked["file"], blocker["file"]

        self.run_tasks(["link", blocked_file, blocker_file])
        first = json.loads(
            self.run_tasks(["unlink", blocked_file, blocker_file]).stdout
        )
        self.assertTrue(first["success"], first)
        second = json.loads(
            self.run_tasks(["unlink", blocked_file, blocker_file]).stdout
        )
        self.assertTrue(second["success"], second)
        self.assertFalse(second["data"]["changed"], second)
        self.assertNotIn(blocker_file, self.metadata(blocked_file).get("Bl", []))

    def test_unlink_nonexistent_task_fails(self):
        blocked = self.create_task(BASE_ID + 30, "Unlink Ghost Blocker Task")
        result = self.run_tasks(["unlink", blocked["file"], "nonexistent-task-id"])
        self.assertNotEqual(result.returncode, 0, result.stdout)
        payload = json.loads(result.stdout)
        self.assertFalse(payload["success"], payload)

    def test_unlink_task_from_itself_fails(self):
        blocked = self.create_task(BASE_ID + 40, "Unlink Self Task")
        result = self.run_tasks(["unlink", blocked["file"], blocked["file"]])
        self.assertNotEqual(result.returncode, 0, result.stdout)
        payload = json.loads(result.stdout)
        self.assertFalse(payload["success"], payload)


if __name__ == "__main__":
    unittest.main()
