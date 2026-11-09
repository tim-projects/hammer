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
        self.dev_tasks_dir = tempfile.mkdtemp(prefix="hammer_tasks_")
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
        config_data = {"repo": {"lint": "ruff", "test": "/bin/true", "type_check": "/bin/true", "format": "ruff"}}
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

    def review_every_patch(self, file):
        """Read each review patch in turn via 'tasks review' until none remain."""
        while True:
            res = self.run_cmd(["review", file])
            self.assertTrue(res["success"], f"review failed for {file}: {res}")
            if not res["data"]["remaining"]:
                return

    def complete_review_gate(self, file):
        """audit -> verify -> review every patch -> --reviewed -> --regression-check."""
        self.review_every_patch(file)
        res = self.run_cmd(["modify", file, "--reviewed", "Read every patch: the fix is scoped and the tests cover it."])
        self.assertTrue(res["success"], f"--reviewed failed for {file}: {res}")
        res = self.run_cmd(["audit", file])
        self.assertTrue(res["success"], f"audit failed for {file}: {res}")
        res = self.run_cmd(["verify", file, "--proof", "Reviewed patches and criteria pass."])
        self.assertTrue(res["success"], f"verify failed for {file}: {res}")
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
        self.run_cmd(["move", task_file, "PROGRESSING"])

        # Commit real work in the worktree (not main repo) so the branch gets the commit
        work_dir = worktree_path if worktree_path and os.path.exists(worktree_path) else self.repo_dir
        subprocess.run(["git", "checkout", branch], cwd=work_dir, capture_output=True)  # noqa: PLW1510
        with open(os.path.join(work_dir, work_file), "w") as f:
            f.write("def func():\n    pass\n")
        subprocess.run(["git", "add", work_file], cwd=work_dir, capture_output=True)  # noqa: PLW1510
        subprocess.run(  # noqa: PLW1510
            ["git", "commit", "-m", "Work"], cwd=work_dir, capture_output=True
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
        subprocess.run(["git", "checkout", branch], cwd=work_dir, capture_output=True)  # noqa: PLW1510
        # REVIEW (current stage=testing) also needs checkboxes complete.
        self.complete_current_criteria(task_file)
        self.run_cmd(["move", task_file, "REVIEW"])
        return task_file

    def complete_current_criteria(self, file):
        """Mark the criteria file in the task's current pipeline stage as done."""
        tasks_root = self.dev_tasks_dir
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
        review_dir = os.path.join(self.dev_tasks_dir, "review", task_file)
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
        patches_dir = os.path.join(self.dev_tasks_dir, "review", task_file, "patches")
        patches = [f for f in os.listdir(patches_dir) if f.endswith(".patch")]
        self.assertTrue(patches, "expected generated patches")
        with open(os.path.join(patches_dir, patches[0]), "a") as f:
            f.write("\n+ tampered line\n")

        res = self.run_cmd(["modify", task_file, "--regression-check"])
        self.assertFalse(res["success"], res)
        low = res.get("error", "").lower() + " " + res.get("hint", "").lower()
        self.assertIn("mismatch", low)

    # --- per-file review flow (task 376) ---
    def _patches(self, task_file):
        patches_dir = os.path.join(self.dev_tasks_dir, "review", task_file, "patches")
        return sorted(f for f in os.listdir(patches_dir) if f.endswith(".patch"))

    def _reviews(self, task_file):
        with open(os.path.join(self.dev_tasks_dir, "review", task_file, "reviews.json")) as f:
            return json.load(f)

    def _add_patch(self, task_file, name, content):
        """Materialize an extra patch file and register it in PatchFiles."""
        patches_dir = os.path.join(self.dev_tasks_dir, "review", task_file, "patches")
        with open(os.path.join(patches_dir, f"{name}.patch"), "w") as f:
            f.write(content)
        review_dir = os.path.join(self.dev_tasks_dir, "review", task_file)
        task = FM.load(review_dir)
        task.metadata["PatchFiles"].append(
            {"file": name, "patch_path": os.path.join(patches_dir, f"{name}.patch")}
        )
        FM.dump(task, review_dir)

    def test_review_reads_one_patch_and_records_a_receipt(self):
        task_file = self.create_and_reach_review("Review One Patch Test Task", "code.py")
        patches = self._patches(task_file)
        self.assertTrue(patches, "expected generated patches")

        res = self.run_cmd(["review", task_file])
        self.assertTrue(res["success"], res)
        self.assertEqual(res["data"]["reviewed"], 1)
        self.assertEqual(res["data"]["total"], len(patches))
        self.assertEqual(res["data"]["remaining"], [])
        self.assertEqual(res["data"]["patch"], patches[0])
        self.assertIn("diff", res["data"]["content"])

        reviews = self._reviews(task_file)
        receipt = reviews["reviews"][0]
        self.assertEqual(receipt["patch"], patches[0])
        self.assertEqual(receipt["seq"], 1)
        self.assertIsNone(receipt["prev_hash"])
        self.assertGreater(receipt["bytes"], 0)

    def test_review_is_repeatable_and_reports_finalize(self):
        task_file = self.create_and_reach_review("Repeat Review Report Task", "code.py")
        self.review_every_patch(task_file)
        text = subprocess.run(  # noqa: PLW1510
            [self.script_path, "tasks", "--dev", "review", task_file],
            cwd=self.repo_dir, capture_output=True, text=True,
        )
        self.assertEqual(text.returncode, 0, text.stderr)
        self.assertIn("already reviewed", text.stdout)
        self.assertIn("Finalize the review", text.stdout)

    def test_review_reports_what_is_left_and_refuses_unknown_patches(self):
        task_file = self.create_and_reach_review("Review Remaining Test Task", "code.py")
        res = self.run_cmd(["review", task_file, "not_a_patch.patch"])
        self.assertFalse(res["success"], res)

    def test_finalize_refused_until_every_patch_is_read(self):
        task_file = self.create_and_reach_review("Review Coverage Test Task", "code.py")
        self._add_patch(task_file, "extra.py", "diff --git a/extra.py b/extra.py\n+second file\n")
        self.run_cmd(["review", task_file])  # first patch only

        res = self.run_cmd(["modify", task_file, "--reviewed", "Read the first patch carefully and nothing else yet."])
        self.assertFalse(res["success"], res)
        low = res.get("error", "").lower() + " " + res.get("hint", "").lower()
        self.assertIn("extra.py.patch", low, f"the unread patch must be named: {res}")

    def test_incidental_open_does_not_satisfy_the_review(self):
        task_file = self.create_and_reach_review("Incidental Open Test Task", "code.py")
        # Every tool that merely opens the file: not a review.
        for patch in self._patches(task_file):
            with open(os.path.join(self.dev_tasks_dir, "review", task_file, "patches", patch)) as f:
                f.read()

        res = self.run_cmd(["modify", task_file, "--reviewed", "I never ran tasks review, only opened the files."])
        self.assertFalse(res["success"], res)
        self.assertIn("incomplete", res.get("error", "").lower(), res)

    def test_finalize_requires_a_substantive_summary(self):
        task_file = self.create_and_reach_review("Review Summary Test Task", "code.py")
        self.review_every_patch(task_file)

        bare = self.run_cmd(["modify", task_file, "--reviewed"])
        self.assertFalse(bare["success"], bare)
        short = self.run_cmd(["modify", task_file, "--reviewed", "looks fine"])
        self.assertFalse(short["success"], short)

        res = self.run_cmd(["modify", task_file, "--reviewed", "Read every patch: the fix is scoped and the tests cover it."])
        self.assertTrue(res["success"], res)
        self.assertTrue(self.get_meta(task_file).get("Reviewed"))
        self.assertIn("summary", self._reviews(task_file))

    def test_repeating_review_keeps_the_summary(self):
        task_file = self.create_and_reach_review("Repeat Review Test Task", "code.py")
        self.review_every_patch(task_file)
        res = self.run_cmd(["modify", task_file, "--reviewed", "Read every patch: the fix is scoped and the tests cover it."])
        self.assertTrue(res["success"], res)

        res = self.run_cmd(["review", task_file])
        self.assertTrue(res["success"], res)
        self.assertEqual(res["data"]["remaining"], [])
        self.assertIn("summary", self._reviews(task_file))

    def test_tampered_review_record_fails_integrity(self):
        task_file = self.create_and_reach_review("Tampered Review Record Task", "code.py")
        self.review_every_patch(task_file)
        res = self.run_cmd(["modify", task_file, "--reviewed", "Read every patch: the fix is scoped and the tests cover it."])
        self.assertTrue(res["success"], res)
        self.run_cmd(["audit", task_file])
        res = self.run_cmd(["verify", task_file, "--proof", "Reviewed patches and criteria pass."])
        self.assertTrue(res["success"], res)

        reviews_path = os.path.join(self.dev_tasks_dir, "review", task_file, "reviews.json")
        with open(reviews_path) as f:
            data = json.load(f)
        data["summary"] = "Rewritten after the fact to dodge the review."
        with open(reviews_path, "w") as f:
            json.dump(data, f)

        res = self.run_cmd(["modify", task_file, "--regression-check"])
        self.assertFalse(res["success"], res)
        self.assertIn("integrity", (res.get("error", "") + res.get("hint", "")).lower(), res)

    def test_review_rejects_unknown_patch_and_non_review_state(self):
        task_file = self.create_and_reach_review("Review Unknown Patch Task", "code.py")
        res = self.run_cmd(["review", task_file, "not_a_patch.patch"])
        self.assertFalse(res["success"], res)

        back = self.run_cmd(["move", task_file, "TESTING"])
        self.assertTrue(back["success"], back)
        res = self.run_cmd(["review", task_file])
        self.assertFalse(res["success"], res)

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
