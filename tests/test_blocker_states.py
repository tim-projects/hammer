import json
import os
import shutil
import unittest

from hammer_test_base import HammerTestBase

STORY = "Sufficiently long story content here to pass validation"
TECH = "Sufficiently long technical description here to pass validation"
CRITERIA = "Sufficiently long acceptance criteria here to pass validation"
PLAN = "Sufficiently long planning details here to pass validation"
BASE_ID = 9200


class BlockerStateTestBase(HammerTestBase):
    def setUp(self):
        super().setUp()
        for rel in ("hammer", "tasks.py"):
            shutil.copy2(
                os.path.join(os.getcwd(), rel), os.path.join(self.repo_path, rel)
            )
        for rel in ("tasks_ai", "data"):
            source = os.path.join(os.getcwd(), rel)
            target = os.path.join(self.repo_path, rel)
            shutil.rmtree(target, ignore_errors=True)
            shutil.copytree(
                source, target, ignore=shutil.ignore_patterns("__pycache__")
            )

    def create_task(self, counter_value, title):
        counter = os.path.join(self.dev_tasks_dir, ".task_counter")
        with open(counter, "w") as handle:
            handle.write(str(counter_value))
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
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return json.loads(result.stdout)["data"]

    def task_path(self, task_file):
        for dirpath, _, filenames in os.walk(self.dev_tasks_dir):
            if os.path.basename(dirpath) == task_file and "meta.json" in filenames:
                return dirpath
        raise AssertionError(f"task directory not found: {task_file}")

    def place_blocker(self, task_file, state):
        source = self.task_path(task_file)
        target = os.path.join(self.dev_tasks_dir, state.lower(), task_file)
        os.makedirs(os.path.dirname(target), exist_ok=True)
        shutil.move(source, target)

    def prepare_blocked_task(self):
        blocked = self.create_task(BASE_ID, "Blocker State Blocked Task")
        blocker = self.create_task(BASE_ID + 2, "Blocker State Completion Task")
        link = self.run_tasks(["link", blocked["file"], blocker["file"]])
        self.assertEqual(link.returncode, 0, link.stdout + link.stderr)
        ready = self.run_tasks(["move", blocked["file"], "READY"])
        self.assertEqual(ready.returncode, 0, ready.stdout + ready.stderr)
        research = self.run_tasks(
            [
                "modify",
                blocked["file"],
                "--research",
                "Reviewed the blocker gate and verified completion-state handling.",
            ]
        )
        self.assertEqual(research.returncode, 0, research.stdout + research.stderr)
        return blocked, blocker

    def enter_progressing(self, blocked_file):
        result = self.run_tasks(["move", blocked_file, "PROGRESSING"])
        return result, json.loads(result.stdout)


class TestBlockerCompletionStates(BlockerStateTestBase):
    def test_done_blocker_allows_progressing(self):
        blocked, blocker = self.prepare_blocked_task()
        self.place_blocker(blocker["file"], "DONE")

        result, payload = self.enter_progressing(blocked["file"])

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertTrue(payload["success"], payload)

    def test_archived_blocker_allows_progressing(self):
        blocked, blocker = self.prepare_blocked_task()
        self.place_blocker(blocker["file"], "ARCHIVED")

        result, payload = self.enter_progressing(blocked["file"])

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertTrue(payload["success"], payload)

    def test_incomplete_blocker_blocks_progressing_with_guidance(self):
        blocked, blocker = self.prepare_blocked_task()
        self.place_blocker(blocker["file"], "BACKLOG")

        result, payload = self.enter_progressing(blocked["file"])

        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertFalse(payload["success"], payload)
        self.assertIn("Blocker must be DONE or ARCHIVED first", payload["error"])
        self.assertIn("PROGRESSING stays blocked", payload["hint"])


if __name__ == "__main__":
    unittest.main()
