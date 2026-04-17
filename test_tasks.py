#!/usr/bin/env python3
import os
import subprocess
import shutil
import tempfile
import unittest
import json
import sys
from datetime import datetime, timedelta

from tasks_ai.file_manager import FM


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
        # Compute absolute path to tasks.py based on this file's location
        self.script_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "tasks.py"
        )

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

            if state == "STAGING":
                self.run_cmd(["modify", issue_file, "--regression-check"])

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

            if state == "STAGING":
                self.run_cmd(["modify", file, "--regression-check"])

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

    def test_review_diff_generated(self):
        """Test that moving to REVIEW automatically generates a diff patch."""
        self.run_cmd(["init"])
        res = self.run_cmd(
            [
                "create",
                "Review Diff Generation Test Task",
                "--story",
                "This is a sufficiently long story to meet minimum length requirements for task creation.",
                "--tech",
                "The diff generation uses git commands to capture changes; this test verifies file creation.",
                "--criteria",
                "A .patch file must appear in .tasks/review/ after REVIEW transition.",
                "--plan",
                "1. Create task\n2. Move to PROGRESSING\n3. Commit changes\n4. Move to TESTING\n5. Setup testing branch merge\n6. Move to REVIEW\n7. Verify diff exists and contains commit",
            ]
        )
        self.assertTrue(res["success"])
        task_file = res["data"]["file"]
        branch = task_file

        # Move to PROGRESSING
        self.run_cmd(["move", task_file, "PROGRESSING"])

        # Create a code file and commit on the task branch
        code_file = os.path.join(self.repo_dir, "feature.py")
        with open(code_file, "w") as f:
            f.write("def new_feature():\n    return 42\n")
        subprocess.run(
            ["git", "add", "feature.py"], cwd=self.repo_dir, capture_output=True
        )
        subprocess.run(
            ["git", "commit", "-m", "Add new feature implementation"],
            cwd=self.repo_dir,
            capture_output=True,
        )

        # Move to TESTING (requires branch ahead of testing)
        res = self.run_cmd(["move", task_file, "TESTING"])
        self.assertTrue(res["success"], f"Move to TESTING failed: {res}")

        # Prepare testing branch: go to main, create testing, merge task, back to main
        subprocess.run(
            ["git", "checkout", "main"], cwd=self.repo_dir, capture_output=True
        )
        subprocess.run(
            ["git", "checkout", "-b", "testing"], cwd=self.repo_dir, capture_output=True
        )
        subprocess.run(["git", "merge", branch], cwd=self.repo_dir, capture_output=True)
        subprocess.run(
            ["git", "checkout", "main"], cwd=self.repo_dir, capture_output=True
        )

        # Mark tests as passed (required for REVIEW)
        res = self.run_cmd(["modify", task_file, "--tests-passed"])
        self.assertTrue(res["success"])

        # Move to REVIEW
        res = self.run_cmd(["move", task_file, "REVIEW"])
        self.assertTrue(res["success"], f"Move to REVIEW failed: {res}")

        # Verify diff file exists
        diff_path = os.path.join(self.repo_dir, ".tasks", "review", f"{branch}.patch")
        self.assertTrue(
            os.path.exists(diff_path), f"Review diff not found at {diff_path}"
        )

        # Diff should contain our commit message
        with open(diff_path) as f:
            content = f.read()
        self.assertIn("new feature", content.lower())

    def test_review_to_staging_requires_regression_check(self):
        """Test REVIEW -> STAGING is blocked until --regression-check is used."""
        self.run_cmd(["init"])
        res = self.run_cmd(
            [
                "create",
                "Regression Check Gate Test Task",
                "--story",
                "This story is long enough to meet minimum length requirements for task creation.",
                "--tech",
                "Technical details about the regression gate implementation are documented here for compliance.",
                "--criteria",
                "STAGING must be blocked without Rc and allowed with Rc.",
                "--plan",
                "1. Create task\n2. Move through pipeline to REVIEW\n3. Try STAGING without Rc -> fail\n4. Set Rc\n5. STAGING -> success",
            ]
        )
        self.assertTrue(res["success"])
        task_file = res["data"]["file"]
        branch = task_file

        # Move to PROGRESSING and make commit
        self.run_cmd(["move", task_file, "PROGRESSING"])
        code_file = os.path.join(self.repo_dir, "code.py")
        with open(code_file, "w") as f:
            f.write("def func():\n    pass\n")
        subprocess.run(
            ["git", "add", "code.py"], cwd=self.repo_dir, capture_output=True
        )
        subprocess.run(
            ["git", "commit", "-m", "Add code"], cwd=self.repo_dir, capture_output=True
        )

        # Move to TESTING
        res = self.run_cmd(["move", task_file, "TESTING"])
        self.assertTrue(res["success"])

        # Setup testing branch merge
        subprocess.run(
            ["git", "checkout", "main"], cwd=self.repo_dir, capture_output=True
        )
        subprocess.run(
            ["git", "checkout", "-b", "testing"], cwd=self.repo_dir, capture_output=True
        )
        subprocess.run(["git", "merge", branch], cwd=self.repo_dir, capture_output=True)
        subprocess.run(
            ["git", "checkout", "main"], cwd=self.repo_dir, capture_output=True
        )

        # Mark tests passed and move to REVIEW
        res = self.run_cmd(["modify", task_file, "--tests-passed"])
        self.assertTrue(res["success"])
        res = self.run_cmd(["move", task_file, "REVIEW"])
        self.assertTrue(res["success"])

        # Attempt move to STAGING without regression check - should fail
        res = self.run_cmd(["move", task_file, "STAGING"])
        self.assertFalse(
            res["success"], "Should not allow STAGING without regression check"
        )
        error = res.get("error", "").lower()
        self.assertIn("regression", error, f"Error should mention regression: {res}")

        # Set regression check
        res = self.run_cmd(["modify", task_file, "--regression-check"])
        self.assertTrue(res["success"], f"modify --regression-check failed: {res}")

        # Now STAGING should succeed
        res = self.run_cmd(["move", task_file, "STAGING"])
        self.assertTrue(res["success"], f"STAGING should succeed after Rc set: {res}")

    def test_regression_check_flag_sets_rc_metadata(self):
        """Test that --regression-check correctly sets Rc metadata field."""
        self.run_cmd(["init"])
        res = self.run_cmd(
            [
                "create",
                "Rc Metadata Flag Test Task",
                "--story",
                "This story is long enough to meet the 15 character minimum requirement for task creation.",
                "--tech",
                "Technical explanation long enough to satisfy the 15 character minimum check.",
                "--criteria",
                "Rc field must be True after using modify flag to confirm regression check.",
                "--plan",
                "1. Create\n2. Move to REVIEW\n3. Verify Rc unset\n4. Modify --regression-check\n5. Verify Rc true",
            ]
        )
        self.assertTrue(res["success"])
        task_file = res["data"]["file"]
        branch = task_file

        # Move to PROGRESSING and commit
        self.run_cmd(["move", task_file, "PROGRESSING"])
        code_file = os.path.join(self.repo_dir, "file.txt")
        with open(code_file, "w") as f:
            f.write("content\n")
        subprocess.run(
            ["git", "add", "file.txt"], cwd=self.repo_dir, capture_output=True
        )
        subprocess.run(
            ["git", "commit", "-m", "Add file"], cwd=self.repo_dir, capture_output=True
        )

        # Move to TESTING
        self.run_cmd(["move", task_file, "TESTING"])

        # Setup testing branch
        subprocess.run(
            ["git", "checkout", "main"], cwd=self.repo_dir, capture_output=True
        )
        subprocess.run(
            ["git", "checkout", "-b", "testing"], cwd=self.repo_dir, capture_output=True
        )
        subprocess.run(["git", "merge", branch], cwd=self.repo_dir, capture_output=True)
        subprocess.run(
            ["git", "checkout", "main"], cwd=self.repo_dir, capture_output=True
        )

        # Move to REVIEW (after tests passed)
        self.run_cmd(["modify", task_file, "--tests-passed"])
        self.run_cmd(["move", task_file, "REVIEW"])

        # Load task from review folder
        review_task_path = os.path.join(self.repo_dir, ".tasks", "review", task_file)
        task = FM.load(review_task_path)
        self.assertFalse(
            task.metadata.get("Rc"), "Rc should be unset after entering REVIEW"
        )

        # Apply regression check
        res = self.run_cmd(["modify", task_file, "--regression-check"])
        self.assertTrue(res["success"], "modify --regression-check must succeed")

        # Verify Rc is now True
        task = FM.load(review_task_path)
        self.assertTrue(task.metadata.get("Rc"), "Rc should be True after modify")

    def test_regression_workflow_move_back_to_progressing(self):
        """Test full regression workflow: REVIEW -> PROGRESSING (fix) -> TESTING -> REVIEW."""
        self.run_cmd(["init"])
        res = self.run_cmd(
            [
                "create",
                "Full Regression Recovery Workflow Task",
                "--story",
                "This story is long enough to meet the minimum length requirement for task creation in the system.",
                "--tech",
                "Technical setup and workflow steps are documented here with sufficient length to pass validation.",
                "--criteria",
                "Cycle REVIEW->PROGRESSING->TESTING->REVIEW; diff regenerated; Rc cleared each REVIEW entry.",
                "--plan",
                "1. Enter REVIEW\n2. Move back to PROGRESSING\n3. Fix and commit\n4. Update testing\n5. Re-enter REVIEW\n6. Verify diff updated and Rc cleared",
            ]
        )
        self.assertTrue(res["success"])
        task_file = res["data"]["file"]
        branch = task_file

        # Initial commit on task branch
        self.run_cmd(["move", task_file, "PROGRESSING"])
        with open(os.path.join(self.repo_dir, "initial.txt"), "w") as f:
            f.write("initial\n")
        subprocess.run(
            ["git", "add", "initial.txt"], cwd=self.repo_dir, capture_output=True
        )
        subprocess.run(
            ["git", "commit", "-m", "Initial commit"],
            cwd=self.repo_dir,
            capture_output=True,
        )

        # Move to TESTING
        self.run_cmd(["move", task_file, "TESTING"])

        # Setup testing branch (merge initial commit)
        subprocess.run(
            ["git", "checkout", "main"], cwd=self.repo_dir, capture_output=True
        )
        subprocess.run(
            ["git", "checkout", "-b", "testing"], cwd=self.repo_dir, capture_output=True
        )
        subprocess.run(["git", "merge", branch], cwd=self.repo_dir, capture_output=True)
        subprocess.run(
            ["git", "checkout", "main"], cwd=self.repo_dir, capture_output=True
        )

        # Set tests passed and move to REVIEW
        self.run_cmd(["modify", task_file, "--tests-passed"])
        self.run_cmd(["move", task_file, "REVIEW"])

        # Diff should exist
        diff_path = os.path.join(self.repo_dir, ".tasks", "review", f"{branch}.patch")
        self.assertTrue(os.path.exists(diff_path), "Initial diff should exist")
        with open(diff_path) as f:
            diff1 = f.read()
        self.assertIn("initial", diff1.lower())

        # Move back to PROGRESSING (simulate finding regression)
        res = self.run_cmd(["move", task_file, "PROGRESSING"])
        self.assertTrue(res["success"], "Move back to PROGRESSING should succeed")

        # Diff should still exist (not auto-deleted)
        self.assertTrue(
            os.path.exists(diff_path), "Diff should persist after moving back"
        )

        # Create fix commit on task branch
        subprocess.run(
            ["git", "checkout", branch], cwd=self.repo_dir, capture_output=True
        )
        with open(os.path.join(self.repo_dir, "fix.txt"), "w") as f:
            f.write("fixed\n")
        subprocess.run(
            ["git", "add", "fix.txt"], cwd=self.repo_dir, capture_output=True
        )
        subprocess.run(
            ["git", "commit", "-m", "Fix regression issue"],
            cwd=self.repo_dir,
            capture_output=True,
        )

        # Move to TESTING (branch ahead)
        self.run_cmd(["move", task_file, "TESTING"])

        # Update testing to include fix (fast-forward merge)
        subprocess.run(
            ["git", "checkout", "main"], cwd=self.repo_dir, capture_output=True
        )
        subprocess.run(
            ["git", "checkout", "testing"], cwd=self.repo_dir, capture_output=True
        )
        subprocess.run(["git", "merge", branch], cwd=self.repo_dir, capture_output=True)
        subprocess.run(
            ["git", "checkout", "main"], cwd=self.repo_dir, capture_output=True
        )

        # Move to REVIEW (new diff regenerated, Rc reset)
        self.run_cmd(["move", task_file, "REVIEW"])

        # Verify diff updated
        with open(diff_path) as f:
            diff2 = f.read()
        self.assertIn("Fix regression", diff2, "Diff should contain fix commit")

        # Verify Rc is reset
        review_task_path = os.path.join(self.repo_dir, ".tasks", "review", task_file)
        task = FM.load(review_task_path)
        self.assertFalse(
            task.metadata.get("Rc"), "Rc should be reset when re-entering REVIEW"
        )


if __name__ == "__main__":
    unittest.main()
