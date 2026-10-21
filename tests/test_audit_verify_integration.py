"""End-to-end tests for the verifiable, non-skippable patch-review gate.

These exercise the full `tasks` CLI over a real git repo (no stubs) and
validate that the REVIEW -> STAGING gate is *not* skippable for tasks with
real patch changes:

* STAGING is blocked until a verifiable, per-patch review is recorded
  (--regression-check / Rc == PASSED).
* `tasks modify --regression-check` fails WITHOUT --reviewed when there are
  real patch changes.
* The full audit -> verify -> --reviewed -> --regression-check -> STAGING
  flow succeeds.
* A patch tampered with after review makes --regression-check fail (md5
  mismatch) and blocks STAGING.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

from tasks_ai.file_manager import FM


class ReviewGateIntegrationTest(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.repo_dir = os.path.join(self.test_dir, "repo")
        os.makedirs(self.repo_dir)
        subprocess.run(["git", "init"], cwd=self.repo_dir, capture_output=True)  # noqa: PLW1510
        subprocess.run(  # noqa: PLW1510
            ["git", "branch", "-m", "master", "main"], cwd=self.repo_dir
        )
        subprocess.run(  # noqa: PLW1510
            ["git", "config", "user.email", "test@example.com"], cwd=self.repo_dir
        )
        subprocess.run(  # noqa: PLW1510
            ["git", "config", "user.name", "Test User"], cwd=self.repo_dir
        )
        with open(os.path.join(self.repo_dir, "README.md"), "w") as f:
            f.write("# Test Repo")
        subprocess.run(["git", "add", "README.md"], cwd=self.repo_dir, capture_output=True)  # noqa: PLW1510
        subprocess.run(  # noqa: PLW1510
            ["git", "commit", "-m", "Initial commit"], cwd=self.repo_dir
        )
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.script_path = os.path.abspath(os.path.join(self.repo_dir, "hammer"))
        os.symlink(os.path.join(project_root, "hammer"), self.script_path)
        subprocess.run(  # noqa: PLW1510
            ["git", "add", "hammer"], cwd=self.repo_dir, capture_output=True
        )
        subprocess.run(  # noqa: PLW1510
            ["git", "commit", "-m", "Add hammer"], cwd=self.repo_dir, capture_output=True
        )

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    # --- helpers (mirror tests/test_tasks.py proven patterns) ---
    def run_cmd(self, args):
        env = os.environ.copy()
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        env["PYTHONPATH"] = (
            project_root
            + ":"
            + os.path.dirname(project_root)
            + ":"
            + env.get("PYTHONPATH", "")
        )
        result = subprocess.run(  # noqa: PLW1510
            [self.script_path, "tasks", "-j", *args],
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

    def complete_review_gate(self, file):
        """audit -> verify -> --reviewed -> --regression-check."""
        res = self.run_cmd(["audit", file])
        self.assertTrue(res["success"], f"audit failed for {file}: {res}")
        res = self.run_cmd(["verify", file, "--proof", "Reviewed patches and criteria pass."])
        self.assertTrue(res["success"], f"verify failed for {file}: {res}")
        res = self.run_cmd(["modify", file, "--reviewed"])
        self.assertTrue(res["success"], f"--reviewed failed for {file}: {res}")
        res = self.run_cmd(["modify", file, "--regression-check"])
        self.assertTrue(res["success"], f"--regression-check failed for {file}: {res}")

    def create_and_reach_review(self, title, work_file):
        """Create a task, commit a work file on its branch, move to REVIEW.

        Mirrors the proven cycle in tests/test_tasks.py::test_full_lifecycle.
        Returns the task filename (basename).
        """
        self.run_cmd(["init"])
        res = self.run_cmd(
            [
                "create",
                title,
                "--story",
                "As a user I want to validate the review gate is enforced.",
                "--tech",
                "Git and Python orchestration for verifiable reviews.",
                "--criteria",
                "- [ ] Sufficient acceptance criteria for the review gate.",
                "--plan",
                "1. Create\n2. Progress\n3. Test\n4. Review",
            ]
        )
        self.assertTrue(res["success"], res)
        task_file = res["data"]["file"]
        branch = task_file  # branch name equals task filename

        self.run_cmd(["move", task_file, "READY"])
        self.run_cmd(["move", task_file, "PROGRESSING"])

        # Commit real work on the task branch so there are patch changes.
        subprocess.run(["git", "checkout", branch], cwd=self.repo_dir, capture_output=True)  # noqa: PLW1510
        with open(os.path.join(self.repo_dir, work_file), "w") as f:
            f.write("def func():\n    pass\n")
        subprocess.run(["git", "add", work_file], cwd=self.repo_dir, capture_output=True)  # noqa: PLW1510
        subprocess.run(  # noqa: PLW1510
            ["git", "commit", "-m", "Work"], cwd=self.repo_dir, capture_output=True
        )

        # TESTING move requires checkboxes complete in the task's CURRENT stage.
        self.complete_current_criteria(task_file)
        self.run_cmd(["move", task_file, "TESTING"])

        # REVIEW move: testing->review needs tests-passed; sync testing branch.
        subprocess.run(["git", "checkout", "main"], cwd=self.repo_dir, capture_output=True)  # noqa: PLW1510
        self.run_cmd(["modify", task_file, "--tests-passed"])
        subprocess.run(  # noqa: PLW1510
            ["git", "checkout", "-b", "testing"], cwd=self.repo_dir, capture_output=True
        )
        subprocess.run(["git", "merge", branch], cwd=self.repo_dir, capture_output=True)  # noqa: PLW1510
        subprocess.run(["git", "checkout", branch], cwd=self.repo_dir, capture_output=True)  # noqa: PLW1510
        # REVIEW (current stage=testing) also needs checkboxes complete.
        self.complete_current_criteria(task_file)
        self.run_cmd(["move", task_file, "REVIEW"])
        return task_file

    def complete_current_criteria(self, file):
        """Mark the criteria file in the task's current pipeline stage as done."""
        tasks_root = os.path.join(self.repo_dir, ".tasks")
        for stage in [
            "backlog", "ready", "progressing", "testing", "review",
            "staging", "done", "archived", "rejected",
        ]:
            criteria_path = os.path.join(tasks_root, stage, file, "criteria.md")
            if os.path.exists(criteria_path):
                with open(criteria_path) as f:
                    content = f.read()
                with open(criteria_path, "w") as f:
                    f.write(content.replace("- [ ]", "- [x]"))
                return

    def get_meta(self, task_file):
        review_dir = os.path.join(self.repo_dir, ".tasks", "review", task_file)
        meta_path = os.path.join(review_dir, "meta.json")
        with open(meta_path) as f:
            return json.load(f)

    # --- tests ---
    def test_staging_blocked_without_regression_check(self):
        task_file = self.create_and_reach_review(
            "Review Gate Blocked Test Task", "code.py"
        )
        # In REVIEW only; no audit/verify/--reviewed/--regression-check yet.
        res = self.run_cmd(["move", task_file, "STAGING"])
        self.assertFalse(res["success"], res)
        self.assertIn("regression", res.get("error", "").lower() + " " + res.get("hint", "").lower())

    def test_regression_check_requires_reviewed(self):
        task_file = self.create_and_reach_review(
            "Regression Check Requires Reviewed Test", "code.py"
        )
        # audit + verify alone do NOT satisfy the gate; Reviewed is still False.
        self.run_cmd(["audit", task_file])
        self.run_cmd(["verify", task_file, "--proof", "Reviewed patches and criteria pass."])
        res = self.run_cmd(["modify", task_file, "--regression-check"])
        self.assertFalse(res["success"], res)
        self.assertIn("regression", res.get("error", "").lower() + " " + res.get("hint", "").lower())
        # Rc must NOT have been flipped to PASSED.
        self.assertNotEqual(self.get_meta(task_file).get("Rc"), "PASSED")

    def test_full_review_flow_succeeds_then_staging_passes(self):
        task_file = self.create_and_reach_review(
            "Full Review Flow Success Test Task", "code.py"
        )
        self.complete_review_gate(task_file)
        # Rc is now PASSED after the full, verifiable gate.
        self.assertEqual(self.get_meta(task_file).get("Rc"), "PASSED")
        self.assertTrue(self.get_meta(task_file).get("Reviewed"))

        res = self.run_cmd(["move", task_file, "STAGING"])
        self.assertTrue(res["success"], f"STAGING should succeed after review: {res}")

    def test_regression_check_fails_on_tampered_patch(self):
        task_file = self.create_and_reach_review(
            "Tampered Patch Rejection Test Task", "code.py"
        )
        self.complete_review_gate(task_file)
        # Full gate passed; now corrupt a patch and re-run regression-check.
        patches_dir = os.path.join(self.repo_dir, ".tasks", "review", task_file, "patches")
        patches = [f for f in os.listdir(patches_dir) if f.endswith(".patch")]
        self.assertTrue(patches, "expected generated patches")
        with open(os.path.join(patches_dir, patches[0]), "a") as f:
            f.write("\n+ tampered line\n")

        res = self.run_cmd(["modify", task_file, "--regression-check"])
        self.assertFalse(res["success"], res)
        low = res.get("error", "").lower() + " " + res.get("hint", "").lower()
        self.assertIn("mismatch", low)

    def test_empty_diff_auto_passes_regression_check(self):
        task_file = self.create_and_reach_review(
            "Empty Diff Auto Pass Test Task", "code.py"
        )
        # Simulate "no actual changes to review": clear PatchFiles + patch dir,
        # reset Reviewed/Rc. The gate must auto-pass without a review record.
        review_dir = os.path.join(self.repo_dir, ".tasks", "review", task_file)
        patches_dir = os.path.join(review_dir, "patches")
        audit_path = os.path.join(self.repo_dir, ".tasks", "review", f"{task_file}.audit")
        task = FM.load(review_dir)
        task.metadata["PatchFiles"] = []
        task.metadata["Reviewed"] = False
        task.metadata["Rc"] = ""
        FM.dump(task, review_dir)
        if os.path.isdir(patches_dir):
            shutil.rmtree(patches_dir, ignore_errors=True)
        if os.path.exists(audit_path):
            os.remove(audit_path)

        res = self.run_cmd(["modify", task_file, "--regression-check"])
        self.assertTrue(res["success"], res)
        self.assertEqual(self.get_meta(task_file).get("Rc"), "PASSED")


if __name__ == "__main__":
    unittest.main()
