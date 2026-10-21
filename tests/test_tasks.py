#!/usr/bin/env python3
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timedelta

from tasks_ai.file_manager import FM


class TestTasksAI(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.repo_dir = os.path.join(self.test_dir, "repo")
        os.makedirs(self.repo_dir)
        subprocess.run(["git", "init"], cwd=self.repo_dir, capture_output=True)  # noqa: PLW1510
        subprocess.run(["git", "branch", "-m", "master", "main"], cwd=self.repo_dir, capture_output=True)
        subprocess.run(  # noqa: PLW1510
            ["git", "config", "user.email", "test@example.com"], cwd=self.repo_dir
        )
        subprocess.run(["git", "config", "user.name", "Test User"], cwd=self.repo_dir)  # noqa: PLW1510
        with open(os.path.join(self.repo_dir, "README.md"), "w") as f:
            f.write("# Test Repo")
        subprocess.run(["git", "add", "README.md"], cwd=self.repo_dir)  # noqa: PLW1510
        subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=self.repo_dir)  # noqa: PLW1510
        # Use hammer CLI entry point instead of the removed tasks.py
        # Use local './hammer' CLI entry point
        # Use absolute path to the local './hammer' script in the repository
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.script_path = os.path.abspath(os.path.join(self.repo_dir, "hammer"))
        os.symlink(os.path.join(project_root, "hammer"), self.script_path)
        subprocess.run(["git", "add", "hammer"], cwd=self.repo_dir, capture_output=True)  # noqa: PLW1510
        subprocess.run(  # noqa: PLW1510
            ["git", "commit", "-m", "Add hammer"],
            cwd=self.repo_dir,
            capture_output=True,
        )

        # Setup config - use skip_push to avoid remote operations
        # Do not manually create .tasks here, let init handle it
        # Instead, write config to a temporary location for init to pick up if needed,
        # or just rely on default initialization.

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def complete_criteria(self, file, stage):
        """Helper to mark all criteria as done."""
        # The file argument is the task directory name (e.g. 1-task-first-task)
        # criteria.md is in .tasks/<stage>/<file>/criteria.md
        task_dir = os.path.join(self.repo_dir, ".tasks", stage, file)
        criteria_path = os.path.join(task_dir, "criteria.md")

        print(f"DEBUG: Checking task dir: {task_dir}", file=sys.stderr)
        if os.path.exists(task_dir):
            print(f"DEBUG: Found task dir: {task_dir}", file=sys.stderr)
        else:
            print(f"DEBUG: Task dir NOT found: {task_dir}", file=sys.stderr)

        if os.path.exists(criteria_path):
            with open(criteria_path, "r") as f:
                content = f.read()
            with open(criteria_path, "w") as f:
                f.write(content.replace("- [ ]", "- [x]"))
        else:
            print(f"DEBUG: Criteria path NOT found: {criteria_path}", file=sys.stderr)

    def complete_current_criteria(self, file):
        """Mark the criteria file in the task's current pipeline stage as done."""
        tasks_root = os.path.join(self.repo_dir, ".tasks")
        for stage in ['backlog', 'ready', 'progressing', 'testing', 'review', 'staging', 'done', 'archived', 'rejected']:
            criteria_path = os.path.join(tasks_root, stage, file, 'criteria.md')
            if os.path.exists(criteria_path):
                with open(criteria_path, "r") as f:
                    content = f.read()
                with open(criteria_path, "w") as f:
                    f.write(content.replace("- [ ]", "- [x]"))
                return

    def generate_audit(self, file, stage=None):
        """Generate a REAL audit (patches + md5) for a task in REVIEW.

        Previously this wrote a mock '{}' audit file, which let the old
        existence-only regression check pass without any real hashes.
        """
        res = self.run_cmd(["audit", file])
        self.assertTrue(res["success"], f"audit failed for {file}: {res}")

    def complete_review_gate(self, file):
        """Run the full, now-mandatory review workflow.

        Order matters: audit (patches + md5) -> verify (proof + sha256 hash)
        -> --reviewed (per-patch md5 review records) -> --regression-check.
        """
        self.generate_audit(file)
        res = self.run_cmd(["verify", file, "--proof", "Reviewed patches and criteria pass."])
        self.assertTrue(res["success"], f"verify failed for {file}: {res}")
        res = self.run_cmd(["modify", file, "--reviewed"])
        self.assertTrue(res["success"], f"--reviewed failed for {file}: {res}")
        res = self.run_cmd(["modify", file, "--regression-check"])
        self.assertTrue(res["success"], f"--regression-check failed for {file}: {res}")

    def run_cmd(self, args):
        env = os.environ.copy()
        # Add current directory to PYTHONPATH and project root
        env["PYTHONPATH"] = (
            os.getcwd()
            + ":"
            + os.path.dirname(os.getcwd())
            + ":"
            + env.get("PYTHONPATH", "")
        )
        # Build command through the hammer wrapper and request JSON from tasks.py.
        cmd = [self.script_path, "tasks", "-j"] + args
        result = subprocess.run(  # noqa: PLW1510
            cmd,
            cwd=self.repo_dir,
            capture_output=True,
            text=True,
            env=env,
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
        # The test class sets up a fresh test_dir for every test case.
        # No need for --force, it should just be "init".
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

        # Move task to READY then PROGRESSING
        self.run_cmd(["move", task_file, "READY"])
        self.run_cmd(["move", task_file, "PROGRESSING"])

        # Verify blocked (already on PROGRESSING, can't move again)
        res = self.run_cmd(["move", task_file, "PROGRESSING"])
        self.assertFalse(res["success"], res)

        # Move issue through states
        self.run_cmd(["move", issue_file, "PROGRESSING"])
        for state in ["TESTING", "REVIEW", "STAGING", "DONE"]:
            branch = issue_file
            subprocess.run(  # noqa: PLW1510
                ["git", "checkout", branch], cwd=self.repo_dir, capture_output=True
            )
            with open(os.path.join(self.repo_dir, "fix.txt"), "a") as f:
                f.write("fixed\n")
            subprocess.run(  # noqa: PLW1510
                ["git", "add", "fix.txt"], cwd=self.repo_dir, capture_output=True
            )
            subprocess.run(  # noqa: PLW1510
                ["git", "commit", "-m", "Work"], cwd=self.repo_dir, capture_output=True
            )

            # Simulate pipeline merges to satisfy enforcement
            if state == "REVIEW":
                subprocess.run(  # noqa: PLW1510
                    ["git", "checkout", "main"], cwd=self.repo_dir, capture_output=True
                )
                self.run_cmd(["modify", issue_file, "--tests-passed"])
                subprocess.run(  # noqa: PLW1510
                    ["git", "checkout", "-b", "testing"],
                    cwd=self.repo_dir,
                    capture_output=True,
                )
                subprocess.run(  # noqa: PLW1510
                    ["git", "merge", branch], cwd=self.repo_dir, capture_output=True
                )
                subprocess.run(  # noqa: PLW1510
                    ["git", "checkout", branch], cwd=self.repo_dir, capture_output=True
                )
            elif state == "DONE":
                subprocess.run(  # noqa: PLW1510
                    ["git", "checkout", "main"], cwd=self.repo_dir, capture_output=True
                )
                subprocess.run(  # noqa: PLW1510
                    ["git", "checkout", "-b", "staging"],
                    cwd=self.repo_dir,
                    capture_output=True,
                )
                subprocess.run(  # noqa: PLW1510
                    ["git", "merge", "testing"], cwd=self.repo_dir, capture_output=True
                )
                subprocess.run(  # noqa: PLW1510
                    ["git", "checkout", "main"], cwd=self.repo_dir, capture_output=True
                )
                subprocess.run(  # noqa: PLW1510
                    ["git", "merge", "staging"], cwd=self.repo_dir, capture_output=True
                )
                subprocess.run(  # noqa: PLW1510
                    ["git", "checkout", branch], cwd=self.repo_dir, capture_output=True
                )
                # Complete checkboxes before DONE move (write to staging folder)
                criteria_path = os.path.join(
                    self.repo_dir, ".tasks", "staging", issue_file, "criteria.md"
                )
                with open(criteria_path, "r") as f:
                    content = f.read()
                with open(criteria_path, "w") as f:
                    f.write(content.replace("- [ ]", "- [x]"))

            # Complete checkboxes before promotion
            if state == "TESTING":
                self.complete_current_criteria(issue_file)
            elif state == "DONE":
                criteria_path = os.path.join(
                    self.repo_dir, ".tasks", "staging", issue_file, "criteria.md"
                )
                with open(criteria_path, "r") as f:
                    content = f.read()
                with open(criteria_path, "w") as f:
                    f.write(content.replace("- [ ]", "- [x]"))

            if state == "STAGING":
                self.complete_review_gate(issue_file)

            # Pass -y for DONE since it requires merge confirmation
            move_args = ["move", issue_file, state]
            if state == "DONE":
                move_args.append("-y")
            res = self.run_cmd(move_args)
            print(f"DEBUG: Full response for {state}: {res}")
            self.assertTrue(res["success"], f"Failed move to {state}: {res}")

        # Archive (Needs a commit and -y)
        subprocess.run(  # noqa: PLW1510
            ["git", "checkout", "main"], cwd=self.repo_dir, capture_output=True
        )
        subprocess.run(  # noqa: PLW1510
            ["git", "merge", issue_file], cwd=self.repo_dir, capture_output=True
        )
        res = self.run_cmd(["move", issue_file, "ARCHIVED", "-y"])
        self.assertTrue(res["success"], res)

        # Now unblocked - verify PROGRESSING -> READY is forbidden
        res = self.run_cmd(["move", task_file, "READY"])
        self.assertFalse(
            res["success"],
            "PROGRESSING -> READY should be a forbidden transition",
        )
        # Verify already-on-PROGRESSING is also blocked
        res = self.run_cmd(["move", task_file, "PROGRESSING"])
        self.assertFalse(
            res["success"],
            "Already on PROGRESSING should be blocked",
        )

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

        # Debug: list backlog to find the task directory
        backlog_dir = os.path.join(self.repo_dir, ".tasks", "backlog")
        print(
            f"DEBUG: Contents of {backlog_dir}: {os.listdir(backlog_dir)}",
            file=sys.stderr,
        )

        self.run_cmd(["move", file, "READY"])

        # Debug: list ready dir
        ready_dir = os.path.join(self.repo_dir, ".tasks", "ready")
        print(
            f"DEBUG: Contents of {ready_dir}: {os.listdir(ready_dir)}", file=sys.stderr
        )

        self.run_cmd(["move", file, "PROGRESSING"])

        branch = file
        subprocess.run(  # noqa: PLW1510
            ["git", "checkout", branch], cwd=self.repo_dir, capture_output=True
        )
        with open(os.path.join(self.repo_dir, "code.txt"), "w") as f:
            f.write("code")
        subprocess.run(  # noqa: PLW1510
            ["git", "add", "code.txt"], cwd=self.repo_dir, capture_output=True
        )
        subprocess.run(  # noqa: PLW1510
            ["git", "commit", "-m", "Work"], cwd=self.repo_dir, capture_output=True
        )
        subprocess.run(  # noqa: PLW1510
            ["git", "checkout", branch], cwd=self.repo_dir, capture_output=True
        )
        # Rebase or merge main into the branch to avoid conflicts
        subprocess.run(["git", "merge", "main"], cwd=self.repo_dir, capture_output=True)  # noqa: PLW1510
        subprocess.run(  # noqa: PLW1510
            ["git", "checkout", "main"], cwd=self.repo_dir, capture_output=True
        )

        for state in ["TESTING", "REVIEW", "STAGING", "DONE"]:
            subprocess.run(  # noqa: PLW1510
                ["git", "checkout", branch], cwd=self.repo_dir, capture_output=True
            )
            # Simulate pipeline merges to satisfy enforcement
            if state == "REVIEW":
                self.run_cmd(["modify", file, "--tests-passed"])
                subprocess.run(  # noqa: PLW1510
                    ["git", "checkout", "-b", "testing"],
                    cwd=self.repo_dir,
                    capture_output=True,
                )
                subprocess.run(  # noqa: PLW1510
                    ["git", "merge", branch], cwd=self.repo_dir, capture_output=True
                )
                subprocess.run(  # noqa: PLW1510
                    ["git", "checkout", "main"], cwd=self.repo_dir, capture_output=True
                )

            # Mark all criteria as done before promotion
            if state in ["TESTING", "REVIEW", "STAGING", "DONE"]:
                # Path depends on where the task currently is
                for stage in ["progressing", "testing", "review", "staging"]:
                    self.complete_criteria(file, stage)

            if state == "STAGING":
                self.complete_review_gate(file)

            # Pass -y for DONE since it requires merge confirmation
            move_args = ["move", file, state]
            if state == "DONE":
                move_args.append("-y")
            res = self.run_cmd(move_args)
            self.assertTrue(res["success"], f"Failed move to {state}: {res}")

        # Backdate log
        log_path = os.path.join(self.repo_dir, ".tasks", "done", file, "activity.log")
        old_date = (datetime.now() - timedelta(days=8)).strftime("%y%m%d %H:%M")  # noqa: DTZ005
        with open(log_path, "w") as f:
            f.write(f"- {old_date}: STAGING->DONE\n")

        res = self.run_cmd(["list"])
        self.assertIn(f"Auto-archiving: {file}", res["messages"], res)
        self.assertTrue(
            os.path.exists(os.path.join(self.repo_dir, ".tasks", "archived", file))
        )
        self.assertFalse(
            os.path.exists(os.path.join(self.repo_dir, ".tasks", "done", file))
        )

    def test_testing_gate_blocks_when_no_new_changes(self):
        """Gate should prevent moving to TESTING if branch is clean and up-to-date with testing."""
        self.run_cmd(["init"])
        # No need to manually commit .gitignore

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
        status_check = subprocess.run(  # noqa: PLW1510
            ["git", "status", "--porcelain"],
            cwd=self.repo_dir,
            capture_output=True,
            text=True,
        )
        self.assertFalse(status_check.stdout.strip(), "Working tree should be clean")

        # Move to TESTING: should succeed when criteria are complete
        self.complete_current_criteria(task_file)
        res = self.run_cmd(["move", task_file, "TESTING"])
        self.assertTrue(
            res["success"],
            f"Move to TESTING should succeed with complete criteria: {res}",
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

        # Move back to PROGRESSING
        res = self.run_cmd(["move", task_file, "READY"])
        self.assertTrue(res["success"], res)
        res = self.run_cmd(["move", task_file, "PROGRESSING"])
        self.assertTrue(res["success"], res)

        # Create a code file and commit on the task branch
        code_file = os.path.join(self.repo_dir, "feature.py")
        with open(code_file, "w") as f:
            f.write("def new_feature():\n    return 42\n")
        subprocess.run(  # noqa: PLW1510
            ["git", "add", "feature.py"], cwd=self.repo_dir, capture_output=True
        )
        subprocess.run(  # noqa: PLW1510
            ["git", "commit", "-m", "Add new feature implementation"],
            cwd=self.repo_dir,
            capture_output=True,
        )

        # Move to TESTING (requires branch ahead of testing)
        self.complete_current_criteria(task_file)
        res = self.run_cmd(["move", task_file, "TESTING"])
        self.assertTrue(res["success"], f"Move to TESTING failed: {res}")

        # Prepare testing branch: go to main, create testing, merge task, back to task branch
        subprocess.run(  # noqa: PLW1510
            ["git", "checkout", "main"], cwd=self.repo_dir, capture_output=True
        )
        subprocess.run(  # noqa: PLW1510
            ["git", "checkout", "-b", "testing"], cwd=self.repo_dir, capture_output=True
        )
        subprocess.run(["git", "merge", branch], cwd=self.repo_dir, capture_output=True)  # noqa: PLW1510
        subprocess.run(  # noqa: PLW1510
            ["git", "checkout", branch], cwd=self.repo_dir, capture_output=True
        )

        # Mark tests as passed (required for REVIEW)
        res = self.run_cmd(["modify", task_file, "--tests-passed"])
        self.assertTrue(res["success"])

        # Move to REVIEW
        res = self.run_cmd(["move", task_file, "REVIEW"])
        self.assertTrue(res["success"], f"Move to REVIEW failed: {res}")

        # Verify diff files exist
        patches_dir = os.path.join(self.repo_dir, ".tasks", "review", branch, "patches")
        self.assertTrue(
            os.path.exists(patches_dir), f"Review patches dir not found at {patches_dir}"
        )
        patch_files = [f for f in os.listdir(patches_dir) if f.endswith(".patch")]
        self.assertTrue(
            len(patch_files) > 0, f"No patch files found in {patches_dir}"
        )

        # Diff should contain our changes
        patch_path = os.path.join(patches_dir, patch_files[0])
        with open(patch_path) as f:
            content = f.read()
        self.assertIn("feature.py", content)
        self.assertIn("new_feature", content)

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

        # Move task to READY then PROGRESSING
        self.run_cmd(["move", task_file, "READY"])
        self.run_cmd(["move", task_file, "PROGRESSING"])
        code_file = os.path.join(self.repo_dir, "code.py")
        with open(code_file, "w") as f:
            f.write("def func():\n    pass\n")
        subprocess.run(  # noqa: PLW1510
            ["git", "add", "code.py"], cwd=self.repo_dir, capture_output=True
        )
        subprocess.run(  # noqa: PLW1510
            ["git", "commit", "-m", "Add code"], cwd=self.repo_dir, capture_output=True
        )

        # Move to TESTING
        self.complete_current_criteria(task_file)
        res = self.run_cmd(["move", task_file, "TESTING"])
        self.assertTrue(res["success"])

        # Setup testing branch merge
        subprocess.run(  # noqa: PLW1510
            ["git", "checkout", "main"], cwd=self.repo_dir, capture_output=True
        )
        subprocess.run(  # noqa: PLW1510
            ["git", "checkout", "-b", "testing"], cwd=self.repo_dir, capture_output=True
        )
        subprocess.run(["git", "merge", branch], cwd=self.repo_dir, capture_output=True)  # noqa: PLW1510
        subprocess.run(  # noqa: PLW1510
            ["git", "checkout", branch], cwd=self.repo_dir, capture_output=True
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

        # --regression-check must now fail WITHOUT a verifiable per-patch review
        res = self.run_cmd(["modify", task_file, "--regression-check"])
        self.assertFalse(
            res["success"], "Should not allow --regression-check without --reviewed"
        )
        self.assertIn("regression", res.get("error", "").lower(), res)

        # Full review workflow: audit -> verify -> --reviewed -> --regression-check
        self.complete_review_gate(task_file)

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

        # Move to READY then PROGRESSING
        self.run_cmd(["move", task_file, "READY"])
        self.run_cmd(["move", task_file, "PROGRESSING"])
        code_file = os.path.join(self.repo_dir, "file.txt")
        with open(code_file, "w") as f:
            f.write("content\n")
        subprocess.run(  # noqa: PLW1510
            ["git", "add", "file.txt"], cwd=self.repo_dir, capture_output=True
        )
        subprocess.run(  # noqa: PLW1510
            ["git", "commit", "-m", "Add file"], cwd=self.repo_dir, capture_output=True
        )

        # Move to TESTING
        self.complete_current_criteria(task_file)
        self.run_cmd(["move", task_file, "TESTING"])

        # Setup testing branch
        subprocess.run(  # noqa: PLW1510
            ["git", "checkout", "main"], cwd=self.repo_dir, capture_output=True
        )
        subprocess.run(  # noqa: PLW1510
            ["git", "checkout", "-b", "testing"], cwd=self.repo_dir, capture_output=True
        )
        subprocess.run(["git", "merge", branch], cwd=self.repo_dir, capture_output=True)  # noqa: PLW1510
        subprocess.run(  # noqa: PLW1510
            ["git", "checkout", branch], cwd=self.repo_dir, capture_output=True
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

        # Apply the full, verifiable review + regression check workflow
        self.complete_review_gate(task_file)

        # Verify Rc is now True (truthy)
        task = FM.load(review_task_path)
        self.assertTrue(task.metadata.get("Rc"), "Rc should be True after modify")

        # --regression-check is idempotent: re-running still verifies and succeeds
        res = self.run_cmd(["modify", task_file, "--regression-check"])
        self.assertTrue(res["success"], f"modify --regression-check must succeed: {res}")

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
        self.run_cmd(["move", task_file, "READY"])
        self.run_cmd(["move", task_file, "PROGRESSING"])

        with open(os.path.join(self.repo_dir, "initial.txt"), "w") as f:
            f.write("initial\n")
        subprocess.run(  # noqa: PLW1510
            ["git", "add", "initial.txt"], cwd=self.repo_dir, capture_output=True
        )
        subprocess.run(  # noqa: PLW1510
            ["git", "commit", "-m", "Initial commit"],
            cwd=self.repo_dir,
            capture_output=True,
        )

        # Move to TESTING
        self.complete_current_criteria(task_file)
        self.run_cmd(["move", task_file, "TESTING"])

        # Setup testing branch (merge initial commit)
        subprocess.run(  # noqa: PLW1510
            ["git", "checkout", "main"], cwd=self.repo_dir, capture_output=True
        )
        subprocess.run(  # noqa: PLW1510
            ["git", "checkout", "-b", "testing"], cwd=self.repo_dir, capture_output=True
        )
        subprocess.run(["git", "merge", branch], cwd=self.repo_dir, capture_output=True)  # noqa: PLW1510
        subprocess.run(  # noqa: PLW1510
            ["git", "checkout", branch], cwd=self.repo_dir, capture_output=True
        )

        # Set tests passed and move to REVIEW
        self.run_cmd(["modify", task_file, "--tests-passed"])
        self.run_cmd(["move", task_file, "REVIEW"])

        # Diff should exist
        patches_dir = os.path.join(self.repo_dir, ".tasks", "review", branch, "patches")
        self.assertTrue(os.path.exists(patches_dir), "Initial patches dir should exist")
        patch_files = [f for f in os.listdir(patches_dir) if f.endswith(".patch")]
        self.assertTrue(len(patch_files) > 0, "Initial diff should exist")
        diff_path = os.path.join(patches_dir, patch_files[0])
        with open(diff_path) as f:
            diff1 = f.read()
        self.assertIn("initial", diff1.lower())

        # Move back to PROGRESSING (simulate finding regression)
        res = self.run_cmd(["move", task_file, "PROGRESSING"])
        self.assertTrue(res["success"], "Move back to PROGRESSING should succeed")

        # Patches should be cleaned up when moving back from REVIEW
        self.assertFalse(
            os.path.exists(patches_dir),
            "Patches should be cleaned up when moving back from REVIEW to PROGRESSING",
        )

        # Create fix commit on task branch
        subprocess.run(  # noqa: PLW1510
            ["git", "checkout", branch], cwd=self.repo_dir, capture_output=True
        )
        with open(os.path.join(self.repo_dir, "fix.txt"), "w") as f:
            f.write("fixed\n")
        subprocess.run(  # noqa: PLW1510
            ["git", "add", "fix.txt"], cwd=self.repo_dir, capture_output=True
        )
        subprocess.run(  # noqa: PLW1510
            ["git", "commit", "-m", "Fix regression issue"],
            cwd=self.repo_dir,
            capture_output=True,
        )

        # Move to TESTING (branch ahead)
        self.complete_current_criteria(task_file)
        self.run_cmd(["move", task_file, "TESTING"])

        # Update testing to include fix (fast-forward merge)
        subprocess.run(  # noqa: PLW1510
            ["git", "checkout", "main"], cwd=self.repo_dir, capture_output=True
        )
        subprocess.run(  # noqa: PLW1510
            ["git", "checkout", "testing"], cwd=self.repo_dir, capture_output=True
        )
        subprocess.run(["git", "merge", branch], cwd=self.repo_dir, capture_output=True)  # noqa: PLW1510
        subprocess.run(  # noqa: PLW1510
            ["git", "checkout", branch], cwd=self.repo_dir, capture_output=True
        )

        # Move to REVIEW (new diff regenerated, Rc reset)
        self.run_cmd(["move", task_file, "REVIEW"])

        # Verify diff updated
        patch_files = [f for f in os.listdir(patches_dir) if f.endswith(".patch")]
        self.assertTrue(len(patch_files) > 0, "Diff should exist after re-entering REVIEW")
        diff_path = os.path.join(patches_dir, patch_files[0])
        with open(diff_path) as f:
            diff2 = f.read()
        self.assertIn("initial", diff2.lower(), "Diff should still contain initial commit")

        # Verify Rc is reset
        review_task_path = os.path.join(self.repo_dir, ".tasks", "review", task_file)
        task = FM.load(review_task_path)
        self.assertFalse(
            task.metadata.get("Rc"), "Rc should be reset when re-entering REVIEW"
        )


if __name__ == "__main__":
    unittest.main()
