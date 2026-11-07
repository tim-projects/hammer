import json
import os
import shutil
import subprocess
import tempfile
import unittest


class TestRobustnessBugfix(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        # Isolated dev store: the default /tmp/.tasks is shared by every dev
        # test in the suite, and one file's corrupted/created state can block
        # another file's create.
        self.dev_tasks_dir = tempfile.mkdtemp(prefix="hammer_tasks_")
        os.environ["HAMMER_DEV_TASKS_DIR"] = self.dev_tasks_dir
        self.repo_dir = os.path.join(self.test_dir, "repo")
        os.makedirs(self.repo_dir)
        subprocess.run(["git", "init"], cwd=self.repo_dir, capture_output=True)  # noqa: PLW1510
        subprocess.run(  # noqa: PLW1510
            ["git", "config", "user.email", "test@example.com"], cwd=self.repo_dir
        )
        subprocess.run(["git", "config", "user.name", "Test User"], cwd=self.repo_dir)  # noqa: PLW1510

        # Initialize tasks
        self.tasks_py = os.path.join(os.getcwd(), "tasks.py")
        import sys

        subprocess.run(  # noqa: PLW1510
            [sys.executable, self.tasks_py, "init"],
            cwd=self.repo_dir,
            capture_output=True,
        )

    def tearDown(self):
        shutil.rmtree(self.test_dir)
        shutil.rmtree(self.dev_tasks_dir, ignore_errors=True)
        shutil.rmtree(self.dev_tasks_dir + "-repo", ignore_errors=True)
        os.environ.pop("HAMMER_DEV_TASKS_DIR", None)

    def test_corrupted_meta_json_does_not_crash_cli(self):
        # Create a task
        import sys

        res = subprocess.run(  # noqa: PLW1510
            [
                sys.executable,
                self.tasks_py,
                "--dev",
                "-j",
                "create",
                "Valid Task Title",
                "--type",
                "task",
                "--story",
                "As a user I want to have a robust task manager",
                "--tech",
                "Technical details about robustness and error handling",
                "--criteria",
                "Acceptance criteria 1 must be satisfied by implementation",
                "--plan",
                "1. Implementation step one should be executed first",
            ],
            cwd=self.repo_dir,
            capture_output=True,
            text=True,
        )
        self.assertEqual(res.returncode, 0, res.stderr)

        # Corrupt the meta.json of the new task
        task_folder = json.loads(res.stdout)["data"]["path"]
        meta_path = os.path.join(self.repo_dir, task_folder, "meta.json")

        with open(meta_path, "w") as f:
            f.write("{ invalid json")

        # Run any tasks command, e.g., list
        import sys

        res = subprocess.run(  # noqa: PLW1510
            [sys.executable, self.tasks_py, "--dev", "-j", "list"],
            cwd=self.repo_dir,
            capture_output=True,
            text=True,
        )

        # Should NOT crash (returncode 0)
        self.assertEqual(
            res.returncode, 0, f"CLI crashed with corrupted meta.json: {res.stderr}"
        )

    def test_empty_meta_json_does_not_crash_cli(self):
        # Create a task
        import sys

        res = subprocess.run(  # noqa: PLW1510
            [
                sys.executable,
                self.tasks_py,
                "--dev",
                "-j",
                "create",
                "Another Task Title",
                "--type",
                "task",
                "--story",
                "As a user I want to have a robust task manager",
                "--tech",
                "Technical details about robustness and error handling",
                "--criteria",
                "Acceptance criteria 1 must be satisfied by implementation",
                "--plan",
                "1. Implementation step one should be executed first",
            ],
            cwd=self.repo_dir,
            capture_output=True,
            text=True,
        )
        self.assertEqual(res.returncode, 0, res.stderr)

        # Corrupt the meta.json of the new task (make it empty)
        task_folder = json.loads(res.stdout)["data"]["path"]
        meta_path = os.path.join(self.repo_dir, task_folder, "meta.json")

        with open(meta_path, "w") as f:
            f.write("")

        # Run any tasks command, e.g., list
        import sys

        res = subprocess.run(  # noqa: PLW1510
            [sys.executable, self.tasks_py, "--dev", "-j", "list"],
            cwd=self.repo_dir,
            capture_output=True,
            text=True,
        )

        # Should NOT crash
        self.assertEqual(
            res.returncode, 0, f"CLI crashed with empty meta.json: {res.stderr}"
        )
