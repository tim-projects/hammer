import os
import subprocess
import shutil
import tempfile
import unittest
import json


class TestRobustnessBugfix(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.repo_dir = os.path.join(self.test_dir, "repo")
        os.makedirs(self.repo_dir)
        subprocess.run(["git", "init"], cwd=self.repo_dir, capture_output=True)
        subprocess.run(
            ["git", "config", "user.email", "test@example.com"], cwd=self.repo_dir
        )
        subprocess.run(["git", "config", "user.name", "Test User"], cwd=self.repo_dir)

        # Initialize tasks
        self.tasks_py = os.path.join(os.getcwd(), "tasks.py")
        subprocess.run(
            ["python", self.tasks_py, "init"], cwd=self.repo_dir, capture_output=True
        )

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def test_corrupted_meta_json_does_not_crash_cli(self):
        # Create a task
        res = subprocess.run(
            [
                "python",
                self.tasks_py,
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
        res = subprocess.run(
            ["python", self.tasks_py, "-j", "list"],
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
        res = subprocess.run(
            [
                "python",
                self.tasks_py,
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
        res = subprocess.run(
            ["python", self.tasks_py, "-j", "list"],
            cwd=self.repo_dir,
            capture_output=True,
            text=True,
        )

        # Should NOT crash
        self.assertEqual(
            res.returncode, 0, f"CLI crashed with empty meta.json: {res.stderr}"
        )


if __name__ == "__main__":
    unittest.main()
