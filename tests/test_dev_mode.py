import subprocess
import os
import shutil
import json
import unittest
import sys
import tempfile


class TestDevMode(unittest.TestCase):
    def setUp(self):
        self.dev_dir = "/tmp/.tasks"
        if os.path.exists(self.dev_dir):
            shutil.rmtree(self.dev_dir)

        # Record absolute path to tasks.py (located in same directory as this test file)
        self.script_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "tasks.py"
        )

        # Create a fresh temporary git repository for this test
        self.test_repo = tempfile.mkdtemp()
        self.root = self.test_repo
        self.old_cwd = os.getcwd()  # Save current cwd
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
        # Create an initial commit
        with open(os.path.join(self.root, "README.md"), "w") as f:
            f.write("# Test Repo")
        subprocess.run(["git", "add", "README.md"], cwd=self.root, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "Initial commit"],
            cwd=self.root,
            capture_output=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "Test User"],
            cwd=self.root,
            capture_output=True,
        )
        # Create an initial commit
        with open(os.path.join(self.root, "README.md"), "w") as f:
            f.write("# Test Repo")
        subprocess.run(["git", "add", "README.md"], cwd=self.root, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "Initial commit"],
            cwd=self.root,
            capture_output=True,
        )
        # Configure git user for commits
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

    def tearDown(self):
        if os.path.exists(self.dev_dir):
            shutil.rmtree(self.dev_dir)
        # Clean up the temporary git repository (includes all branches)
        if hasattr(self, "test_repo") and os.path.exists(self.test_repo):
            shutil.rmtree(self.test_repo)
        # Restore original cwd if we changed it
        if hasattr(self, "old_cwd"):
            os.chdir(self.old_cwd)

    def run_tasks(self, args):
        cmd = [sys.executable, self.script_path, "--dev"] + args
        result = subprocess.run(cmd, capture_output=True, text=True)
        return result

    def test_dev_lifecycle(self):
        # 1. Init
        res = subprocess.run(
            [sys.executable, self.script_path, "--dev", "init"],
            capture_output=True,
            text=True,
        )
        self.assertEqual(res.returncode, 0)
        self.assertTrue(os.path.exists(self.dev_dir))
        self.assertTrue(os.path.exists(os.path.join(self.dev_dir, "backlog")))

        # 2. Create
        res = subprocess.run(
            [
                sys.executable,
                self.script_path,
                "-j",
                "--dev",
                "create",
                "Dev Task Test",
                "--story",
                "As a dev I want to test dev mode",
                "--tech",
                "Using /tmp/.tasks",
                "--criteria",
                "Task exists in /tmp",
                "--plan",
                "1. Run this test",
            ],
            capture_output=True,
            text=True,
        )
        self.assertEqual(res.returncode, 0)
        data = json.loads(res.stdout)
        task_id = data["data"]["id"]
        self.assertEqual(task_id, 1)

        # Verify it's in /tmp and NOT in project .tasks
        dev_backlog = os.path.join(self.dev_dir, "backlog")
        items = os.listdir(dev_backlog)
        self.assertTrue(any("1-task-dev-task-test" in item for item in items))

        project_tasks = os.path.join(self.root, ".tasks")
        # Ensure no task with that branch name was created in the real project tasks
        for root, dirs, files in os.walk(project_tasks):
            for d in dirs:
                self.assertFalse("1-task-dev-task-test" in d)

        # 3. List
        res = subprocess.run(
            [sys.executable, self.script_path, "-j", "--dev", "list"],
            capture_output=True,
            text=True,
        )
        data = json.loads(res.stdout)
        self.assertEqual(len(data["data"]["BACKLOG"]), 1)

        # 4. Modify
        res = subprocess.run(
            [
                sys.executable,
                self.script_path,
                "-j",
                "--dev",
                "modify",
                "1",
                "--progress",
                "Working in dev",
            ],
            capture_output=True,
            text=True,
        )
        self.assertEqual(res.returncode, 0)

        # 5. Move
        res = subprocess.run(
            [
                sys.executable,
                self.script_path,
                "-j",
                "--dev",
                "move",
                "1",
                "READY,PROGRESSING",
            ],
            capture_output=True,
            text=True,
        )
        self.assertEqual(res.returncode, 0)
        self.assertTrue(os.path.exists(os.path.join(self.dev_dir, "progressing")))

        # 6. Delete
        res = subprocess.run(
            [sys.executable, self.script_path, "-j", "--dev", "delete", "1"],
            capture_output=True,
            text=True,
        )
        data = json.loads(res.stdout)
        code = data["data"]["delete_code"]

        res = subprocess.run(
            [
                sys.executable,
                self.script_path,
                "-j",
                "--dev",
                "delete",
                "1",
                "--confirm",
                code,
            ],
            capture_output=True,
            text=True,
        )
        self.assertEqual(res.returncode, 0)

        # Verify empty
        res = subprocess.run(
            [sys.executable, self.script_path, "-j", "--dev", "list"],
            capture_output=True,
            text=True,
        )
        data = json.loads(res.stdout)
        self.assertFalse("BACKLOG" in data["data"])
        self.assertFalse("READY,PROGRESSING" in data["data"])

    def test_config_dev(self):
        print(f"[DEBUG] script_path = {self.script_path}")
        # Init
        subprocess.run(
            [sys.executable, self.script_path, "--dev", "init"], capture_output=True
        )

        # Check if dev config file is created in /tmp/.tasks/config.yaml
        # Run any dev command - should work without error
        res = subprocess.run(
            [sys.executable, self.script_path, "--dev", "list"],
            capture_output=True,
            text=True,
        )
        self.assertEqual(res.returncode, 0)

    def test_review_diff_in_dev_mode(self):
        """Test that diff generation works in dev mode."""
        # Init dev environment
        res = subprocess.run(
            [sys.executable, self.script_path, "--dev", "init"],
            capture_output=True,
            text=True,
        )
        self.assertEqual(res.returncode, 0)

        # Determine the initial default branch (before any task branches)
        initial_branch = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=self.root,
            capture_output=True,
            text=True,
        ).stdout.strip()
        print(f"[TEST] Initial default branch: {initial_branch}")

        # Create task
        res = subprocess.run(
            [
                sys.executable,
                self.script_path,
                "-j",
                "--dev",
                "create",
                "Dev Review Diff",
                "--story",
                "This is a sufficiently long story for dev mode testing with enough characters.",
                "--tech",
                "This is a sufficiently long technical description for dev mode testing with enough characters.",
                "--criteria",
                "This is a sufficiently long acceptance criteria for dev mode testing with enough characters.",
                "--plan",
                "1. Initialize dev environment. 2. Create task. 3. Make changes on branch. 4. Move to testing. 5. Merge to testing branch. 6. Mark tests passed. 7. Move to review. 8. Verify diff exists.",
            ],
            capture_output=True,
            text=True,
        )
        self.assertEqual(res.returncode, 0)
        data = json.loads(res.stdout)
        task_file = data["data"]["file"]
        branch = task_file
        self.branch_name = branch  # store for cleanup

        # Move to PROGRESSING
        res = subprocess.run(
            [
                sys.executable,
                self.script_path,
                "-j",
                "--dev",
                "move",
                task_file,
                "READY,PROGRESSING",
            ],
            capture_output=True,
            text=True,
        )
        print(
            f"[TEST] move PROGRESSING rc={res.returncode}, stdout={res.stdout[:200]}, stderr={res.stderr[:200]}"
        )
        self.assertEqual(res.returncode, 0)

        # Create a code file and commit on the task branch
        print("[TEST] Creating code file and committing...")
        code_file = os.path.join(self.root, "dev_feature.py")
        with open(code_file, "w") as f:
            f.write("def dev_feature():\n    return 'dev'\n")
        subprocess.run(
            ["git", "add", "dev_feature.py"], cwd=self.root, capture_output=True
        )
        res_commit = subprocess.run(
            ["git", "commit", "-m", "Add dev feature implementation"],
            cwd=self.root,
            capture_output=True,
            text=True,
        )
        print(
            f"[TEST] git commit rc={res_commit.returncode}, stdout={res_commit.stdout[:200]}, stderr={res_commit.stderr[:200]}"
        )

        # Move to TESTING (requires branch ahead of testing)
        res = subprocess.run(
            [
                sys.executable,
                self.script_path,
                "-j",
                "--dev",
                "move",
                task_file,
                "TESTING",
            ],
            capture_output=True,
            text=True,
        )
        self.assertEqual(res.returncode, 0, f"Move to TESTING failed: {res}")
        print("[TEST] Move to TESTING succeeded")

        # Prepare testing branch: go to default branch, create testing, merge task, back to default
        default_branch = initial_branch
        subprocess.run(
            ["git", "checkout", default_branch], cwd=self.root, capture_output=True
        )
        print("[TEST] Checked out default_branch")
        subprocess.run(
            ["git", "checkout", "-b", "testing"], cwd=self.root, capture_output=True
        )
        print("[TEST] Created testing branch")
        res_merge = subprocess.run(
            ["git", "merge", branch], cwd=self.root, capture_output=True, text=True
        )
        print(
            f"[TEST] git merge rc={res_merge.returncode}, stdout={res_merge.stdout[:200]}, stderr={res_merge.stderr[:200]}"
        )
        subprocess.run(
            ["git", "checkout", default_branch], cwd=self.root, capture_output=True
        )
        print("[TEST] Checked back to default_branch")

        # Mark tests as passed (required for REVIEW)
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
        print(
            f"[TEST] modify rc={res.returncode}, stdout={res.stdout[:200]}, stderr={res.stderr[:200]}"
        )
        self.assertEqual(res.returncode, 0, f"Modify tests-passed failed: {res}")

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
        self.assertEqual(res.returncode, 0, f"Move to REVIEW failed: {res}")

        # Check diff exists in /tmp/.tasks/review/
        task_basename = os.path.basename(task_file).rsplit(".", 1)[0]
        diff_path = f"/tmp/.tasks/review/{task_basename}.patch"
        self.assertTrue(
            os.path.exists(diff_path), f"Dev mode diff not found: {diff_path}"
        )
        # Diff should contain our commit message or code change
        with open(diff_path) as f:
            content = f.read()
        self.assertIn("dev feature", content.lower())


if __name__ == "__main__":
    # Clean up any leftover branch from previous aborted tests
    subprocess.run(["git", "branch", "-D", "1-task-dev-task-test"], capture_output=True)
    unittest.main()
