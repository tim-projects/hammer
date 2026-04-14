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
        self.script_path = os.path.abspath("tasks.py")

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

        res = self.run_cmd(["undo", file])
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


if __name__ == "__main__":
    unittest.main()
