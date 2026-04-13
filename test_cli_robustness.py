#!/usr/bin/env python3
import os
import subprocess
import shutil
import tempfile
import unittest
import json
import sys


class TestCLIRobustness(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.repo_dir = os.path.join(self.test_dir, "repo")
        os.makedirs(self.repo_dir)
        subprocess.run(["git", "init"], cwd=self.repo_dir, capture_output=True)
        self.tasks_py = os.path.abspath("tasks.py")
        self.repo_py = os.path.abspath("repo.py")
        self.check_py = os.path.abspath("check.py")

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def test_tasks_no_command(self):
        """Running 'tasks' without any command should return non-zero and show usage."""
        result = subprocess.run(
            [sys.executable, self.tasks_py],
            cwd=self.repo_dir,
            capture_output=True,
            text=True,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("usage: tasks", result.stderr)

    def test_repo_no_command(self):
        """Running 'repo' without any command should show help."""
        result = subprocess.run(
            [sys.executable, self.repo_py],
            cwd=self.repo_dir,
            capture_output=True,
            text=True,
        )
        # repo.py currently returns 0 when showing help
        self.assertEqual(result.returncode, 0)
        self.assertIn("Usage: repo", result.stdout)

    def test_check_no_command(self):
        """Running 'check' without any command should return 1 and show usage."""
        result = subprocess.run(
            [sys.executable, self.check_py],
            cwd=self.repo_dir,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 1)
        self.assertIn("usage: check", result.stdout + result.stderr)

    def test_tasks_missing_tool(self):
        """Running a tool that is not configured or missing should fail."""
        # Initialize tasks first
        subprocess.run(
            [sys.executable, self.tasks_py, "init"],
            cwd=self.repo_dir,
            capture_output=True,
        )

        # Copy check.py to temp repo because TasksCLI.run_tool calls it
        shutil.copy(self.check_py, self.repo_dir)

        # Configure a tool that doesn't exist
        subprocess.run(
            [
                sys.executable,
                self.tasks_py,
                "config",
                "set",
                "repo.lint",
                "nonexistent-tool",
            ],
            cwd=self.repo_dir,
            capture_output=True,
        )

        # Run it
        result = subprocess.run(
            [sys.executable, self.tasks_py, "-j", "run", "lint"],
            cwd=self.repo_dir,
            capture_output=True,
            text=True,
        )
        res = json.loads(result.stdout)
        self.assertFalse(res["success"])
        self.assertIn("No lint tool configured", res["error"])

    def test_repo_validation_failure(self):
        """repo commit should fail if validation tools fail or are missing."""
        subprocess.run(
            [sys.executable, self.tasks_py, "init"],
            cwd=self.repo_dir,
            capture_output=True,
        )

        # Copy check.py to temp repo because repo.py calls it
        shutil.copy(self.check_py, self.repo_dir)

        # Configure a tool that is missing from PATH
        subprocess.run(
            [sys.executable, self.tasks_py, "config", "set", "repo.lint", "ruff"],
            cwd=self.repo_dir,
            capture_output=True,
        )

        # Ensure 'ruff' is definitely not found by overriding PATH or just relying on it missing
        # If ruff IS in the system path, this test might pass incorrectly.
        # But we want to see it fail if it's missing.

        # Create a change to commit
        with open(os.path.join(self.repo_dir, "change.txt"), "w") as f:
            f.write("change")

        # Run repo commit - should fail because ruff is missing (unless installed)
        # We can simulate failure by pointing to a non-existent command if needed
        subprocess.run(
            [
                sys.executable,
                self.tasks_py,
                "config",
                "set",
                "repo.lint",
                "missing-command",
            ],
            cwd=self.repo_dir,
            capture_output=True,
        )

        result = subprocess.run(
            [sys.executable, self.repo_py, "commit", "test commit"],
            cwd=self.repo_dir,
            capture_output=True,
            text=True,
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("failed", result.stdout + result.stderr)

    def test_create_validation_short_fields(self):
        """Task create should fail if fields are too short."""
        subprocess.run(
            [sys.executable, self.tasks_py, "init"],
            cwd=self.repo_dir,
            capture_output=True,
        )

        # Test with too short fields
        result = subprocess.run(
            [
                sys.executable,
                self.tasks_py,
                "create",
                "Valid Task Title Here",
                "--story",
                "Short",
                "--tech",
                "Short",
                "--criteria",
                "Short",
                "--plan",
                "Short",
            ],
            cwd=self.repo_dir,
            capture_output=True,
            text=True,
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("too short", result.stderr)

    def test_create_validation_missing_fields(self):
        """Task create should fail if required fields are missing."""
        subprocess.run(
            [sys.executable, self.tasks_py, "init"],
            cwd=self.repo_dir,
            capture_output=True,
        )

        # Test with missing fields
        result = subprocess.run(
            [
                sys.executable,
                self.tasks_py,
                "create",
                "Valid Task Title Here",
            ],
            cwd=self.repo_dir,
            capture_output=True,
            text=True,
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Missing required fields", result.stderr)


if __name__ == "__main__":
    unittest.main()
