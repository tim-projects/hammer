#!/usr/bin/env python3
import os
import subprocess
import shutil
import tempfile
import unittest
import json
import sys


class TestRobustness(unittest.TestCase):
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

    def run_cmd(self, args, check=False):
        result = subprocess.run(
            [sys.executable, self.script_path, "-j"] + args,
            cwd=self.repo_dir,
            capture_output=True,
            text=True,
        )
        try:
            data = json.loads(result.stdout)
            return data
        except json.JSONDecodeError:
            return {
                "success": False,
                "error": "JSON Decode Error",
                "stdout": result.stdout,
                "stderr": result.stderr,
            }

    def test_invalid_status_move(self):
        """1. Create task, invalid status move."""
        self.run_cmd(["init"])
        res = self.run_cmd(
            [
                "create",
                "Test Task for Invalid Move Validation",
                "--story",
                "As a user I want to test invalid moves with proper validation.",
                "--tech",
                "Python testing framework validation and verification.",
                "--criteria",
                "Invalid move is properly rejected by the system.",
                "--plan",
                "Step1: Create task. Step2: Try invalid move.",
            ]
        )
        self.assertTrue(res["success"], res)
        file = res["data"]["file"]
        res = self.run_cmd(["move", file, "INVALID_STATE"])
        self.assertFalse(res["success"], res)
        self.assertIn("INVALID_STATE", res.get("error", ""))

    def test_circular_dependency(self):
        """3. Link task, circular dependency attempt."""
        self.run_cmd(["init"])
        res = self.run_cmd(
            [
                "create",
                "Task Alpha Implementation",
                "--story",
                "Task A story details for circular dependency test.",
                "--tech",
                "Task A technical implementation details here for testing.",
                "--criteria",
                "Task A criteria for completion and verification.",
                "--plan",
                "Create A task and link to B.",
            ]
        )
        self.assertTrue(res["success"], res)
        task_a = res["data"]["file"]
        res = self.run_cmd(
            [
                "create",
                "Task Beta Implementation",
                "--story",
                "Task B story details for circular dependency test.",
                "--tech",
                "Task B technical implementation details here for testing.",
                "--criteria",
                "Task B criteria for completion and verification.",
                "--plan",
                "Create B task and link to A.",
            ]
        )
        self.assertTrue(res["success"], res)
        task_b = res["data"]["file"]
        self.run_cmd(["move", task_a, "READY"])
        self.run_cmd(["move", task_a, "PROGRESSING"])
        self.run_cmd(["move", task_b, "READY"])
        self.run_cmd(["move", task_b, "PROGRESSING"])
        res = self.run_cmd(["link", task_a, task_b])
        self.assertTrue(res["success"], res)
        res = self.run_cmd(["link", task_b, task_a])
        self.assertFalse(res["success"], res)
        self.assertIn("circular", res.get("error", "").lower())

    def test_revert_progressing_to_testing(self):
        """4. Move to TESTING, then revert to PROGRESSING."""
        self.run_cmd(["init"])
        res = self.run_cmd(
            [
                "create",
                "Revert Test Task Implementation",
                "--story",
                "Test reverting state from testing to progressing.",
                "--tech",
                "Testing framework validation and verification.",
                "--criteria",
                "Revert operation works correctly.",
                "--plan",
                "Move to testing then revert to progressing.",
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
        res = self.run_cmd(["move", file, "TESTING"])
        self.assertTrue(res["success"], res)
        res = self.run_cmd(["move", file, "PROGRESSING"])
        self.assertTrue(res["success"], res)

    def test_revert_staging_to_progressing(self):
        """5. Move to STAGING, then move to REVIEW."""
        self.run_cmd(["init"])
        res = self.run_cmd(
            [
                "create",
                "Staging Revert Task Implementation",
                "--story",
                "Test reverting from staging back to progressing.",
                "--tech",
                "Testing framework validation and verification.",
                "--criteria",
                "Revert from staging works correctly.",
                "--plan",
                "Move to staging then move to review.",
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
        self.run_cmd(["move", file, "TESTING"])
        self.run_cmd(["modify", file, "--tests-passed"])
        subprocess.run(
            ["git", "checkout", "-b", "testing"], cwd=self.repo_dir, capture_output=True
        )
        subprocess.run(["git", "merge", branch], cwd=self.repo_dir, capture_output=True)
        subprocess.run(
            ["git", "checkout", "main"], cwd=self.repo_dir, capture_output=True
        )
        res = self.run_cmd(["move", file, "REVIEW"])
        self.assertTrue(res["success"], res)
        self.run_cmd(["modify", file, "--regression-check"])
        subprocess.run(
            ["git", "checkout", "-b", "staging"], cwd=self.repo_dir, capture_output=True
        )
        subprocess.run(
            ["git", "merge", "testing"], cwd=self.repo_dir, capture_output=True
        )
        subprocess.run(
            ["git", "checkout", "main"], cwd=self.repo_dir, capture_output=True
        )
        res = self.run_cmd(["move", file, "STAGING"])
        self.assertTrue(res["success"], res)
        file_id = res["data"]["id"]
        res = self.run_cmd(["move", str(file_id), "REVIEW"])
        self.assertTrue(res["success"], res)

    def test_delete_live_task_fails(self):
        """7. Attempt to delete task when not in LIVE state."""
        self.run_cmd(["init"])
        res = self.run_cmd(
            [
                "create",
                "Live Task Deletion Test",
                "--story",
                "Test deleting task state for validation.",
                "--tech",
                "Testing framework validation and verification.",
                "--criteria",
                "Delete operation handles the task state.",
                "--plan",
                "Create task move to LIVE try delete.",
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
        self.run_cmd(["modify", file, "--tests-passed"])
        subprocess.run(
            ["git", "checkout", "-b", "testing"], cwd=self.repo_dir, capture_output=True
        )
        subprocess.run(["git", "merge", branch], cwd=self.repo_dir, capture_output=True)
        subprocess.run(
            ["git", "checkout", "main"], cwd=self.repo_dir, capture_output=True
        )
        self.run_cmd(["move", file, "TESTING"])
        subprocess.run(
            ["git", "checkout", "-b", "staging"], cwd=self.repo_dir, capture_output=True
        )
        subprocess.run(
            ["git", "merge", "testing"], cwd=self.repo_dir, capture_output=True
        )
        subprocess.run(
            ["git", "checkout", "main"], cwd=self.repo_dir, capture_output=True
        )
        self.run_cmd(["move", file, "REVIEW"])
        self.run_cmd(["modify", file, "--regression-check"])
        res = self.run_cmd(["move", file, "STAGING"])
        self.assertTrue(res["success"], res)
        criteria_path = os.path.join(
            self.repo_dir, ".tasks", "staging", file, "criteria.md"
        )
        with open(criteria_path, "r") as f:
            content = f.read()
        with open(criteria_path, "w") as f:
            f.write(content.replace("- [ ]", "- [x]"))
        subprocess.run(
            ["git", "checkout", "-b", "live"], cwd=self.repo_dir, capture_output=True
        )
        subprocess.run(
            ["git", "merge", "staging"], cwd=self.repo_dir, capture_output=True
        )
        subprocess.run(
            ["git", "checkout", "main"], cwd=self.repo_dir, capture_output=True
        )
        subprocess.run(["git", "merge", "live"], cwd=self.repo_dir, capture_output=True)
        res = self.run_cmd(["move", file, "LIVE", "-y"])
        self.assertTrue(res["success"], res)
        res = self.run_cmd(["delete", file])
        self.assertTrue(res["success"], res)

    def test_reconcile_non_merged(self):
        """8. Reconcile with non-merged branches."""
        self.run_cmd(["init"])
        res = self.run_cmd(
            [
                "create",
                "Reconcile Task Implementation",
                "--story",
                "Test reconcile functionality for non-merged branches.",
                "--tech",
                "Testing framework validation and verification.",
                "--criteria",
                "Reconcile operation works correctly.",
                "--plan",
                "Create task then reconcile.",
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
        self.run_cmd(["move", file, "TESTING"])
        criteria_path = os.path.join(
            self.repo_dir, ".tasks", "testing", file, "criteria.md"
        )
        with open(criteria_path, "r") as f:
            content = f.read()
        with open(criteria_path, "w") as f:
            f.write(content.replace("- [ ]", "- [x]"))
        res = self.run_cmd(["reconcile", "--all"])
        self.assertTrue(res["success"], res)

    def test_link_nonexistent_task(self):
        """9. Link non-existent tasks."""
        self.run_cmd(["init"])
        res = self.run_cmd(
            [
                "create",
                "Link Test Task Implementation",
                "--story",
                "Test linking to nonexistent tasks for validation.",
                "--tech",
                "Testing framework validation and verification.",
                "--criteria",
                "Link operation handles nonexistent tasks.",
                "--plan",
                "Create task then link to nonexistent.",
            ]
        )
        self.assertTrue(res["success"], res)
        file = res["data"]["file"]
        self.run_cmd(["move", file, "READY"])
        self.run_cmd(["move", file, "PROGRESSING"])
        res = self.run_cmd(["link", file, "nonexistent-task-id"])
        self.assertFalse(res["success"], res)

    def test_multiple_checkpoints(self):
        """10. Attempt multiple checkpoint operations."""
        self.run_cmd(["init"])
        res = self.run_cmd(
            [
                "create",
                "Checkpoint Test Task Implementation",
                "--story",
                "Test multiple checkpoint operations for robustness.",
                "--tech",
                "Testing framework validation and verification.",
                "--criteria",
                "Multiple checkpoint operations work correctly.",
                "--plan",
                "Create task then multiple checkpoints.",
            ]
        )
        self.assertTrue(res["success"], res)
        file = res["data"]["file"]
        self.run_cmd(["move", file, "READY"])
        self.run_cmd(["move", file, "PROGRESSING"])
        res = self.run_cmd(["checkpoint"])
        self.assertTrue(res["success"], res)
        res = self.run_cmd(["checkpoint"])
        self.assertTrue(res["success"], res)

    def test_detached_head_operations(self):
        """11. Run tasks operations while in detached HEAD state."""
        self.run_cmd(["init"])
        res = self.run_cmd(
            [
                "create",
                "Detached Head Task Implementation",
                "--story",
                "Test operations in detached HEAD state for robustness.",
                "--tech",
                "Testing framework validation and verification.",
                "--criteria",
                "Operations work in detached HEAD state.",
                "--plan",
                "Create task detach HEAD operate.",
            ]
        )
        self.assertTrue(res["success"], res)
        file = res["data"]["file"]
        subprocess.run(
            ["git", "checkout", file], cwd=self.repo_dir, capture_output=True
        )
        res = self.run_cmd(["list"])
        self.assertTrue(res["success"], res)
        subprocess.run(
            ["git", "checkout", "main"], cwd=self.repo_dir, capture_output=True
        )

    def test_illegal_state_transition(self):
        """12. Attempt to move task to illegal state (READY -> LIVE)."""
        self.run_cmd(["init"])
        res = self.run_cmd(
            [
                "create",
                "Illegal Transition Task Implementation",
                "--story",
                "Test illegal state transition for validation.",
                "--tech",
                "Testing framework validation and verification.",
                "--criteria",
                "Illegal transition is properly rejected.",
                "--plan",
                "Create task try illegal transition.",
            ]
        )
        self.assertTrue(res["success"], res)
        file = res["data"]["file"]
        self.run_cmd(["move", file, "READY"])
        res = self.run_cmd(["move", file, "LIVE"])
        self.assertFalse(res["success"], res)

    def test_link_task_to_itself(self):
        """13. Link task to itself."""
        self.run_cmd(["init"])
        res = self.run_cmd(
            [
                "create",
                "Self Link Task Implementation",
                "--story",
                "Test linking task to itself for validation.",
                "--tech",
                "Testing framework validation and verification.",
                "--criteria",
                "Self link is properly rejected.",
                "--plan",
                "Create task link to itself.",
            ]
        )
        self.assertTrue(res["success"], res)
        file = res["data"]["file"]
        self.run_cmd(["move", file, "READY"])
        self.run_cmd(["move", file, "PROGRESSING"])
        res = self.run_cmd(["link", file, file])
        self.assertFalse(res["success"], res)

    def test_move_rejected_from_staging(self):
        """14. Move task to REJECTED from STAGING."""
        self.run_cmd(["init"])
        res = self.run_cmd(
            [
                "create",
                "Reject Test Task Implementation",
                "--story",
                "Test reject from staging state for validation.",
                "--tech",
                "Testing framework validation and verification.",
                "--criteria",
                "Reject operation works from staging.",
                "--plan",
                "Create task move to staging reject.",
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
        self.run_cmd(["modify", file, "--tests-passed"])
        subprocess.run(
            ["git", "checkout", "-b", "testing"], cwd=self.repo_dir, capture_output=True
        )
        subprocess.run(["git", "merge", branch], cwd=self.repo_dir, capture_output=True)
        subprocess.run(
            ["git", "checkout", "main"], cwd=self.repo_dir, capture_output=True
        )
        self.run_cmd(["move", file, "TESTING"])
        subprocess.run(
            ["git", "checkout", "-b", "staging"], cwd=self.repo_dir, capture_output=True
        )
        subprocess.run(
            ["git", "merge", "testing"], cwd=self.repo_dir, capture_output=True
        )
        subprocess.run(
            ["git", "checkout", "main"], cwd=self.repo_dir, capture_output=True
        )
        self.run_cmd(["move", file, "REVIEW"])
        subprocess.run(
            ["git", "checkout", "-b", "live"], cwd=self.repo_dir, capture_output=True
        )
        subprocess.run(
            ["git", "merge", "staging"], cwd=self.repo_dir, capture_output=True
        )
        subprocess.run(
            ["git", "checkout", "main"], cwd=self.repo_dir, capture_output=True
        )
        subprocess.run(["git", "merge", "live"], cwd=self.repo_dir, capture_output=True)
        self.run_cmd(["modify", file, "--regression-check"])
        self.run_cmd(["move", file, "STAGING"])
        res = self.run_cmd(["move", file, "REJECTED"])
        self.assertTrue(res["success"], res)

    def test_duplicate_issue_name(self):
        """15. Create issue with same name as existing task."""
        self.run_cmd(["init"])
        res = self.run_cmd(
            [
                "create",
                "Duplicate Name Task Implementation",
                "--story",
                "First task with this name for duplicate test.",
                "--tech",
                "Testing framework validation and verification.",
                "--criteria",
                "First task criteria for duplicate test.",
                "--plan",
                "Create first task with this name.",
            ]
        )
        self.assertTrue(res["success"], res)
        res = self.run_cmd(
            [
                "create",
                "Duplicate Name Task Implementation",
                "--story",
                "Second task with duplicate name for validation.",
                "--tech",
                "Testing framework validation and verification.",
                "--criteria",
                "Second task criteria for duplicate test.",
                "--plan",
                "Create second task with same name.",
            ]
        )
        self.assertTrue(res["success"], res)

    def test_archive_without_merge_fails(self):
        """16. Move task to ARCHIVED without being merged."""
        self.run_cmd(["init"])
        res = self.run_cmd(
            [
                "create",
                "Archive Test Task Implementation",
                "--story",
                "Test archive without merge for validation.",
                "--tech",
                "Testing framework validation and verification.",
                "--criteria",
                "Archive operation is rejected without merge.",
                "--plan",
                "Create task try archive without merge.",
            ]
        )
        self.assertTrue(res["success"], res)
        file = res["data"]["file"]
        self.run_cmd(["move", file, "READY"])
        self.run_cmd(["move", file, "PROGRESSING"])
        res = self.run_cmd(["move", file, "ARCHIVED"])
        self.assertFalse(res["success"], res)

    def test_modify_archived_task_fails(self):
        """17. Attempt to modify task that is ARCHIVED."""
        self.run_cmd(["init"])
        res = self.run_cmd(
            [
                "create",
                "Modify Archived Task Implementation",
                "--story",
                "Test modify archived task for validation.",
                "--tech",
                "Testing framework validation and verification.",
                "--criteria",
                "Modify operation is rejected for archived tasks.",
                "--plan",
                "Create task archive then try modify.",
            ]
        )
        self.assertTrue(res["success"], res)
        file_id = res["data"]["id"]
        file = res["data"]["file"]
        self.run_cmd(["move", str(file_id), "READY"])
        self.run_cmd(["move", str(file_id), "PROGRESSING"])
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
        self.run_cmd(["modify", str(file_id), "--tests-passed"])
        subprocess.run(
            ["git", "checkout", "-b", "testing"], cwd=self.repo_dir, capture_output=True
        )
        subprocess.run(["git", "merge", branch], cwd=self.repo_dir, capture_output=True)
        subprocess.run(
            ["git", "checkout", "main"], cwd=self.repo_dir, capture_output=True
        )
        self.run_cmd(["move", str(file_id), "TESTING"])
        subprocess.run(
            ["git", "checkout", "-b", "staging"], cwd=self.repo_dir, capture_output=True
        )
        subprocess.run(
            ["git", "merge", "testing"], cwd=self.repo_dir, capture_output=True
        )
        subprocess.run(
            ["git", "checkout", "main"], cwd=self.repo_dir, capture_output=True
        )
        self.run_cmd(["move", str(file_id), "REVIEW"])
        subprocess.run(
            ["git", "checkout", "-b", "live"], cwd=self.repo_dir, capture_output=True
        )
        subprocess.run(
            ["git", "merge", "staging"], cwd=self.repo_dir, capture_output=True
        )
        subprocess.run(
            ["git", "checkout", "main"], cwd=self.repo_dir, capture_output=True
        )
        subprocess.run(["git", "merge", "live"], cwd=self.repo_dir, capture_output=True)
        self.run_cmd(["move", str(file_id), "LIVE", "-y"])
        self.run_cmd(["move", str(file_id), "ARCHIVED", "-y"])
        res = self.run_cmd(["modify", str(file_id), "--story", "New story"])
        self.assertTrue(res["success"], res)

    def test_comma_separated_move(self):
        """18. Move multiple tasks test comma-separated attempt."""
        self.run_cmd(["init"])
        res = self.run_cmd(
            [
                "create",
                "Multi Move Task One Implementation",
                "--story",
                "First task for multi-move test.",
                "--tech",
                "Testing framework validation and verification.",
                "--criteria",
                "First task criteria for multi-move test.",
                "--plan",
                "Create first task then try multi-move.",
            ]
        )
        self.assertTrue(res["success"], res)
        file1 = res["data"]["file"]
        res = self.run_cmd(
            [
                "create",
                "Multi Move Task Two Implementation",
                "--story",
                "Second task for multi-move test.",
                "--tech",
                "Testing framework validation and verification.",
                "--criteria",
                "Second task criteria for multi-move test.",
                "--plan",
                "Create second task then try multi-move.",
            ]
        )
        self.assertTrue(res["success"], res)
        file2 = res["data"]["file"]
        res = self.run_cmd(["move", f"{file1},{file2}", "READY,READY"])
        self.assertFalse(res["success"], res)

    def test_doctor_detection(self):
        """19. Verify tasks doctor detects data inconsistency."""
        self.run_cmd(["init"])
        res = self.run_cmd(
            [
                "create",
                "Doctor Test Task Implementation",
                "--story",
                "Test doctor functionality for data validation.",
                "--tech",
                "Testing framework validation and verification.",
                "--criteria",
                "Doctor operation works correctly.",
                "--plan",
                "Create task run doctor command.",
            ]
        )
        self.assertTrue(res["success"], res)
        res = self.run_cmd(["doctor"])
        self.assertTrue(res["success"], res)

    def test_undo_after_transition(self):
        """20. Test that undo command is available."""
        self.run_cmd(["init"])
        res = self.run_cmd(
            [
                "create",
                "Undo Test Task Implementation",
                "--story",
                "Test undo functionality after state transition.",
                "--tech",
                "Testing framework validation and verification.",
                "--criteria",
                "Undo operation works correctly.",
                "--plan",
                "Create task move then try undo.",
            ]
        )
        self.assertTrue(res["success"], res)
        file = res["data"]["file"]
        self.run_cmd(["move", file, "READY"])
        initial_dir = os.path.join(self.repo_dir, ".tasks", "ready", file)
        self.assertTrue(os.path.exists(initial_dir))
        res = self.run_cmd(["list"])
        self.assertTrue(res["success"], res)

    def test_cleanup_merged_task(self):
        """21. Run tasks cleanup on merged tasks."""
        self.run_cmd(["init"])
        res = self.run_cmd(
            [
                "create",
                "Cleanup Test Task Implementation",
                "--story",
                "Test cleanup functionality for merged tasks.",
                "--tech",
                "Testing framework validation and verification.",
                "--criteria",
                "Cleanup operation works correctly.",
                "--plan",
                "Create task merge then cleanup.",
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
        self.run_cmd(["modify", file, "--tests-passed"])
        subprocess.run(
            ["git", "checkout", "-b", "testing"], cwd=self.repo_dir, capture_output=True
        )
        subprocess.run(["git", "merge", branch], cwd=self.repo_dir, capture_output=True)
        subprocess.run(
            ["git", "checkout", "main"], cwd=self.repo_dir, capture_output=True
        )
        self.run_cmd(["move", file, "TESTING"])
        subprocess.run(
            ["git", "checkout", "-b", "staging"], cwd=self.repo_dir, capture_output=True
        )
        subprocess.run(
            ["git", "merge", "testing"], cwd=self.repo_dir, capture_output=True
        )
        subprocess.run(
            ["git", "checkout", "main"], cwd=self.repo_dir, capture_output=True
        )
        self.run_cmd(["move", file, "REVIEW"])
        subprocess.run(
            ["git", "checkout", "-b", "live"], cwd=self.repo_dir, capture_output=True
        )
        subprocess.run(
            ["git", "merge", "staging"], cwd=self.repo_dir, capture_output=True
        )
        subprocess.run(
            ["git", "checkout", "main"], cwd=self.repo_dir, capture_output=True
        )
        subprocess.run(["git", "merge", "live"], cwd=self.repo_dir, capture_output=True)
        self.run_cmd(["modify", file, "--regression-check"])
        self.run_cmd(["move", file, "STAGING"])
        criteria_path = os.path.join(
            self.repo_dir, ".tasks", "staging", file, "criteria.md"
        )
        with open(criteria_path, "r") as f:
            content = f.read()
        with open(criteria_path, "w") as f:
            f.write(content.replace("- [ ]", "- [x]"))
        self.run_cmd(["move", file, "LIVE", "-y"])
        self.run_cmd(["move", file, "ARCHIVED", "-y"])
        res = self.run_cmd(["cleanup"])
        self.assertTrue(res["success"], res)

    def test_list_json_filtering(self):
        """22. Test tasks list command."""
        self.run_cmd(["init"])
        res = self.run_cmd(
            [
                "create",
                "Filter Test Task Implementation",
                "--story",
                "Test filtering functionality for list command.",
                "--tech",
                "Testing framework validation and verification.",
                "--criteria",
                "Filter operation works correctly.",
                "--plan",
                "Create task then run list command.",
            ]
        )
        self.assertTrue(res["success"], res)
        res = self.run_cmd(["list"])
        self.assertTrue(res["success"], res)

    def test_invalid_task_id(self):
        """23. Run workflow operations with invalid task IDs."""
        self.run_cmd(["init"])
        res = self.run_cmd(["move", "nonexistent-task-id", "READY"])
        self.assertFalse(res["success"], res)

    def test_extreme_characters(self):
        """25. Test task creation with extreme character counts."""
        self.run_cmd(["init"])
        long_story = "a" * 10000
        long_tech = "b" * 10000
        res = self.run_cmd(
            [
                "create",
                "Long Fields Task Implementation",
                "--story",
                long_story,
                "--tech",
                long_tech,
                "--criteria",
                "Extreme character counts are handled properly.",
                "--plan",
                "Create with long story and tech fields.",
            ]
        )
        self.assertTrue(res["success"], res)

    def test_invalid_state_name(self):
        """45. Check if tasks move accepts invalid state names."""
        self.run_cmd(["init"])
        res = self.run_cmd(
            [
                "create",
                "Invalid State Test Implementation",
                "--story",
                "Test invalid state name for validation.",
                "--tech",
                "Testing framework validation and verification.",
                "--criteria",
                "Invalid state names are rejected.",
                "--plan",
                "Create task try invalid state name.",
            ]
        )
        self.assertTrue(res["success"], res)
        file = res["data"]["file"]
        res = self.run_cmd(["move", file, "NOT_A_STATE"])
        self.assertFalse(res["success"], res)

    def test_empty_modify_values(self):
        """36. Test tasks modify with empty values."""
        self.run_cmd(["init"])
        res = self.run_cmd(
            [
                "create",
                "Empty Modify Test Implementation",
                "--story",
                "Test empty modify values for validation.",
                "--tech",
                "Testing framework validation and verification.",
                "--criteria",
                "Empty modify values are handled properly.",
                "--plan",
                "Create task try empty modify.",
            ]
        )
        self.assertTrue(res["success"], res)
        file = res["data"]["file"]
        res = self.run_cmd(["modify", file, "--story", ""])
        self.assertTrue(res["success"], res)

    def test_list_non_task_repo(self):
        """32. Run tasks list in a non-task git repository."""
        non_task_dir = os.path.join(self.test_dir, "non_task")
        os.makedirs(non_task_dir)
        subprocess.run(["git", "init"], cwd=non_task_dir, capture_output=True)
        subprocess.run(
            ["git", "config", "user.email", "test@example.com"], cwd=non_task_dir
        )
        subprocess.run(["git", "config", "user.name", "Test User"], cwd=non_task_dir)
        with open(os.path.join(non_task_dir, "README.md"), "w") as f:
            f.write("# Test Repo")
        subprocess.run(["git", "add", "README.md"], cwd=non_task_dir)
        subprocess.run(["git", "commit", "-m", "Initial"], cwd=non_task_dir)
        result = subprocess.run(
            [sys.executable, self.script_path, "-j", "list"],
            cwd=non_task_dir,
            capture_output=True,
            text=True,
        )
        res = json.loads(result.stdout)
        self.assertFalse(res["success"], res)

    def test_link_archived_task(self):
        """26. Attempt to link an ARCHIVED task to a new task."""
        self.run_cmd(["init"])
        res = self.run_cmd(
            [
                "create",
                "Archived Task Link Test",
                "--story",
                "Test linking archived task to new task.",
                "--tech",
                "Testing framework validation and verification.",
                "--criteria",
                "Link operation works correctly.",
                "--plan",
                "Create task move to archived link to new.",
            ]
        )
        self.assertTrue(res["success"], res)
        file_id = res["data"]["id"]
        self.run_cmd(["move", str(file_id), "READY"])
        self.run_cmd(["move", str(file_id), "PROGRESSING"])
        branch = res["data"]["file"]
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
        self.run_cmd(["modify", str(file_id), "--tests-passed"])
        subprocess.run(
            ["git", "checkout", "-b", "testing"], cwd=self.repo_dir, capture_output=True
        )
        subprocess.run(["git", "merge", branch], cwd=self.repo_dir, capture_output=True)
        subprocess.run(
            ["git", "checkout", "main"], cwd=self.repo_dir, capture_output=True
        )
        self.run_cmd(["move", str(file_id), "TESTING"])
        subprocess.run(
            ["git", "checkout", "-b", "staging"], cwd=self.repo_dir, capture_output=True
        )
        subprocess.run(
            ["git", "merge", "testing"], cwd=self.repo_dir, capture_output=True
        )
        subprocess.run(
            ["git", "checkout", "main"], cwd=self.repo_dir, capture_output=True
        )
        self.run_cmd(["move", str(file_id), "REVIEW"])
        subprocess.run(
            ["git", "checkout", "-b", "live"], cwd=self.repo_dir, capture_output=True
        )
        subprocess.run(
            ["git", "merge", "staging"], cwd=self.repo_dir, capture_output=True
        )
        subprocess.run(
            ["git", "checkout", "main"], cwd=self.repo_dir, capture_output=True
        )
        subprocess.run(["git", "merge", "live"], cwd=self.repo_dir, capture_output=True)
        self.run_cmd(["modify", str(file_id), "--regression-check"])
        self.run_cmd(["move", str(file_id), "STAGING"])
        criteria_path = os.path.join(
            self.repo_dir, ".tasks", "staging", branch, "criteria.md"
        )
        with open(criteria_path, "r") as f:
            content = f.read()
        with open(criteria_path, "w") as f:
            f.write(content.replace("- [ ]", "- [x]"))
        self.run_cmd(["move", str(file_id), "LIVE", "-y"])
        self.run_cmd(["move", str(file_id), "ARCHIVED", "-y"])
        res = self.run_cmd(
            [
                "create",
                "New Task To Link",
                "--story",
                "New task to link to archived task.",
                "--tech",
                "Testing framework validation and verification.",
                "--criteria",
                "New task criteria for linking.",
                "--plan",
                "Create new task for linking.",
            ]
        )
        self.assertTrue(res["success"], res)
        new_file = res["data"]["file"]
        self.run_cmd(["move", new_file, "READY"])
        self.run_cmd(["move", new_file, "PROGRESSING"])
        res = self.run_cmd(["link", new_file, branch])
        self.assertTrue(res["success"], res)

    def test_move_deleted_task(self):
        """28. Attempt to move a task after it has been deleted."""
        self.run_cmd(["init"])
        res = self.run_cmd(
            [
                "create",
                "Task To Delete",
                "--story",
                "Test deleting and moving deleted task.",
                "--tech",
                "Testing framework validation and verification.",
                "--criteria",
                "Delete operation works correctly.",
                "--plan",
                "Create task delete then try move.",
            ]
        )
        self.assertTrue(res["success"], res)
        file = res["data"]["file"]
        res = self.run_cmd(["delete", file])
        self.assertTrue(res["success"], res)
        res = self.run_cmd(["move", file, "READY"])
        self.assertFalse(res["success"], res)

    def test_branch_deletion_after_cleanup(self):
        """29. Verify task branch deletion after tasks cleanup."""
        self.run_cmd(["init"])
        res = self.run_cmd(
            [
                "create",
                "Branch Delete Test",
                "--story",
                "Test branch deletion after cleanup.",
                "--tech",
                "Testing framework validation and verification.",
                "--criteria",
                "Branch deletion works correctly.",
                "--plan",
                "Create task archive cleanup check branch.",
            ]
        )
        self.assertTrue(res["success"], res)
        file = res["data"]["file"]
        branch = file
        self.run_cmd(["move", file, "READY"])
        self.run_cmd(["move", file, "PROGRESSING"])
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
        self.run_cmd(["modify", file, "--tests-passed"])
        subprocess.run(
            ["git", "checkout", "-b", "testing"], cwd=self.repo_dir, capture_output=True
        )
        subprocess.run(["git", "merge", branch], cwd=self.repo_dir, capture_output=True)
        subprocess.run(
            ["git", "checkout", "main"], cwd=self.repo_dir, capture_output=True
        )
        self.run_cmd(["move", file, "TESTING"])
        subprocess.run(
            ["git", "checkout", "-b", "staging"], cwd=self.repo_dir, capture_output=True
        )
        subprocess.run(
            ["git", "merge", "testing"], cwd=self.repo_dir, capture_output=True
        )
        subprocess.run(
            ["git", "checkout", "main"], cwd=self.repo_dir, capture_output=True
        )
        self.run_cmd(["move", file, "REVIEW"])
        subprocess.run(
            ["git", "checkout", "-b", "live"], cwd=self.repo_dir, capture_output=True
        )
        subprocess.run(
            ["git", "merge", "staging"], cwd=self.repo_dir, capture_output=True
        )
        subprocess.run(
            ["git", "checkout", "main"], cwd=self.repo_dir, capture_output=True
        )
        subprocess.run(["git", "merge", "live"], cwd=self.repo_dir, capture_output=True)
        self.run_cmd(["modify", file, "--regression-check"])
        self.run_cmd(["move", file, "STAGING"])
        criteria_path = os.path.join(
            self.repo_dir, ".tasks", "staging", file, "criteria.md"
        )
        with open(criteria_path, "r") as f:
            content = f.read()
        with open(criteria_path, "w") as f:
            f.write(content.replace("- [ ]", "- [x]"))
        self.run_cmd(["move", file, "LIVE", "-y"])
        self.run_cmd(["move", file, "ARCHIVED", "-y"])
        res = self.run_cmd(["cleanup", "--dry-run"])
        self.assertTrue(res["success"], res)

    def test_concurrent_move_operations(self):
        """30. Test sequential move operations on the same task."""
        self.run_cmd(["init"])
        res = self.run_cmd(
            [
                "create",
                "Sequential Move Test",
                "--story",
                "Test sequential moves on same task.",
                "--tech",
                "Testing framework validation and verification.",
                "--criteria",
                "Sequential moves work correctly.",
                "--plan",
                "Create task perform sequential moves.",
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
        res = self.run_cmd(["move", file, "TESTING"])
        self.assertTrue(res["success"], res)
        res = self.run_cmd(["move", file, "PROGRESSING"])
        self.assertTrue(res["success"], res)

    def test_failed_git_command_handling(self):
        """31. Check task status after a failed command."""
        self.run_cmd(["init"])
        res = self.run_cmd(
            [
                "create",
                "Failed Git Test",
                "--story",
                "Test handling of failed git commands.",
                "--tech",
                "Testing framework validation and verification.",
                "--criteria",
                "Failed commands handled correctly.",
                "--plan",
                "Create task try failed git operation.",
            ]
        )
        self.assertTrue(res["success"], res)
        result = subprocess.run(
            ["git", "status"], cwd=self.repo_dir, capture_output=True, text=True
        )
        self.assertEqual(result.returncode, 0)
        res = self.run_cmd(["list"])
        self.assertTrue(res["success"], res)

    def test_non_utf8_characters(self):
        """33. Verify tasks.py handles non-utf-8 characters."""
        self.run_cmd(["init"])
        res = self.run_cmd(
            [
                "create",
                "Unicode Test Task",
                "--story",
                "Test handling of unicode characters.",
                "--tech",
                "Testing framework with unicode chars.",
                "--criteria",
                "Unicode handled correctly.",
                "--plan",
                "Create task with unicode characters.",
            ]
        )
        self.assertTrue(res["success"], res)

    def test_duplicate_numeric_id_simulation(self):
        """34. Attempt to create a task with duplicate numeric ID (simulated)."""
        self.run_cmd(["init"])
        res = self.run_cmd(
            [
                "create",
                "Duplicate ID Test",
                "--story",
                "Test handling of duplicate IDs.",
                "--tech",
                "Testing framework validation.",
                "--criteria",
                "ID handling works correctly.",
                "--plan",
                "Create task with specific ID pattern.",
            ]
        )
        self.assertTrue(res["success"], res)
        res = self.run_cmd(
            [
                "create",
                "Another Duplicate ID Test",
                "--story",
                "Another task with similar ID pattern.",
                "--tech",
                "Testing framework validation.",
                "--criteria",
                "ID handling works correctly.",
                "--plan",
                "Create another task.",
            ]
        )
        self.assertTrue(res["success"], res)

    def test_show_missing_fields(self):
        """35. Verify tasks show output for missing fields."""
        self.run_cmd(["init"])
        res = self.run_cmd(
            [
                "create",
                "Show Missing Fields Test",
                "--story",
                "Test show command output.",
                "--tech",
                "Testing framework validation.",
                "--criteria",
                "Show command works correctly.",
                "--plan",
                "Create task run show command.",
            ]
        )
        self.assertTrue(res["success"], res)
        file = res["data"]["file"]
        res = self.run_cmd(["show", file])
        self.assertTrue(res["success"], res)

    def test_blocker_transition_logic(self):
        """37. Validate task state transition logic when blockers exist."""
        self.run_cmd(["init"])
        res = self.run_cmd(
            [
                "create",
                "Blocker Test Task",
                "--story",
                "Test blocker transition logic.",
                "--tech",
                "Testing framework validation.",
                "--criteria",
                "Blocker logic works correctly.",
                "--plan",
                "Create task with blocker.",
            ]
        )
        self.assertTrue(res["success"], res)
        blocker = res["data"]["file"]
        res = self.run_cmd(
            [
                "create",
                "Blocked Task Test",
                "--story",
                "Test blocked task.",
                "--tech",
                "Testing framework validation.",
                "--criteria",
                "Blocked task works correctly.",
                "--plan",
                "Create blocked task.",
            ]
        )
        self.assertTrue(res["success"], res)
        blocked = res["data"]["file"]
        self.run_cmd(["move", blocker, "READY"])
        self.run_cmd(["move", blocker, "PROGRESSING"])
        self.run_cmd(["move", blocked, "READY"])
        self.run_cmd(["move", blocked, "PROGRESSING"])
        res = self.run_cmd(["list"])
        self.assertTrue(res["success"], res)

    def test_run_invalid_command(self):
        """38. Run tasks run with an invalid command."""
        self.run_cmd(["init"])
        res = self.run_cmd(["run", "nonexistent-tool"])
        self.assertFalse(res["success"], res)

    def test_doctor_on_clean_repo(self):
        """39. Check tasks doctor behavior on clean repo."""
        self.run_cmd(["init"])
        res = self.run_cmd(
            [
                "create",
                "Doctor Clean Test",
                "--story",
                "Test doctor on clean repo.",
                "--tech",
                "Testing framework validation.",
                "--criteria",
                "Doctor works on clean repo.",
                "--plan",
                "Create task run doctor.",
            ]
        )
        self.assertTrue(res["success"], res)
        res = self.run_cmd(["doctor"])
        self.assertTrue(res["success"], res)

    def test_branch_naming_special_chars(self):
        """40. Verify task branch naming with special characters."""
        self.run_cmd(["init"])
        res = self.run_cmd(
            [
                "create",
                "Special Branch Test",
                "--story",
                "Test branch naming.",
                "--tech",
                "Testing framework validation.",
                "--criteria",
                "Branch naming works correctly.",
                "--plan",
                "Create task with special name.",
            ]
        )
        self.assertTrue(res["success"], res)
        file = res["data"]["file"]
        self.run_cmd(["move", file, "READY"])
        self.run_cmd(["move", file, "PROGRESSING"])
        branch_exists = subprocess.run(
            ["git", "rev-parse", "--verify", file],
            cwd=self.repo_dir,
            capture_output=True,
        )
        self.assertEqual(branch_exists.returncode, 0)

    def test_task_movement_workflow(self):
        """41. Test task movement through valid workflow."""
        self.run_cmd(["init"])
        res = self.run_cmd(
            [
                "create",
                "Full Workflow Test",
                "--story",
                "Test full workflow movement.",
                "--tech",
                "Testing framework validation.",
                "--criteria",
                "Workflow works correctly.",
                "--plan",
                "Create task move through workflow.",
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
        res = self.run_cmd(["move", file, "TESTING"])
        self.assertTrue(res["success"], res)

    def test_partial_title_matching(self):
        """44. Run workflow operations with partial task titles."""
        self.run_cmd(["init"])
        res = self.run_cmd(
            [
                "create",
                "Unique Partial Match Test",
                "--story",
                "Test partial title matching.",
                "--tech",
                "Testing framework validation.",
                "--criteria",
                "Partial matching works.",
                "--plan",
                "Create task use partial match.",
            ]
        )
        self.assertTrue(res["success"], res)
        res = self.run_cmd(["list"])
        self.assertTrue(res["success"], res)

    def test_history_log_integrity(self):
        """46. Verify task history log integrity after multiple moves."""
        self.run_cmd(["init"])
        res = self.run_cmd(
            [
                "create",
                "History Log Test",
                "--story",
                "Test history log integrity.",
                "--tech",
                "Testing framework validation.",
                "--criteria",
                "History log works correctly.",
                "--plan",
                "Create task check history log.",
            ]
        )
        self.assertTrue(res["success"], res)
        file = res["data"]["file"]
        self.run_cmd(["move", file, "READY"])
        self.run_cmd(["move", file, "PROGRESSING"])
        res = self.run_cmd(["list"])
        self.assertTrue(res["success"], res)

    def test_cleanup_dry_run(self):
        """47. Test tasks cleanup dry-run vs actual execution."""
        self.run_cmd(["init"])
        res = self.run_cmd(
            [
                "create",
                "Cleanup Dry Run Test",
                "--story",
                "Test cleanup dry-run functionality.",
                "--tech",
                "Testing framework validation.",
                "--criteria",
                "Dry-run works correctly.",
                "--plan",
                "Create task test dry-run cleanup.",
            ]
        )
        self.assertTrue(res["success"], res)
        res = self.run_cmd(["cleanup", "--dry-run"])
        self.assertTrue(res["success"], res)

    def test_sequential_undo_operations(self):
        """48. Ensure tasks undo handles multiple sequential operations correctly."""
        self.run_cmd(["init"])
        res = self.run_cmd(
            [
                "create",
                "Sequential Undo Test",
                "--story",
                "Test sequential undo operations.",
                "--tech",
                "Testing framework validation.",
                "--criteria",
                "Sequential undo works correctly.",
                "--plan",
                "Create task test sequential undo.",
            ]
        )
        self.assertTrue(res["success"], res)
        file = res["data"]["file"]
        self.run_cmd(["move", file, "READY"])
        res = self.run_cmd(["list"])
        self.assertTrue(res["success"], res)

    def test_long_plan_criteria_lists(self):
        """49. Test task creation with long plan/criteria lists."""
        self.run_cmd(["init"])
        long_plan = "Step 1: Do something.\n" * 50
        long_criteria = "- [ ] Criteria item.\n" * 50
        res = self.run_cmd(
            [
                "create",
                "Long Plan Criteria Test",
                "--story",
                "Test long plan and criteria lists.",
                "--tech",
                "Testing framework validation.",
                "--criteria",
                long_criteria,
                "--plan",
                long_plan,
            ]
        )
        self.assertTrue(res["success"], res)

    def test_init_already_initialized(self):
        """50. Run tasks init in an already initialized repository."""
        self.run_cmd(["init"])
        res = self.run_cmd(["init"])
        self.assertTrue(res["success"], res)

    def test_regression_check_gate_blocks_staging(self):
        """Test that moving from REVIEW to STAGING is blocked until --regression-check."""
        self.run_cmd(["init"])
        res = self.run_cmd(
            [
                "create",
                "Regression Gate Test",
                "--story",
                "A sufficiently long story to pass minimum length requirements for task creation in the system.",
                "--tech",
                "Technical details about regression check gate.",
                "--criteria",
                "STAGING must be blocked without Rc and allowed after --regression-check.",
                "--plan",
                "1. Create\n2. Move to REVIEW\n3. STAGING fails\n4. Set Rc\n5. STAGING succeeds",
            ]
        )
        self.assertTrue(res["success"])
        file = res["data"]["file"]
        branch = file

        # Move through workflow to REVIEW
        self.run_cmd(["move", file, "PROGRESSING"])
        subprocess.run(
            ["git", "checkout", branch], cwd=self.repo_dir, capture_output=True
        )
        with open(os.path.join(self.repo_dir, "code.txt"), "w") as f:
            f.write("code\n")
        subprocess.run(
            ["git", "add", "code.txt"], cwd=self.repo_dir, capture_output=True
        )
        subprocess.run(
            ["git", "commit", "-m", "Add code"], cwd=self.repo_dir, capture_output=True
        )
        subprocess.run(
            ["git", "checkout", "main"], cwd=self.repo_dir, capture_output=True
        )
        self.run_cmd(["modify", file, "--tests-passed"])
        subprocess.run(
            ["git", "checkout", "-b", "testing"], cwd=self.repo_dir, capture_output=True
        )
        subprocess.run(["git", "merge", branch], cwd=self.repo_dir, capture_output=True)
        subprocess.run(
            ["git", "checkout", "main"], cwd=self.repo_dir, capture_output=True
        )
        self.run_cmd(["move", file, "TESTING"])
        subprocess.run(
            ["git", "checkout", "-b", "staging"], cwd=self.repo_dir, capture_output=True
        )
        subprocess.run(
            ["git", "merge", "testing"], cwd=self.repo_dir, capture_output=True
        )
        subprocess.run(
            ["git", "checkout", "main"], cwd=self.repo_dir, capture_output=True
        )
        self.run_cmd(["move", file, "REVIEW"])

        # Without Rc, STAGING should fail
        res = self.run_cmd(["move", file, "STAGING"])
        self.assertFalse(res["success"])
        self.assertIn("regression", res.get("error", "").lower())

        # Set Rc
        self.run_cmd(["modify", file, "--regression-check"])

        # Now STAGING should succeed
        res = self.run_cmd(["move", file, "STAGING"])
        self.assertTrue(res["success"])

    def test_regression_workflow_cycle(self):
        """Test full regression workflow cycle: REVIEW -> PROGRESSING -> (fix) -> REVIEW -> STAGING."""
        self.run_cmd(["init"])
        res = self.run_cmd(
            [
                "create",
                "Regression Cycle Task",
                "--story",
                "A sufficiently long story describing the regression cycle test scenario thoroughly.",
                "--tech",
                "Technical implementation details for the regression workflow.",
                "--criteria",
                "Regression workflow cycle completes successfully.",
                "--plan",
                "1. Create\n2. Move to PROGRESSING\n3. Commit initial code\n4. TESTING\n5. REVIEW\n6. Move back to PROGRESSING\n7. Fix and return to REVIEW\n8. Set Rc\n9. Move to STAGING",
            ]
        )
        self.assertTrue(res["success"])
        file = res["data"]["file"]
        branch = file

        # Initial progress to REVIEW
        self.run_cmd(["move", file, "PROGRESSING"])
        subprocess.run(
            ["git", "checkout", branch], cwd=self.repo_dir, capture_output=True
        )
        with open(os.path.join(self.repo_dir, "code.txt"), "w") as f:
            f.write("initial\n")
        subprocess.run(
            ["git", "add", "code.txt"], cwd=self.repo_dir, capture_output=True
        )
        subprocess.run(
            ["git", "commit", "-m", "Initial work"],
            cwd=self.repo_dir,
            capture_output=True,
        )
        subprocess.run(
            ["git", "checkout", "main"], cwd=self.repo_dir, capture_output=True
        )
        self.run_cmd(["modify", file, "--tests-passed"])
        subprocess.run(
            ["git", "checkout", "-b", "testing"], cwd=self.repo_dir, capture_output=True
        )
        subprocess.run(["git", "merge", branch], cwd=self.repo_dir, capture_output=True)
        subprocess.run(
            ["git", "checkout", "main"], cwd=self.repo_dir, capture_output=True
        )
        self.run_cmd(["move", file, "TESTING"])
        subprocess.run(
            ["git", "checkout", "-b", "staging"], cwd=self.repo_dir, capture_output=True
        )
        subprocess.run(
            ["git", "merge", "testing"], cwd=self.repo_dir, capture_output=True
        )
        subprocess.run(
            ["git", "checkout", "main"], cwd=self.repo_dir, capture_output=True
        )
        self.run_cmd(["move", file, "REVIEW"])

        # Move back to PROGRESSING (simulate finding regressions) - allowed without Rc
        res = self.run_cmd(["move", file, "PROGRESSING"])
        self.assertTrue(res["success"])

        # Fix on task branch
        subprocess.run(
            ["git", "checkout", branch], cwd=self.repo_dir, capture_output=True
        )
        with open(os.path.join(self.repo_dir, "code.txt"), "a") as f:
            f.write("fix\n")
        subprocess.run(
            ["git", "add", "code.txt"], cwd=self.repo_dir, capture_output=True
        )
        subprocess.run(
            ["git", "commit", "-m", "Fix regression"],
            cwd=self.repo_dir,
            capture_output=True,
        )
        subprocess.run(
            ["git", "checkout", "main"], cwd=self.repo_dir, capture_output=True
        )
        # Re-merge to testing and staging
        subprocess.run(
            ["git", "checkout", "testing"], cwd=self.repo_dir, capture_output=True
        )
        subprocess.run(["git", "merge", branch], cwd=self.repo_dir, capture_output=True)
        subprocess.run(
            ["git", "checkout", "main"], cwd=self.repo_dir, capture_output=True
        )
        self.run_cmd(["move", file, "TESTING"])
        subprocess.run(
            ["git", "checkout", "-b", "staging"], cwd=self.repo_dir, capture_output=True
        )
        subprocess.run(
            ["git", "merge", "testing"], cwd=self.repo_dir, capture_output=True
        )
        subprocess.run(
            ["git", "checkout", "main"], cwd=self.repo_dir, capture_output=True
        )
        self.run_cmd(["move", file, "REVIEW"])

        # Set regression check and move to STAGING
        self.run_cmd(["modify", file, "--regression-check"])
        res = self.run_cmd(["move", file, "STAGING"])
        self.assertTrue(res["success"])

    def test_doctor_stale_counter_detection_and_fix(self):
        """45. Verify doctor detects stale task counter and fixes with --fix."""
        self.run_cmd(["init"])
        # Create two tasks to generate IDs 1 and 2
        res1 = self.run_cmd(
            [
                "create",
                "Stale Counter Task One",
                "--story",
                "First task for stale counter test with enough detail.",
                "--tech",
                "Testing counter logic and doctor fix behavior.",
                "--criteria",
                "Task created successfully with proper validation.",
                "--plan",
                "Implement the task fully with tests and documentation.",
            ]
        )
        self.assertTrue(res1["success"])
        res2 = self.run_cmd(
            [
                "create",
                "Stale Counter Task Two",
                "--story",
                "Second task for stale counter test with enough detail.",
                "--tech",
                "Testing counter logic and doctor fix behavior.",
                "--criteria",
                "Task created successfully with proper validation.",
                "--plan",
                "Implement the task fully with tests and documentation.",
            ]
        )
        self.assertTrue(res2["success"])

        # Simulate stale counter by manually setting .task_counter to 0
        tasks_dir = os.path.join(self.repo_dir, ".tasks")
        counter_path = os.path.join(tasks_dir, ".task_counter")
        with open(counter_path, "w") as f:
            f.write("0")
        subprocess.run(
            ["git", "add", ".task_counter"], cwd=tasks_dir, capture_output=True
        )
        subprocess.run(
            ["git", "commit", "-m", "Simulate stale counter"],
            cwd=tasks_dir,
            capture_output=True,
        )

        # Doctor without fix should detect the issue
        res = self.run_cmd(["doctor"])
        self.assertTrue(res["success"])
        self.assertEqual(res["data"]["issues_found"], 1)
        self.assertEqual(res["data"]["bugs"][0]["id"], "stale-task-counter")

        # Doctor with --fix should update counter to max_id + 1 (which is 2+1=3)
        res_fix = self.run_cmd(["doctor", "--fix"])
        self.assertTrue(res_fix["success"])

        # Verify counter value
        with open(counter_path, "r") as f:
            new_val = int(f.read().strip())
        self.assertEqual(new_val, 3)

    def test_doctor_state_mismatch_detection_and_fix(self):
        """46. Verify doctor detects state folder mismatch and fixes with --fix."""
        self.run_cmd(["init"])
        # Create task (default state is BACKLOG)
        res = self.run_cmd(
            [
                "create",
                "State Mismatch Task",
                "--story",
                "Task to test state mismatch detection with enough details.",
                "--tech",
                "Testing state consistency and doctor fix behavior.",
                "--criteria",
                "Task moved to correct state automatically by doctor.",
                "--plan",
                "Implement the task with proper testing and documentation.",
            ]
        )
        self.assertTrue(res["success"])
        tid = res["data"]["file"]

        # Task should be in backlog/
        backlog_dir = os.path.join(self.repo_dir, ".tasks", "backlog")
        task_dir = os.path.join(backlog_dir, tid)
        self.assertTrue(os.path.exists(task_dir))

        # Manually set metadata state to LIVE without moving the folder
        meta_path = os.path.join(task_dir, "meta.json")
        with open(meta_path, "r") as f:
            meta = json.load(f)
        meta["St"] = "LIVE"
        with open(meta_path, "w") as f:
            json.dump(meta, f)

        tasks_dir = os.path.join(self.repo_dir, ".tasks")
        subprocess.run(["git", "add", "."], cwd=tasks_dir, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "Set state mismatch manually"],
            cwd=tasks_dir,
            capture_output=True,
        )

        # Doctor should detect state mismatch (and also stale counter if counter < expected)
        res = self.run_cmd(["doctor"])
        self.assertTrue(res["success"])
        self.assertGreaterEqual(res["data"]["issues_found"], 1)
        mismatch_found = any(
            "state-mismatch" in bug["id"] for bug in res["data"]["bugs"]
        )
        self.assertTrue(mismatch_found, "Expected state-mismatch bug to be detected")

        # Doctor with --fix should move task to live/
        res_fix = self.run_cmd(["doctor", "--fix"])
        self.assertTrue(res_fix["success"])

        # After fix, issues should be resolved (re-run doctor should show 0)
        res_after = self.run_cmd(["doctor"])
        self.assertEqual(res_after["data"]["issues_found"], 0)

        # Verify task moved to live/
        new_task_dir = os.path.join(self.repo_dir, ".tasks", "live", tid)
        self.assertTrue(os.path.exists(new_task_dir))
        # Old location should be gone
        self.assertFalse(os.path.exists(task_dir))


if __name__ == "__main__":
    unittest.main()
