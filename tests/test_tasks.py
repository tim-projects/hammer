#!/usr/bin/env python3
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timedelta

from tasks_ai.constants import STATE_FOLDERS
from tasks_ai.file_manager import FM
from tests.hammer_test_base import ensure_dev_repo


class TestTasksAI(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.dev_tasks_dir = tempfile.mkdtemp(prefix="hammer_tasks_")
        os.environ["HAMMER_DEV_TASKS_DIR"] = self.dev_tasks_dir
        self.repo_dir = os.path.join(self.test_dir, "repo")
        os.makedirs(self.repo_dir)
        subprocess.run(["git", "init"], cwd=self.repo_dir, capture_output=True)  # noqa: PLW1510
        subprocess.run(["git", "branch", "-m", "master", "main"], cwd=self.repo_dir, capture_output=True, check=False)
        subprocess.run(  # noqa: PLW1510
            ["git", "config", "user.email", "test@example.com"], cwd=self.repo_dir
        )
        subprocess.run(["git", "config", "user.name", "Test User"], cwd=self.repo_dir)  # noqa: PLW1510
        subprocess.run(  # noqa: PLW1510
            ["git", "config", "commit.gpgsign", "false"], cwd=self.repo_dir
        )
        with open(os.path.join(self.repo_dir, "README.md"), "w") as f:
            f.write("# Test Repo")
        subprocess.run(["git", "add", "README.md"], cwd=self.repo_dir)  # noqa: PLW1510
        subprocess.run(  # noqa: PLW1510
            ["git", "commit", "-m", "Initial commit"], cwd=self.repo_dir
        )
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.script_path = os.path.abspath(os.path.join(self.repo_dir, "hammer"))
        os.symlink(os.path.join(project_root, "hammer"), self.script_path)
        subprocess.run(["git", "add", "hammer"], cwd=self.repo_dir, capture_output=True)  # noqa: PLW1510
        subprocess.run(  # noqa: PLW1510
            ["git", "commit", "-m", "Add hammer"],
            cwd=self.repo_dir,
            capture_output=True,
        )

        # Manually initialize dev tasks dir (init in dev mode tries to clone 'tasks' branch)
        for folder in STATE_FOLDERS.values():
            d = os.path.join(self.dev_tasks_dir, folder)
            os.makedirs(d, exist_ok=True)
            open(os.path.join(d, ".gitkeep"), "w").close()
        counter_file = os.path.join(self.dev_tasks_dir, ".task_counter")
        if not os.path.exists(counter_file):
            with open(counter_file, "w") as f:
                f.write("0")
        config_data = {"repo": {"lint": "ruff", "test": "/bin/true", "type_check": "/bin/true", "format": "ruff"}}
        with open(os.path.join(self.dev_tasks_dir, "config.yaml"), "w") as f:
            json.dump(config_data, f)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)
        shutil.rmtree(self.dev_tasks_dir, ignore_errors=True)
        shutil.rmtree(self.dev_repo_dir, ignore_errors=True)
        # The store switch keys on this env var, so leaving it set turns every
        # later non-dev test into a dev one.
        os.environ.pop("HAMMER_DEV_TASKS_DIR", None)

    def get_worktree_path(self, task_numeric_id):
        """Get the worktree path for a task from the manifest."""
        manifest_path = os.path.join(self.dev_tasks_dir, "worktrees.json")
        if os.path.exists(manifest_path):
            with open(manifest_path) as f:
                manifest = json.load(f)
            entry = manifest.get("worktrees", {}).get(str(task_numeric_id))
            if entry:
                return entry.get("path")
        return None

    @property
    def dev_repo_dir(self):
        """Repo the --dev CLI acts on: a throwaway clone, never this fixture repo.

        Dev mode must leave the repo it was invoked from untouched, so every
        pipeline-branch simulation below has to target the dev repo.
        """
        return ensure_dev_repo(self.dev_tasks_dir)

    def git_checkout(self, branch, cwd=None):
        """Checkout a branch, preferring worktree path if branch is checked out there."""
        if cwd is None:
            cwd = self.repo_dir
        subprocess.run(
            ["git", "checkout", branch],
            cwd=cwd,
            capture_output=True,
            check=False,
        )

    def git_checkout_main(self):
        """Checkout main in the repo the --dev CLI acts on (always works)."""
        subprocess.run(
            ["git", "checkout", "main"],
            cwd=self.dev_repo_dir,
            capture_output=True,
            check=False,
        )

    def complete_criteria(self, file, stage):
        """Helper to mark all criteria as done."""
        task_dir = os.path.join(self.dev_tasks_dir, stage, file)
        criteria_path = os.path.join(task_dir, "criteria.md")
        if os.path.exists(criteria_path):
            with open(criteria_path, "r") as f:
                content = f.read()
            with open(criteria_path, "w") as f:
                f.write(content.replace("- [ ]", "- [x]"))

    def complete_current_criteria(self, file):
        """Mark the criteria file in the task's current pipeline stage as done."""
        tasks_root = self.dev_tasks_dir
        for stage in ['backlog', 'ready', 'progressing', 'testing', 'review', 'staging', 'done', 'archived', 'rejected']:
            criteria_path = os.path.join(tasks_root, stage, file, 'criteria.md')
            if os.path.exists(criteria_path):
                with open(criteria_path, "r") as f:
                    content = f.read()
                with open(criteria_path, "w") as f:
                    f.write(content.replace("- [ ]", "- [x]"))
                return

    def generate_audit(self, file, stage=None):
        """Generate a REAL audit (patches + md5) for a task in REVIEW."""
        res = self.run_cmd(["audit", file])
        self.assertTrue(res["success"], f"audit failed for {file}: {res}")

    def complete_review_gate(self, file):
        """Run the full, now-mandatory review workflow."""
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
        cmd = [self.script_path, "tasks", "-j", "--dev"] + args
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
        issue_id = res["data"]["id"]

        # Move to READY (Required)
        res = self.run_cmd(["move", issue_file, "READY"])
        self.assertTrue(res["success"], res)

        # Verify it moved from backlog to ready
        self.assertFalse(
            os.path.exists(os.path.join(self.dev_tasks_dir, "backlog", issue_file))
        )
        self.assertTrue(
            os.path.exists(os.path.join(self.dev_tasks_dir, "ready", issue_file))
        )

        # Move task to READY then PROGRESSING
        self.run_cmd(["move", task_file, "READY"])
        self.run_cmd(["move", task_file, "PROGRESSING"])

        # Verify blocked (already on PROGRESSING, can't move again)
        res = self.run_cmd(["move", task_file, "PROGRESSING"])
        self.assertFalse(res["success"], res)

        # Get worktree paths for working in worktrees
        issue_worktree = self.get_worktree_path(issue_id)

        # Move issue to PROGRESSING
        self.run_cmd(["move", issue_file, "PROGRESSING"])

        # Move issue through states
        for state in ["TESTING", "REVIEW", "STAGING", "DONE"]:
            branch = issue_file
            # Checkout the task branch from the worktree (not main repo, since worktree has it)
            wt = issue_worktree if issue_worktree and os.path.exists(issue_worktree) else self.repo_dir
            subprocess.run(  # noqa: PLW1510
                ["git", "checkout", branch], cwd=wt, capture_output=True
            )
            work_file = os.path.join(wt, "fix.txt")
            with open(work_file, "a") as f:
                f.write("fixed\n")
            subprocess.run(["git", "add", "fix.txt"], cwd=wt, capture_output=True)  # noqa: PLW1510
            subprocess.run(  # noqa: PLW1510
                ["git", "commit", "-m", "Work"], cwd=wt, capture_output=True
            )

            # Simulate pipeline merges to satisfy enforcement
            if state == "REVIEW":
                self.git_checkout_main()
                self.run_cmd(["modify", issue_file, "--tests-passed"])
                subprocess.run(  # noqa: PLW1510
                    ["git", "checkout", "-b", "testing"], cwd=self.dev_repo_dir, capture_output=True
                )
                subprocess.run(["git", "merge", branch], cwd=self.dev_repo_dir, capture_output=True)  # noqa: PLW1510
                subprocess.run(["git", "checkout", branch], cwd=wt, capture_output=True)  # noqa: PLW1510
            elif state == "DONE":
                self.git_checkout_main()
                subprocess.run(  # noqa: PLW1510
                    ["git", "checkout", "-b", "staging"], cwd=self.dev_repo_dir, capture_output=True
                )
                subprocess.run(  # noqa: PLW1510
                    ["git", "merge", "testing"], cwd=self.dev_repo_dir, capture_output=True
                )
                self.git_checkout_main()
                subprocess.run(  # noqa: PLW1510
                    ["git", "merge", "staging"], cwd=self.dev_repo_dir, capture_output=True
                )
                subprocess.run(["git", "checkout", branch], cwd=wt, capture_output=True)  # noqa: PLW1510
                # Complete checkboxes before DONE move (write to staging folder)
                criteria_path = os.path.join(
                    self.dev_tasks_dir, "staging", issue_file, "criteria.md"
                )
                with open(criteria_path, "r") as f:
                    content = f.read()
                with open(criteria_path, "w") as f:
                    f.write(content.replace("- [ ]", "- [x]"))

            # Complete checkboxes before promotion
            if state == "TESTING":
                self.complete_current_criteria(issue_file)

            if state == "STAGING":
                self.complete_review_gate(issue_file)

            # Pass -y for DONE since it requires merge confirmation
            move_args = ["move", issue_file, state]
            if state == "DONE":
                move_args.append("-y")
            res = self.run_cmd(move_args)
            self.assertTrue(res["success"], f"Failed move to {state}: {res}")

        # Archive (Needs branch merged to main and -y)
        self.git_checkout_main()
        subprocess.run(  # noqa: PLW1510
            ["git", "merge", branch], cwd=self.dev_repo_dir, capture_output=True
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

    def test_long_form_flags_accept_file_path(self):
        """Long-form flags may name a file: bulk content comes from disk."""
        story_path = os.path.join(self.test_dir, "story.txt")
        with open(story_path, "w") as f:
            f.write("As a user I want long-form content from a file.\nSecond line.")
        criteria_path = os.path.join(self.test_dir, "criteria.md")
        with open(criteria_path, "w") as f:
            f.write("- [ ] one\n- [ ] two\n")
        plan_path = os.path.join(self.test_dir, "plan.txt")
        with open(plan_path, "w") as f:
            f.write("step one\nstep two\n")

        res = self.run_cmd(
            [
                "create",
                "File Submission Task",
                "--story",
                story_path,
                "--tech",
                "Python and Git orchestration.",
                "--criteria",
                criteria_path,
                "--plan",
                plan_path,
            ]
        )
        self.assertTrue(res["success"], res)
        task_file = res["data"]["file"]

        task = FM.load(os.path.join(self.dev_tasks_dir, "backlog", task_file))
        with open(story_path) as f:
            self.assertEqual(task.parts["story"], f.read())
        self.assertEqual(task.parts["criteria"], "- [ ] one\n- [ ] two")
        self.assertEqual(task.parts["plan"], "1. step one\n2. step two")

        # modify accepts the same file convention
        tech_path = os.path.join(self.test_dir, "tech.txt")
        with open(tech_path, "w") as f:
            f.write("Technical background from a file.\nMore detail.")
        res = self.run_cmd(["modify", task_file, "--tech", tech_path])
        self.assertTrue(res["success"], res)
        task = FM.load(os.path.join(self.dev_tasks_dir, "backlog", task_file))
        with open(tech_path) as f:
            self.assertEqual(task.parts["tech"], f.read())

        # A path-shaped value naming no file is an error, not stored prose
        res = self.run_cmd(["modify", task_file, "--story", "/tmp/no-such-story.md"])
        self.assertFalse(res["success"])
        self.assertIn("CONTENT_FILE_NOT_FOUND", res["error"])

    def test_auto_archival(self):
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
        task_id = res["data"]["id"]

        self.run_cmd(["move", file, "READY"])
        self.run_cmd(["move", file, "PROGRESSING"])

        branch = file
        worktree_path = self.get_worktree_path(task_id)
        wt = worktree_path if worktree_path and os.path.exists(worktree_path) else self.repo_dir

        subprocess.run(["git", "checkout", branch], cwd=wt, capture_output=True)  # noqa: PLW1510
        with open(os.path.join(wt, "code.txt"), "w") as f:
            f.write("code")
        subprocess.run(["git", "add", "code.txt"], cwd=wt, capture_output=True)  # noqa: PLW1510
        subprocess.run(["git", "commit", "-m", "Work"], cwd=wt, capture_output=True)  # noqa: PLW1510
        subprocess.run(["git", "checkout", branch], cwd=wt, capture_output=True)  # noqa: PLW1510
        # Rebase or merge main into the branch to avoid conflicts
        subprocess.run(["git", "merge", "main"], cwd=wt, capture_output=True)  # noqa: PLW1510
        self.git_checkout_main()

        for state in ["TESTING", "REVIEW", "STAGING", "DONE"]:
            subprocess.run(["git", "checkout", branch], cwd=wt, capture_output=True)  # noqa: PLW1510
            # Simulate pipeline merges to satisfy enforcement
            if state == "REVIEW":
                self.run_cmd(["modify", file, "--tests-passed"])
                subprocess.run(["git", "checkout", "-b", "testing"], cwd=self.dev_repo_dir, capture_output=True)  # noqa: PLW1510
                subprocess.run(["git", "merge", branch], cwd=self.dev_repo_dir, capture_output=True)  # noqa: PLW1510
                self.git_checkout_main()

            # Mark all criteria as done before promotion
            if state in ["TESTING", "REVIEW", "STAGING", "DONE"]:
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
        log_path = os.path.join(self.dev_tasks_dir, "done", file, "activity.log")
        old_date = (datetime.now() - timedelta(days=8)).strftime("%y%m%d %H:%M")  # noqa: DTZ005
        with open(log_path, "w") as f:
            f.write(f"- {old_date}: STAGING->DONE\n")

        res = self.run_cmd(["list"])
        self.assertIn(f"Auto-archiving: {file}", res["messages"], res)
        self.assertTrue(
            os.path.exists(os.path.join(self.dev_tasks_dir, "archived", file))
        )
        self.assertFalse(
            os.path.exists(os.path.join(self.dev_tasks_dir, "done", file))
        )

    def test_testing_gate_blocks_when_no_new_changes(self):
        """Gate should prevent moving to TESTING if branch is clean and up-to-date with testing."""
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
        task_id = res["data"]["id"]

        # Move through READY -> PROGRESSING
        self.run_cmd(["move", task_file, "READY"])
        self.run_cmd(["move", task_file, "PROGRESSING"])

        # Get worktree path for working in worktree
        worktree_path = self.get_worktree_path(task_id)
        wt = worktree_path if worktree_path and os.path.exists(worktree_path) else self.repo_dir

        # Create initial commit on the task branch
        subprocess.run(
            ["git", "checkout", task_file],
            cwd=wt,
            capture_output=True,
            check=True,
        )
        work_file = os.path.join(wt, "work.txt")
        with open(work_file, "w") as f:
            f.write("initial work\n")
        subprocess.run(
            ["git", "add", "work.txt"],
            cwd=wt,
            capture_output=True,
            check=True,
        )
        subprocess.run(
            ["git", "commit", "-m", "Add work"],
            cwd=wt,
            capture_output=True,
            check=True,
        )

        # Capture the commit SHA of the task branch
        sha_res = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=wt,
            capture_output=True,
            text=True,
            check=True,
        )
        task_sha = sha_res.stdout.strip()

        # Create/force-update a 'testing' branch to point to the same commit,
        # simulating that testing already contains this work.
        subprocess.run(
            ["git", "branch", "-f", "testing", task_sha],
            cwd=self.dev_repo_dir,
            capture_output=True,
            check=True,
        )

        # Ensure we are on the task branch and working tree is clean
        subprocess.run(
            ["git", "checkout", task_file],
            cwd=wt,
            capture_output=True,
            check=True,
        )
        status_check = subprocess.run(  # noqa: PLW1510
            ["git", "status", "--porcelain"],
            cwd=wt,
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
        task_id = res["data"]["id"]
        worktree_path = self.get_worktree_path(task_id)

        # Move back to PROGRESSING
        res = self.run_cmd(["move", task_file, "READY"])
        self.assertTrue(res["success"], res)
        res = self.run_cmd(["move", task_file, "PROGRESSING"])
        self.assertTrue(res["success"], res)

        # Create a code file and commit on the task branch
        wt = worktree_path if worktree_path and os.path.exists(worktree_path) else self.repo_dir
        subprocess.run(["git", "checkout", branch], cwd=wt, capture_output=True)  # noqa: PLW1510
        code_file = os.path.join(wt, "feature.py")
        with open(code_file, "w") as f:
            f.write("def new_feature():\n    return 42\n")
        subprocess.run(  # noqa: PLW1510
            ["git", "add", "feature.py"], cwd=wt, capture_output=True
        )
        subprocess.run(  # noqa: PLW1510
            ["git", "commit", "-m", "Add new feature implementation"], cwd=wt, capture_output=True
        )

        # Move to TESTING (requires branch ahead of testing)
        self.complete_current_criteria(task_file)
        res = self.run_cmd(["move", task_file, "TESTING"])
        self.assertTrue(res["success"], f"Move to TESTING failed: {res}")

        # Prepare testing branch: go to main, create testing, merge task, back to task branch
        self.git_checkout_main()
        subprocess.run(  # noqa: PLW1510
            ["git", "checkout", "-b", "testing"], cwd=self.dev_repo_dir, capture_output=True
        )
        subprocess.run(["git", "merge", branch], cwd=self.dev_repo_dir, capture_output=True)  # noqa: PLW1510
        subprocess.run(["git", "checkout", branch], cwd=wt, capture_output=True)  # noqa: PLW1510

        # Mark tests as passed (required for REVIEW)
        res = self.run_cmd(["modify", task_file, "--tests-passed"])
        self.assertTrue(res["success"])

        # Move to REVIEW
        res = self.run_cmd(["move", task_file, "REVIEW"])
        self.assertTrue(res["success"], f"Move to REVIEW failed: {res}")

        # Verify diff files exist
        patches_dir = os.path.join(self.dev_tasks_dir, "review", branch, "patches")
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
        task_id = res["data"]["id"]
        worktree_path = self.get_worktree_path(task_id)

        # Move task to READY then PROGRESSING
        self.run_cmd(["move", task_file, "READY"])
        self.run_cmd(["move", task_file, "PROGRESSING"])
        wt = worktree_path if worktree_path and os.path.exists(worktree_path) else self.repo_dir
        code_file = os.path.join(wt, "code.py")
        with open(code_file, "w") as f:
            f.write("def func():\n    pass\n")
        subprocess.run(  # noqa: PLW1510
            ["git", "add", "code.py"], cwd=wt, capture_output=True
        )
        subprocess.run(  # noqa: PLW1510
            ["git", "commit", "-m", "Add code"], cwd=wt, capture_output=True
        )

        # Move to TESTING
        self.complete_current_criteria(task_file)
        res = self.run_cmd(["move", task_file, "TESTING"])
        self.assertTrue(res["success"])

        # Setup testing branch merge
        self.git_checkout_main()
        subprocess.run(  # noqa: PLW1510
            ["git", "checkout", "-b", "testing"], cwd=self.dev_repo_dir, capture_output=True
        )
        subprocess.run(["git", "merge", branch], cwd=self.dev_repo_dir, capture_output=True)  # noqa: PLW1510
        subprocess.run(  # noqa: PLW1510
            ["git", "checkout", branch], cwd=wt, capture_output=True
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
        task_id = res["data"]["id"]
        worktree_path = self.get_worktree_path(task_id)

        # Move to READY then PROGRESSING
        self.run_cmd(["move", task_file, "READY"])
        self.run_cmd(["move", task_file, "PROGRESSING"])
        wt = worktree_path if worktree_path and os.path.exists(worktree_path) else self.repo_dir
        code_file = os.path.join(wt, "file.txt")
        with open(code_file, "w") as f:
            f.write("content\n")
        subprocess.run(  # noqa: PLW1510
            ["git", "add", "file.txt"], cwd=wt, capture_output=True
        )
        subprocess.run(  # noqa: PLW1510
            ["git", "commit", "-m", "Add file"], cwd=wt, capture_output=True
        )

        # Move to TESTING
        self.complete_current_criteria(task_file)
        self.run_cmd(["move", task_file, "TESTING"])

        # Setup testing branch
        self.git_checkout_main()
        subprocess.run(  # noqa: PLW1510
            ["git", "checkout", "-b", "testing"], cwd=self.dev_repo_dir, capture_output=True
        )
        subprocess.run(["git", "merge", branch], cwd=self.dev_repo_dir, capture_output=True)  # noqa: PLW1510
        subprocess.run(  # noqa: PLW1510
            ["git", "checkout", branch], cwd=wt, capture_output=True
        )

        # Move to REVIEW (after tests passed)
        self.run_cmd(["modify", task_file, "--tests-passed"])
        self.run_cmd(["move", task_file, "REVIEW"])

        # Load task from review folder
        review_task_path = os.path.join(self.dev_tasks_dir, "review", task_file)
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
        task_id = res["data"]["id"]
        worktree_path = self.get_worktree_path(task_id)

        # Initial commit on task branch
        self.run_cmd(["move", task_file, "READY"])
        self.run_cmd(["move", task_file, "PROGRESSING"])
        wt = worktree_path if worktree_path and os.path.exists(worktree_path) else self.repo_dir
        subprocess.run(["git", "checkout", branch], cwd=wt, capture_output=True)  # noqa: PLW1510
        with open(os.path.join(wt, "initial.txt"), "w") as f:
            f.write("initial\n")
        subprocess.run(["git", "add", "initial.txt"], cwd=wt, capture_output=True)  # noqa: PLW1510
        subprocess.run(  # noqa: PLW1510
            ["git", "commit", "-m", "Initial commit"], cwd=wt, capture_output=True
        )

        # Move to TESTING
        self.complete_current_criteria(task_file)
        self.run_cmd(["move", task_file, "TESTING"])

        # Setup testing branch (merge initial commit)
        self.git_checkout_main()
        subprocess.run(["git", "checkout", "-b", "testing"], cwd=self.dev_repo_dir, capture_output=True)  # noqa: PLW1510
        subprocess.run(["git", "merge", branch], cwd=self.dev_repo_dir, capture_output=True)  # noqa: PLW1510
        subprocess.run(["git", "checkout", branch], cwd=wt, capture_output=True)  # noqa: PLW1510

        # Set tests passed and move to REVIEW
        self.run_cmd(["modify", task_file, "--tests-passed"])
        self.run_cmd(["move", task_file, "REVIEW"])

        # Diff should exist
        patches_dir = os.path.join(self.dev_tasks_dir, "review", branch, "patches")
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
        subprocess.run(["git", "checkout", branch], cwd=wt, capture_output=True)  # noqa: PLW1510
        with open(os.path.join(wt, "fix.txt"), "w") as f:
            f.write("fixed\n")
        subprocess.run(["git", "add", "fix.txt"], cwd=wt, capture_output=True)  # noqa: PLW1510
        subprocess.run(  # noqa: PLW1510
            ["git", "commit", "-m", "Fix regression issue"], cwd=wt, capture_output=True
        )

        # Move to TESTING (branch ahead)
        self.complete_current_criteria(task_file)
        self.run_cmd(["move", task_file, "TESTING"])

        # Update testing to include fix (fast-forward merge)
        self.git_checkout_main()
        subprocess.run(["git", "checkout", "testing"], cwd=self.dev_repo_dir, capture_output=True)  # noqa: PLW1510
        subprocess.run(["git", "merge", branch], cwd=self.dev_repo_dir, capture_output=True)  # noqa: PLW1510
        subprocess.run(["git", "checkout", branch], cwd=wt, capture_output=True)  # noqa: PLW1510

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
        review_task_path = os.path.join(self.dev_tasks_dir, "review", task_file)
        task = FM.load(review_task_path)
        self.assertFalse(
            task.metadata.get("Rc"), "Rc should be reset when re-entering REVIEW"
        )


if __name__ == "__main__":
    unittest.main()
