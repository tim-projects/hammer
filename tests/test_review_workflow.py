#!/usr/bin/env python3
"""Test for the automated PR review workflow."""

import subprocess
import os
import shutil
import json
import unittest
import sys
import tempfile


class TestReviewWorkflow(unittest.TestCase):
    def setUp(self):
        self.dev_dir = "/tmp/.tasks"
        if os.path.exists(self.dev_dir):
            shutil.rmtree(self.dev_dir)

        self.script_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "tasks.py"
        )

        self.test_repo = tempfile.mkdtemp()
        self.root = self.test_repo
        self.old_cwd = os.getcwd()
        os.chdir(self.root)
        subprocess.run(["git", "init"], cwd=self.root, capture_output=True)
        subprocess.run(
            ["git", "config", "user.email", "test@example.com"],
            cwd=self.root,
            capture_output=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "Test User"],
            cwd=self.root,
            capture_output=True,
        )

        with open(os.path.join(self.root, "README.md"), "w") as f:
            f.write("# Test Repo")
        subprocess.run(["git", "add", "README.md"], cwd=self.root, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "Initial commit"],
            cwd=self.root,
            capture_output=True,
        )

    def tearDown(self):
        os.chdir(self.old_cwd)
        if os.path.exists(self.test_repo):
            shutil.rmtree(self.test_repo)

    def test_review_workflow(self):
        """Test the full review workflow: create -> progress -> testing -> review -> review command -> regression check -> staging."""
        # Init tasks
        res = subprocess.run(
            [sys.executable, self.script_path, "-j", "--dev", "init"],
            capture_output=True,
            text=True,
        )
        self.assertEqual(res.returncode, 0, f"Init failed: {res.stdout}")
        print("[TEST] Init succeeded")

        # Create task
        res = subprocess.run(
            [
                sys.executable,
                self.script_path,
                "-j",
                "--dev",
                "create",
                "Test Review Workflow Feature",
                "--story",
                "Test story for review workflow implementation",
                "--tech",
                "Test tech for review workflow",
                "--criteria",
                "Test criteria for review workflow",
                "--plan",
                "Test plan for review workflow",
            ],
            capture_output=True,
            text=True,
        )
        self.assertEqual(res.returncode, 0, f"Create failed: {res.stderr}")
        task_file = json.loads(res.stdout)["data"]["task_id"]
        print(f"[TEST] Created task: {task_file}")

        # Make some file changes to have a diff
        initial_branch = "main"
        with open(os.path.join(self.root, "test_file.py"), "w") as f:
            f.write("# Test file\nprint('hello')\n")
        subprocess.run(
            ["git", "add", "test_file.py"], cwd=self.root, capture_output=True
        )
        subprocess.run(
            ["git", "commit", "-m", "Add test file"],
            cwd=self.root,
            capture_output=True,
        )

        # Move to TESTING (needs tests passed)
        res = subprocess.run(
            [
                sys.executable,
                self.script_path,
                "-j",
                "--dev",
                "move",
                task_file,
                "READY,PROGRESSING,TESTING",
            ],
            capture_output=True,
            text=True,
        )
        self.assertEqual(res.returncode, 0, f"Move to TESTING failed: {res.stderr}")
        print("[TEST] Moved to TESTING")

        # Mark tests passed (required for REVIEW)
        res = subprocess.run(
            [
                sys.executable,
                self.script_path,
                "-j",
                "--dev",
                "modify",
                task_file,
                "--tests-passed",
            ],
            capture_output=True,
            text=True,
        )
        self.assertEqual(res.returncode, 0, f"Tests passed failed: {res.stderr}")
        print("[TEST] Tests passed marked")

        # Set up testing branch with commit
        subprocess.run(
            ["git", "checkout", "-b", "testing"], cwd=self.root, capture_output=True
        )
        subprocess.run(
            ["git", "merge", initial_branch], cwd=self.root, capture_output=True
        )
        subprocess.run(
            ["git", "checkout", initial_branch], cwd=self.root, capture_output=True
        )

        # Move to REVIEW
        res = subprocess.run(
            [
                sys.executable,
                self.script_path,
                "-j",
                "--dev",
                "move",
                task_file,
                "REVIEW",
            ],
            capture_output=True,
            text=True,
        )
        if res.returncode != 0:
            print(f"ERROR: {res.stderr}")
            print(f"STDOUT: {res.stdout}")
        self.assertEqual(res.returncode, 0, f"Move to REVIEW failed: {res.stderr}")
        print("[TEST] Moved to REVIEW")

        # Check diff summary exists
        task_basename = task_file.rsplit(".", 1)[0]
        summary_path = f"/tmp/.tasks/review/{task_basename}.summary"
        self.assertTrue(
            os.path.exists(summary_path), f"Summary not found: {summary_path}"
        )
        print("[TEST] Diff summary exists")

        # Check review summary content
        with open(summary_path) as f:
            content = f.read()
        print(f"[TEST] Summary content: {content[:200]}")
        self.assertIn("test_file.py", content)

        # Test review --list command
        res = subprocess.run(
            [
                sys.executable,
                self.script_path,
                "-j",
                "--dev",
                "review",
                task_file,
                "--list",
            ],
            capture_output=True,
            text=True,
        )
        self.assertEqual(res.returncode, 0, f"Review --list failed: {res.stderr}")
        print(f"[TEST] Review --list: {json.loads(res.stdout)['data']}")

        # Confirm a file as reviewed
        res = subprocess.run(
            [
                sys.executable,
                self.script_path,
                "-j",
                "--dev",
                "review",
                task_file,
                "test_file.py",
            ],
            capture_output=True,
            text=True,
        )
        self.assertEqual(res.returncode, 0, f"Review file failed: {res.stderr}")
        print("[TEST] Confirmed review of test_file.py")

        # Test regression check passes now
        res = subprocess.run(
            [
                sys.executable,
                self.script_path,
                "-j",
                "--dev",
                "modify",
                task_file,
                "--regression-check",
            ],
            capture_output=True,
            text=True,
        )
        self.assertEqual(res.returncode, 0, f"Regression check failed: {res.stderr}")
        print("[TEST] Regression check passed")

        # Try to move to STAGING (should now work)
        res = subprocess.run(
            [
                sys.executable,
                self.script_path,
                "-j",
                "--dev",
                "move",
                task_file,
                "STAGING",
            ],
            capture_output=True,
            text=True,
        )
        self.assertEqual(res.returncode, 0, f"Move to STAGING failed: {res.stderr}")
        print("[TEST] Moved to STAGING - WORKFLOW COMPLETE!")


if __name__ == "__main__":
    unittest.main()
