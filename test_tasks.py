#!/usr/bin/env python3
import os
import subprocess
import shutil
import tempfile
import unittest
import json
import sys
from datetime import datetime, timedelta


class TestTasksAI(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.repo_dir = os.path.join(self.test_dir, "repo")
        os.makedirs(self.repo_dir)
        subprocess.run(["git", "init"], cwd=self.repo_dir, capture_output=True)
        subprocess.run(
            ["git", "config", "user.email", "test@example.com"], cwd=self.repo_dir
        )
        subprocess.run(["git", "config", "user.name", "Test User"], cwd=self.repo_dir)
        with open(os.path.join(self.repo_dir, "README.md"), "w") as f:
            f.write("# Test Repo")
        subprocess.run(["git", "add", "README.md"], cwd=self.repo_dir)
        subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=self.repo_dir)
        self.script_path = os.path.abspath("tasks.py")

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def run_cmd(self, args):
        result = subprocess.run(
            [sys.executable, self.script_path, "-j"] + args,
            cwd=self.repo_dir,
            capture_output=True,
            text=True,
        )
        try:
            data = json.loads(result.stdout)
            if not data.get("success"):
                print(f"CMD FAILED: tasks {' '.join(args)}", file=sys.stderr)
                print(f"STDOUT: {result.stdout}", file=sys.stderr)
                print(f"STDERR: {result.stderr}", file=sys.stderr)
            return data
        except json.JSONDecodeError:
            print(f"JSON ERROR: tasks {' '.join(args)}", file=sys.stderr)
            print(f"STDOUT: {result.stdout}", file=sys.stderr)
            print(f"STDERR: {result.stderr}", file=sys.stderr)
            return {
                "success": False,
                "error": "JSON Decode Error",
                "stdout": result.stdout,
                "stderr": result.stderr,
            }

    def test_full_lifecycle(self):
        res = self.run_cmd(["init"])
        self.assertTrue(res["success"], res)

        res = self.run_cmd(
            [
                "create",
                "First Task",
                "--priority",
                "3",
                "--story",
                "As a user I want to test the full lifecycle.",
                "--tech",
                "Python and Git orchestration.",
                "--criteria",
                "Task moves through all states correctly.",
                "--plan",
                "1. Init repo\n2. Create task\n3. Move states",
            ]
        )
        self.assertTrue(res["success"], res)
        task_file = res["data"]["file"]  # This is just filename

        res = self.run_cmd(
            [
                "create",
                "Urgent Bug",
                "--type",
                "issue",
                "--story",
                "As a user I want bugs to be fixed fast.",
                "--tech",
                "Python debugger and unit tests.",
                "--criteria",
                "Bug is archived after fix.",
                "--plan",
                "1. Repro\n2. Fix\n3. Verify",
                "--repro",
                "Steps to reproduce the issue locally.",
            ]
        )
        self.assertTrue(res["success"], res)
        issue_file = res["data"]["file"]

        # Move to READY (Required)
        res = self.run_cmd(["move", issue_file, "READY"])
        self.assertTrue(res["success"], res)

        # Verify it moved from backlog to ready
        self.assertFalse(
            os.path.exists(os.path.join(self.repo_dir, ".tasks", "backlog", issue_file))
        )
        self.assertTrue(
            os.path.exists(os.path.join(self.repo_dir, ".tasks", "ready", issue_file))
        )

        # Move to PROGRESSING
        res = self.run_cmd(["move", issue_file, "PROGRESSING"])
        self.assertTrue(res["success"], res)

        # Linking
        self.run_cmd(["move", task_file, "READY"])
        res = self.run_cmd(["link", task_file, issue_file])
        self.assertTrue(res["success"], res)

        # Verify blocked (Urgent Bug is in PROGRESSING, not ARCHIVED)
        res = self.run_cmd(["move", task_file, "PROGRESSING"])
        self.assertFalse(res["success"], res)
        self.assertIn("Blocked by", res.get("error", ""))

        # Move issue through states
        for state in ["TESTING", "REVIEW", "STAGING", "LIVE"]:
            branch = issue_file
            subprocess.run(
                ["git", "checkout", branch], cwd=self.repo_dir, capture_output=True
            )
            with open(os.path.join(self.repo_dir, "fix.txt"), "a") as f:
                f.write("fixed\n")
            subprocess.run(
                ["git", "add", "fix.txt"], cwd=self.repo_dir, capture_output=True
            )
            subprocess.run(
                ["git", "commit", "-m", "Work"], cwd=self.repo_dir, capture_output=True
            )
            subprocess.run(
                ["git", "checkout", "main"], cwd=self.repo_dir, capture_output=True
            )

            # Simulate pipeline merges to satisfy enforcement
            if state == "REVIEW":
                self.run_cmd(["modify", issue_file, "--tests-passed"])
                subprocess.run(
                    ["git", "checkout", "-b", "testing"],
                    cwd=self.repo_dir,
                    capture_output=True,
                )
                subprocess.run(
                    ["git", "merge", branch], cwd=self.repo_dir, capture_output=True
                )
                subprocess.run(
                    ["git", "checkout", "main"], cwd=self.repo_dir, capture_output=True
                )
            elif state == "LIVE":
                subprocess.run(
                    ["git", "checkout", "-b", "staging"],
                    cwd=self.repo_dir,
                    capture_output=True,
                )
                subprocess.run(
                    ["git", "merge", "testing"], cwd=self.repo_dir, capture_output=True
                )
                subprocess.run(
                    ["git", "checkout", "main"], cwd=self.repo_dir, capture_output=True
                )
                subprocess.run(
                    ["git", "merge", "staging"], cwd=self.repo_dir, capture_output=True
                )
                # Complete checkboxes before LIVE move (write to staging folder)
                criteria_path = os.path.join(
                    self.repo_dir, ".tasks", "staging", issue_file, "criteria.md"
                )
                with open(criteria_path, "r") as f:
                    content = f.read()
                with open(criteria_path, "w") as f:
                    f.write(content.replace("- [ ]", "- [x]"))

            # Complete checkboxes only when moving to LIVE
            # (write to staging folder - will be moved to live)
            if state == "LIVE":
                criteria_path = os.path.join(
                    self.repo_dir, ".tasks", "staging", issue_file, "criteria.md"
                )
                with open(criteria_path, "r") as f:
                    content = f.read()
                with open(criteria_path, "w") as f:
                    f.write(content.replace("- [ ]", "- [x]"))

            # Pass -y for LIVE since it requires merge confirmation
            move_args = ["move", issue_file, state]
            if state == "LIVE":
                move_args.append("-y")
            res = self.run_cmd(move_args)
            print(f"DEBUG: Full response for {state}: {res}")
            self.assertTrue(res["success"], f"Failed move to {state}: {res}")

        # Archive (Needs a commit and -y)
        res = self.run_cmd(["move", issue_file, "ARCHIVED", "-y"])
        self.assertTrue(res["success"], res)

        # Now unblocked
        res = self.run_cmd(["move", task_file, "PROGRESSING"])
        self.assertTrue(res["success"], res)

    def test_auto_archival(self):
        self.run_cmd(["init"])
        res = self.run_cmd(
            [
                "create",
                "Testing Auto Archival Feature",
                "--story",
                "As a user I want to test auto archival.",
                "--tech",
                "Python time manipulation.",
                "--criteria",
                "Task is archived after 7 days.",
                "--plan",
                "1. Create task\n2. Wait 7 days\n3. Check list",
            ]
        )
        self.assertTrue(res["success"], res)
        file = res["data"]["file"]

        self.run_cmd(["move", file, "READY"])
        self.run_cmd(["move", file, "PROGRESSING"])

        branch = file
        subprocess.run(
            ["git", "checkout", branch], cwd=self.repo_dir, capture_output=True
        )
        with open(os.path.join(self.repo_dir, "code.txt"), "w") as f:
            f.write("code")
        subprocess.run(
            ["git", "add", "code.txt"], cwd=self.repo_dir, capture_output=True
        )
        subprocess.run(
            ["git", "commit", "-m", "Work"], cwd=self.repo_dir, capture_output=True
        )
        subprocess.run(
            ["git", "checkout", "main"], cwd=self.repo_dir, capture_output=True
        )

        for state in ["TESTING", "REVIEW", "STAGING", "LIVE"]:
            # Simulate pipeline merges to satisfy enforcement
            if state == "REVIEW":
                self.run_cmd(["modify", file, "--tests-passed"])
                subprocess.run(
                    ["git", "checkout", "-b", "testing"],
                    cwd=self.repo_dir,
                    capture_output=True,
                )
                subprocess.run(
                    ["git", "merge", branch], cwd=self.repo_dir, capture_output=True
                )
                subprocess.run(
                    ["git", "checkout", "main"], cwd=self.repo_dir, capture_output=True
                )
            elif state == "LIVE":
                subprocess.run(
                    ["git", "checkout", "-b", "staging"],
                    cwd=self.repo_dir,
                    capture_output=True,
                )
                subprocess.run(
                    ["git", "merge", "testing"], cwd=self.repo_dir, capture_output=True
                )
                subprocess.run(
                    ["git", "checkout", "main"], cwd=self.repo_dir, capture_output=True
                )
                subprocess.run(
                    ["git", "merge", "staging"], cwd=self.repo_dir, capture_output=True
                )
                # Complete checkboxes BEFORE LIVE move (write to staging folder)
                criteria_path = os.path.join(
                    self.repo_dir, ".tasks", "staging", file, "criteria.md"
                )
                with open(criteria_path, "r") as f:
                    content = f.read()
                with open(criteria_path, "w") as f:
                    f.write(content.replace("- [ ]", "- [x]"))

            # Complete checkboxes only when moving to LIVE (write to staging folder)
            if state == "LIVE":
                criteria_path = os.path.join(
                    self.repo_dir, ".tasks", "staging", file, "criteria.md"
                )
                with open(criteria_path, "r") as f:
                    content = f.read()
                with open(criteria_path, "w") as f:
                    f.write(content.replace("- [ ]", "- [x]"))

            # Pass -y for LIVE since it requires merge confirmation
            move_args = ["move", file, state]
            if state == "LIVE":
                move_args.append("-y")
            res = self.run_cmd(move_args)
            self.assertTrue(res["success"], f"Failed move to {state}: {res}")

        # Backdate log
        log_path = os.path.join(self.repo_dir, ".tasks", "live", file, "activity.log")
        old_date = (datetime.now() - timedelta(days=8)).strftime("%y%m%d %H:%M")
        with open(log_path, "w") as f:
            f.write(f"- {old_date}: STAGING->LIVE\n")

        res = self.run_cmd(["list"])
        self.assertIn(f"Auto-archiving: {file}", res["messages"], res)
        self.assertTrue(
            os.path.exists(os.path.join(self.repo_dir, ".tasks", "archived", file))
        )
        self.assertFalse(
            os.path.exists(os.path.join(self.repo_dir, ".tasks", "live", file))
        )

    def test_testing_gate_blocks_when_no_new_changes(self):
        """Gate should prevent moving to TESTING if branch is clean and up-to-date with testing."""
        self.run_cmd(["init"])
        # Commit the .gitignore created by init to avoid it appearing as unstaged
        subprocess.run(
            ["git", "add", ".gitignore"],
            cwd=self.repo_dir,
            capture_output=True,
            check=True,
        )
        subprocess.run(
            ["git", "commit", "-m", "Add .gitignore"],
            cwd=self.repo_dir,
            capture_output=True,
            check=True,
        )

        res = self.run_cmd(
            [
                "create",
                "Testing Gate",
                "--story",
                "As a developer I want the gate to block when appropriate",
                "--tech",
                "Python CLI and Git branch validation gates",
                "--criteria",
                "Gate blocks when no changes",
                "--plan",
                "1. Test gate logic",
            ]
        )
        self.assertTrue(res["success"], res)
        task_file = res["data"]["file"]

        # Move through READY -> PROGRESSING
        self.run_cmd(["move", task_file, "READY"])
        self.run_cmd(["move", task_file, "PROGRESSING"])

        # Create initial commit on the task branch
        subprocess.run(
            ["git", "checkout", task_file],
            cwd=self.repo_dir,
            capture_output=True,
            check=True,
        )
        work_file = os.path.join(self.repo_dir, "work.txt")
        with open(work_file, "w") as f:
            f.write("initial work\n")
        subprocess.run(
            ["git", "add", "work.txt"],
            cwd=self.repo_dir,
            capture_output=True,
            check=True,
        )
        subprocess.run(
            ["git", "commit", "-m", "Add work"],
            cwd=self.repo_dir,
            capture_output=True,
            check=True,
        )

        # Capture the commit SHA of the task branch
        sha_res = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=self.repo_dir,
            capture_output=True,
            text=True,
            check=True,
        )
        task_sha = sha_res.stdout.strip()

        # Create/force-update a 'testing' branch to point to the same commit,
        # simulating that testing already contains this work.
        subprocess.run(
            ["git", "branch", "-f", "testing", task_sha],
            cwd=self.repo_dir,
            capture_output=True,
            check=True,
        )

        # Ensure we are on the task branch and working tree is clean
        subprocess.run(
            ["git", "checkout", task_file],
            cwd=self.repo_dir,
            capture_output=True,
            check=True,
        )
        status_check = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=self.repo_dir,
            capture_output=True,
            text=True,
        )
        self.assertFalse(status_check.stdout.strip(), "Working tree should be clean")

        # Attempt to move to TESTING: should fail because no unstaged changes and no newer commits
        res = self.run_cmd(["move", task_file, "TESTING"])
        self.assertFalse(
            res["success"],
            f"Move to TESTING should have been blocked but succeeded: {res}",
        )
        error_msg = res.get("error", "").lower()
        self.assertIn("no unstaged", error_msg)
        self.assertIn("no commits newer", error_msg)

        # Add an unstaged file; now move should succeed
        with open(work_file, "a") as f:
            f.write("additional unstaged work\n")
        # Don't git add or commit
        res = self.run_cmd(["move", task_file, "TESTING"])
        self.assertTrue(
            res["success"],
            f"Move to TESTING should succeed with unstaged changes: {res}",
        )


if __name__ == "__main__":
    unittest.main()
