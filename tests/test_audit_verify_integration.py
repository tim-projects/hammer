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
from tests.hammer_test_base import ensure_dev_repo


class ReviewGateIntegrationTest(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.dev_tasks_dir = tempfile.mkdtemp(prefix="hammer_tasks_")
        # Restore the variable even if setUp fails later: this file runs before
        # tests that issue non-dev commands, and a leaked value pointing at a
        # deleted store silently redirects their store (task 364).
        prev_env = os.environ.get("HAMMER_DEV_TASKS_DIR")
        self.addCleanup(
            lambda: (
                os.environ.__setitem__("HAMMER_DEV_TASKS_DIR", prev_env)
                if prev_env is not None
                else os.environ.pop("HAMMER_DEV_TASKS_DIR", None)
            )
        )
        os.environ["HAMMER_DEV_TASKS_DIR"] = self.dev_tasks_dir
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
        subprocess.run(  # noqa: PLW1510
            ["git", "config", "commit.gpgsign", "false"], cwd=self.repo_dir
        )
        with open(os.path.join(self.repo_dir, "README.md"), "w") as f:
            f.write("# Test Repo")
        subprocess.run(
            ["git", "add", "README.md"],
            cwd=self.repo_dir,
            capture_output=True,
            check=False,
        )
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
            ["git", "commit", "-m", "Add hammer"],
            cwd=self.repo_dir,
            capture_output=True,
        )

        # Manually initialize dev tasks dir (init in dev mode tries to clone 'tasks' branch which doesn't exist)
        from tasks_ai.constants import STATE_FOLDERS

        counter_file = os.path.join(self.dev_tasks_dir, ".task_counter")
        os.makedirs(self.dev_tasks_dir, exist_ok=True)
        for folder in STATE_FOLDERS.values():
            os.makedirs(os.path.join(self.dev_tasks_dir, folder), exist_ok=True)
            open(os.path.join(self.dev_tasks_dir, folder, ".gitkeep"), "w").close()
        if not os.path.exists(counter_file):
            with open(counter_file, "w") as f:
                f.write("0")
        # Write config so validation passes
        config_data = {
            "repo": {
                "lint": "ruff",
                "test": "noop",
                "type_check": "noop",
                "format": "ruff",
            }
        }
        with open(os.path.join(self.dev_tasks_dir, "config.yaml"), "w") as f:
            json.dump(config_data, f)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)
        shutil.rmtree(self.dev_tasks_dir, ignore_errors=True)

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
            [self.script_path, "tasks", "-j", "--dev", *args],
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
        res = self.run_cmd(
            ["verify", file, "--proof", "Reviewed patches and criteria pass."]
        )
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
        worktree_path = res["data"].get("worktree", "")

        self.run_cmd(["move", task_file, "READY"])
        # READY -> PROGRESSING now requires a recorded research pass (task 386).
        # Without it the task never leaves READY and every downstream gate
        # assertion degrades to a vacuous pass.
        self.run_cmd(
            [
                "modify",
                task_file,
                "--research",
                "Read pipeline_hooks.py and audit.py to trace the review gate.",
            ]
        )
        self.run_cmd(["move", task_file, "PROGRESSING"])

        # Commit real work in the worktree (not main repo) so the branch gets the commit
        work_dir = (
            worktree_path
            if worktree_path and os.path.exists(worktree_path)
            else self.repo_dir
        )
        subprocess.run(["git", "checkout", branch], cwd=work_dir, capture_output=True)  # noqa: PLW1510
        work_files = [work_file] if isinstance(work_file, str) else work_file
        for filename in work_files:
            with open(os.path.join(work_dir, filename), "w") as f:
                f.write("def func():\n    pass\n")
            subprocess.run(  # noqa: PLW1510
                ["git", "add", filename], cwd=work_dir, capture_output=True
            )
        subprocess.run(  # noqa: PLW1510
            ["git", "commit", "-m", "Work"], cwd=work_dir, capture_output=True
        )

        # TESTING move requires checkboxes complete in the task's CURRENT stage.
        self.complete_current_criteria(task_file)
        self.run_cmd(["move", task_file, "TESTING"])

        # REVIEW move: testing->review needs tests-passed; sync testing branch.
        subprocess.run(
            ["git", "checkout", "main"],
            cwd=self.repo_dir,
            capture_output=True,
            check=False,
        )
        self.run_cmd(["modify", task_file, "--tests-passed"])
        subprocess.run(  # noqa: PLW1510
            ["git", "checkout", "-b", "testing"], cwd=self.repo_dir, capture_output=True
        )
        subprocess.run(["git", "merge", branch], cwd=self.repo_dir, capture_output=True)  # noqa: PLW1510
        subprocess.run(["git", "checkout", branch], cwd=work_dir, capture_output=True)  # noqa: PLW1510
        # REVIEW (current stage=testing) also needs checkboxes complete.
        self.complete_current_criteria(task_file)
        self.run_cmd(["move", task_file, "REVIEW"])
        return task_file

    def complete_current_criteria(self, file):
        """Mark the criteria file in the task's current pipeline stage as done."""
        tasks_root = self.dev_tasks_dir
        for stage in [
            "backlog",
            "ready",
            "progressing",
            "testing",
            "review",
            "staging",
            "done",
            "archived",
            "rejected",
        ]:
            criteria_path = os.path.join(tasks_root, stage, file, "criteria.md")
            if os.path.exists(criteria_path):
                with open(criteria_path) as f:
                    content = f.read()
                with open(criteria_path, "w") as f:
                    f.write(content.replace("- [ ]", "- [x]"))
                return

    def get_meta(self, task_file):
        review_dir = os.path.join(self.dev_tasks_dir, "review", task_file)
        meta_path = os.path.join(review_dir, "meta.json")
        with open(meta_path) as f:
            return json.load(f)

    def get_worktree(self, task_file):
        manifest_path = os.path.join(self.dev_tasks_dir, "worktrees.json")
        with open(manifest_path) as f:
            manifest = json.load(f)
        task_id = task_file.split("-", 1)[0]
        return manifest["worktrees"][task_id]["path"]

    def reenter_review(self, task_file):
        self.complete_current_criteria(task_file)
        res = self.run_cmd(["move", task_file, "TESTING"])
        self.assertTrue(res["success"], f"move to TESTING failed: {res}")
        self.complete_current_criteria(task_file)
        res = self.run_cmd(["move", task_file, "REVIEW"])
        self.assertTrue(res["success"], f"move to REVIEW failed: {res}")

    # --- tests ---
    def test_staging_blocked_without_regression_check(self):
        task_file = self.create_and_reach_review(
            "Review Gate Blocked Test Task", "code.py"
        )
        # In REVIEW only; no audit/verify/--reviewed/--regression-check yet.
        res = self.run_cmd(["move", task_file, "STAGING"])
        self.assertFalse(res["success"], res)
        self.assertIn(
            "regression",
            res.get("error", "").lower() + " " + res.get("hint", "").lower(),
        )

    def test_regression_check_requires_reviewed(self):
        task_file = self.create_and_reach_review(
            "Regression Check Requires Reviewed Test", "code.py"
        )
        # audit + verify alone do NOT satisfy the gate; Reviewed is still False.
        self.run_cmd(["audit", task_file])
        self.run_cmd(
            ["verify", task_file, "--proof", "Reviewed patches and criteria pass."]
        )
        res = self.run_cmd(["modify", task_file, "--regression-check"])
        self.assertFalse(res["success"], res)
        self.assertIn(
            "regression",
            res.get("error", "").lower() + " " + res.get("hint", "").lower(),
        )
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
        patches_dir = os.path.join(self.dev_tasks_dir, "review", task_file, "patches")
        patches = [f for f in os.listdir(patches_dir) if f.endswith(".patch")]
        self.assertTrue(patches, "expected generated patches")
        with open(os.path.join(patches_dir, patches[0]), "a") as f:
            f.write("\n+ tampered line\n")

        res = self.run_cmd(["modify", task_file, "--regression-check"])
        self.assertFalse(res["success"], res)
        low = res.get("error", "").lower() + " " + res.get("hint", "").lower()
        self.assertIn("mismatch", low)

    def test_audit_refreshes_stale_patches_without_round_trip(self):
        """A stale or missing patch set must be regenerated by audit alone.

        Regression: patches kept stale base content while --reviewed/audit
        md5s bound over them, and audit skipped regeneration whenever
        Rc == PASSED, so the stale set could not self-heal.
        """
        task_file = self.create_and_reach_review("Stale Patch Task", "work.py")
        branch = task_file
        patches_dir = os.path.join(self.dev_tasks_dir, "review", task_file, "patches")

        dev_repo = ensure_dev_repo(self.dev_tasks_dir)
        res = subprocess.run(
            ["git", "diff", "--name-only", f"main...{branch}"],
            cwd=dev_repo,
            capture_output=True,
            text=True,
            check=False,
        )
        changed_files = [f for f in res.stdout.splitlines() if f]
        self.assertTrue(
            changed_files,
            f"branch has changed files vs main (rc={res.returncode}, err={res.stderr})",
        )

        # simulate the stale artifact: corrupt one patch
        target = changed_files[0].replace(os.sep, "_") + ".patch"
        with open(os.path.join(patches_dir, target), "w") as f:
            f.write("stale content from an old base\n")

        # audit alone must refresh it to the branch tip - no state round-trip
        res = self.run_cmd(["audit", task_file])
        self.assertTrue(res["success"], res)
        res = subprocess.run(
            ["git", "diff", f"main..{branch}", "--", changed_files[0]],
            cwd=dev_repo,
            capture_output=True,
            text=True,
            check=False,
        )
        with open(os.path.join(patches_dir, target)) as f:
            self.assertEqual(
                f.read(),
                res.stdout,
                f"patch {target} was not refreshed to the branch tip",
            )
        with open(os.path.join(patches_dir, target)) as fh:
            self.assertNotIn("stale content", fh.read())

        # and again with the regression gate already passed (the Rc==PASSED
        # skip path used to refuse regeneration outright)
        self.complete_review_gate(task_file)
        with open(os.path.join(patches_dir, target), "w") as f:
            f.write("stale content after rc passed\n")
        res = self.run_cmd(["audit", task_file])
        self.assertTrue(res["success"], res)
        with open(os.path.join(patches_dir, target)) as f:
            self.assertNotIn("stale content", f.read())

    def test_review_reentry_refreshes_branch_changes_and_invalidates_receipts(self):
        task_file = self.create_and_reach_review(
            "Review Reentry Refresh Task", "code.py"
        )
        self.complete_review_gate(task_file)
        worktree = self.get_worktree(task_file)
        with open(os.path.join(worktree, "code.py"), "w") as f:
            f.write("def func():\n    return 2\n")
        subprocess.run(  # noqa: PLW1510
            ["git", "add", "code.py"], cwd=worktree, capture_output=True
        )
        subprocess.run(  # noqa: PLW1510
            ["git", "commit", "-m", "Change reviewed code"],
            cwd=worktree,
            capture_output=True,
        )

        self.reenter_review(task_file)

        dev_repo = ensure_dev_repo(self.dev_tasks_dir)
        expected = subprocess.run(
            ["git", "diff", f"main..{task_file}", "--", "code.py"],
            cwd=dev_repo,
            capture_output=True,
            text=True,
            check=False,
        ).stdout
        patch_path = os.path.join(
            self.dev_tasks_dir, "review", task_file, "patches", "code.py.patch"
        )
        with open(patch_path) as f:
            self.assertEqual(f.read(), expected)
        meta = self.get_meta(task_file)
        self.assertFalse(meta.get("Reviewed"))
        self.assertFalse(meta.get("Rc"))
        for patch_info in meta.get("PatchFiles", []):
            self.assertTrue(os.path.exists(patch_info["patch_path"]))
            self.assertNotIn(".ops/staging", patch_info["patch_path"])
        self.assertFalse(
            os.path.exists(
                os.path.join(self.dev_tasks_dir, "review", task_file, "reviews.json")
            )
        )
        res = self.run_cmd(["modify", task_file, "--regression-check"])
        self.assertFalse(res["success"], res)

    def test_review_reentry_prunes_patches_outside_changed_set(self):
        task_file = self.create_and_reach_review(
            "Review Prune Task", ["keep.py", "remove.py"]
        )
        worktree = self.get_worktree(task_file)
        os.remove(os.path.join(worktree, "remove.py"))
        subprocess.run(  # noqa: PLW1510
            ["git", "add", "-A"], cwd=worktree, capture_output=True
        )
        subprocess.run(  # noqa: PLW1510
            ["git", "commit", "-m", "Remove reviewed file"],
            cwd=worktree,
            capture_output=True,
        )

        self.reenter_review(task_file)

        patches_dir = os.path.join(self.dev_tasks_dir, "review", task_file, "patches")
        patch_names = {
            name for name in os.listdir(patches_dir) if name.endswith(".patch")
        }
        self.assertIn("keep.py.patch", patch_names)
        self.assertNotIn("remove.py.patch", patch_names)

    def test_review_reentry_refreshes_after_main_sync_merge(self):
        task_file = self.create_and_reach_review("Review Sync Merge Task", "code.py")
        self.complete_review_gate(task_file)
        dev_repo = ensure_dev_repo(self.dev_tasks_dir)
        subprocess.run(  # noqa: PLW1510
            ["git", "checkout", "main"], cwd=dev_repo, capture_output=True
        )
        with open(os.path.join(dev_repo, "sync.txt"), "w") as f:
            f.write("main moved\n")
        subprocess.run(  # noqa: PLW1510
            ["git", "add", "sync.txt"], cwd=dev_repo, capture_output=True
        )
        subprocess.run(  # noqa: PLW1510
            ["git", "commit", "-m", "Advance main"],
            cwd=dev_repo,
            capture_output=True,
        )

        self.reenter_review(task_file)

        merged = subprocess.run(
            ["git", "merge-base", "--is-ancestor", "main", task_file],
            cwd=dev_repo,
            capture_output=True,
            check=False,
        )
        self.assertEqual(merged.returncode, 0, "task branch did not sync main")
        expected = subprocess.run(
            ["git", "diff", f"main..{task_file}", "--", "code.py"],
            cwd=dev_repo,
            capture_output=True,
            text=True,
            check=False,
        ).stdout
        patch_path = os.path.join(
            self.dev_tasks_dir, "review", task_file, "patches", "code.py.patch"
        )
        with open(patch_path) as f:
            self.assertEqual(f.read(), expected)
        self.assertFalse(self.get_meta(task_file).get("Reviewed"))

    def test_audit_refreshes_new_branch_file_without_manual_deletion(self):
        task_file = self.create_and_reach_review(
            "Audit Refresh New File Task", "code.py"
        )
        self.complete_review_gate(task_file)
        worktree = self.get_worktree(task_file)
        with open(os.path.join(worktree, "new.py"), "w") as f:
            f.write("value = 1\n")
        subprocess.run(  # noqa: PLW1510
            ["git", "add", "new.py"], cwd=worktree, capture_output=True
        )
        subprocess.run(  # noqa: PLW1510
            ["git", "commit", "-m", "Add new file"],
            cwd=worktree,
            capture_output=True,
        )

        res = self.run_cmd(["audit", task_file])
        self.assertTrue(res["success"], res)
        patches_dir = os.path.join(self.dev_tasks_dir, "review", task_file, "patches")
        self.assertTrue(
            os.path.exists(os.path.join(patches_dir, "new.py.patch")),
            "audit did not add the new branch file",
        )
        self.assertFalse(self.get_meta(task_file).get("Reviewed"))
        self.assertFalse(self.get_meta(task_file).get("Rc"))
        self.assertFalse(
            os.path.exists(
                os.path.join(self.dev_tasks_dir, "review", task_file, "reviews.json")
            )
        )

    def test_regression_check_requires_receipt_for_every_current_patch(self):
        task_file = self.create_and_reach_review("Receipt Coverage Task", "code.py")
        self.complete_review_gate(task_file)
        reviews_path = os.path.join(
            self.dev_tasks_dir, "review", task_file, "reviews.json"
        )
        with open(reviews_path) as f:
            reviews = json.load(f)
        reviews["reviews"] = []
        with open(reviews_path, "w") as f:
            json.dump(reviews, f)

        res = self.run_cmd(["modify", task_file, "--regression-check"])
        self.assertFalse(res["success"], res)
        self.assertIn(
            "mismatch",
            res.get("error", "").lower() + " " + res.get("hint", "").lower(),
        )

    def test_empty_diff_auto_passes_regression_check(self):
        task_file = self.create_and_reach_review(
            "Empty Diff Auto Pass Test Task", "code.py"
        )
        # Simulate "no actual changes to review": clear PatchFiles + patch dir,
        # reset Reviewed/Rc. The gate must auto-pass without a review record.
        review_dir = os.path.join(self.dev_tasks_dir, "review", task_file)
        patches_dir = os.path.join(review_dir, "patches")
        audit_path = os.path.join(self.dev_tasks_dir, "review", f"{task_file}.audit")
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
