import json
import os
import tempfile
import unittest
from types import SimpleNamespace

from hammer_test_base import HammerTestBase
from tasks_ai.pipeline_hooks import ProgressUpdateHook, ValidationHook


class FakeWorktrees:
    def get_worktree_path(self, task_id):
        return "/tmp"


class FakeGit:
    def __init__(self):
        self.worktrees = FakeWorktrees()

    def get_default_branch(self):
        return None


class FakeCli:
    def __init__(self):
        self.validations = []
        self.errors = []
        self.git = FakeGit()

    def console(self, *args):
        pass

    def log(self, message):
        pass

    def error(self, message, **kwargs):
        self.errors.append(message)
        raise RuntimeError(message)

    def run_tool(self, tool_name=None, fix=False, cwd=None):
        self.validations.append(tool_name)

    def _atomic_write(self, path, task):
        pass


class TestRejectValidation(unittest.TestCase):
    def setUp(self):
        self.cli = FakeCli()
        self.task = SimpleNamespace(metadata={}, parts={})
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def test_progression_to_rejected_skips_code_validation(self):
        ValidationHook().execute(
            self.cli,
            self.task,
            "PROGRESSING",
            "REJECTED",
            self.tmp.name,
        )

        self.assertEqual(self.cli.validations, [])

    def test_testing_to_rejected_skips_code_validation(self):
        ValidationHook().execute(
            self.cli,
            self.task,
            "TESTING",
            "REJECTED",
            self.tmp.name,
        )

        self.assertEqual(self.cli.validations, [])

    def test_progression_to_rejected_skips_progress_update(self):
        ProgressUpdateHook().execute(
            self.cli,
            self.task,
            "PROGRESSING",
            "REJECTED",
            self.tmp.name,
        )

    def test_normal_promotion_still_requires_progress_update(self):
        with self.assertRaisesRegex(RuntimeError, "No progress tracking file found"):
            ProgressUpdateHook().execute(
                self.cli,
                self.task,
                "PROGRESSING",
                "TESTING",
                self.tmp.name,
            )

    def test_normal_promotion_still_runs_code_validation(self):
        for filename in ("criteria.md", "progress.md"):
            with open(os.path.join(self.tmp.name, filename), "w") as handle:
                handle.write("ok\n")

        ValidationHook().execute(
            self.cli,
            self.task,
            "PROGRESSING",
            "TESTING",
            self.tmp.name,
        )

        self.assertEqual(self.cli.validations, ["all"])


class TestRejectWithoutProgressFiles(HammerTestBase):
    def setUp(self):
        super().setUp()
        fixture_hammer = os.path.join(self.repo_path, "hammer")
        if os.path.lexists(fixture_hammer):
            os.remove(fixture_hammer)
        os.symlink(os.path.join(os.getcwd(), "hammer"), fixture_hammer)

    def test_progressing_task_can_be_rejected_without_progress_files(self):
        self.seed_counter(9100)
        created = self.run_tasks(
            [
                "create",
                "Reject task without progress files",
                "--story",
                "Sufficiently long story content here to pass validation",
                "--tech",
                "Sufficiently long technical description here to pass validation",
                "--criteria",
                "Sufficiently long acceptance criteria here to pass validation",
                "--plan",
                "Sufficiently long planning details here to pass validation",
            ]
        )
        data = json.loads(created.stdout)["data"]
        task_id = str(data["id"])
        task_file = data["file"]
        self.run_tasks(
            [
                "modify",
                task_id,
                "--research",
                "Read the progress update hook and rejection transition before testing.",
            ]
        )
        self.run_tasks(["move", task_id, "READY"])
        self.run_tasks(["move", task_id, "PROGRESSING"])

        task_dir = os.path.join(self.dev_tasks_dir, "progressing", task_file)
        for filename in ("progress.md", "current-task.md"):
            path = os.path.join(task_dir, filename)
            if os.path.exists(path):
                os.remove(path)

        result = self.run_tasks(["move", task_id, "REJECTED"])
        output = json.loads(result.stdout)
        self.assertTrue(output.get("success"), output)
        self.assertTrue(
            os.path.exists(os.path.join(self.dev_tasks_dir, "rejected", task_file))
        )


if __name__ == "__main__":
    unittest.main()
