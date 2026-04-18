import unittest
import os
import shutil
import tempfile
from tasks_ai.cli import TasksCLI


class TestSecurity(unittest.TestCase):
    def setUp(self):
        import sys

        sys._called_from_test = True  # type: ignore[attr-defined]
        self.tmp_dir = tempfile.mkdtemp()
        # Mock git root
        self.old_cwd = os.getcwd()
        os.chdir(self.tmp_dir)
        import subprocess

        subprocess.run(["git", "init"], capture_output=True)
        self.cli = TasksCLI(quiet=True)
        self.cli.init()

    def tearDown(self):
        os.chdir(self.old_cwd)
        shutil.rmtree(self.tmp_dir)

    def test_directory_traversal(self):
        # Try to find a task outside the tasks directory
        path, state = self.cli.find_task("../../../etc/passwd")
        self.assertIsNone(path)

        # Try with a valid-looking name but traversal content
        path, state = self.cli.find_task(".._.._etc_passwd")
        self.assertIsNone(path)

    def test_invalid_task_ids(self):
        # Test suspicious characters
        invalid_ids = [
            "1; rm -rf /",
            "task' OR '1'='1",
            "$(whoami)",
            "task\nnewline",
            "task\0null",
        ]
        for tid in invalid_ids:
            path, state = self.cli.find_task(tid)
            self.assertIsNone(path, f"ID '{tid}' should be rejected")

    def test_id_cleaning_on_create(self):
        # Create a task with weird characters
        self.cli.create(
            "Task with <script>alert(1)</script>",
            story="...",
            tech="...",
            criteria="...",
            plan="...",
        )

        # Check generated ID in backlog
        backlog = os.path.join(self.cli.tasks_path, "backlog")
        items = os.listdir(backlog)
        task_dir = next(item for item in items if "script" in item)

        # Should be something like "1-task-task-with-script-alert-1-scrip"
        self.assertFalse("<" in task_dir)
        self.assertFalse(">" in task_dir)
        self.assertFalse("(" in task_dir)
        self.assertFalse(")" in task_dir)
        self.assertTrue(task_dir.startswith("1-task-task-with-script-alert-1-"))


if __name__ == "__main__":
    unittest.main()
