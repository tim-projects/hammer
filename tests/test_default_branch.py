"""User tests for task 342: gates and sync must resolve the actual default
branch instead of assuming 'main'.

Two things are verified end to end:
  - a repo whose default branch is 'master' promotes through the whole pipeline
  - a repo with neither main nor master fails with an actionable error
"""

import json
import os
import shutil
import subprocess
import tempfile
import types
import unittest


def git(args, cwd, check=False):
    return subprocess.run(
        ["git"] + args, cwd=cwd, capture_output=True, text=True, check=check
    )


RESEARCH = (
    "Read tasks_ai/pipeline_hooks.py ResearchGateHook, tasks_ai/pipeline.py "
    "transition rules and this suite before driving the task."
)


def _make_test_root():
    """Create the test repo outside /tmp (validate_path short-circuits there)."""
    try:
        return tempfile.mkdtemp(prefix="default_branch_test_", dir="/var/tmp")
    except OSError as exc:
        raise unittest.SkipTest(f"no writable non-/tmp temp dir (/var/tmp): {exc}")


class MasterRepoTestBase(unittest.TestCase):
    """A hammer repo whose default branch is 'master', with no remote."""

    default_branch = "master"

    def setUp(self):
        self.test_dir = _make_test_root()
        self.repo_dir = os.path.join(self.test_dir, "repo")
        os.makedirs(self.repo_dir)
        git(["init", "-b", self.default_branch], self.repo_dir)
        git(["config", "user.email", "test@example.com"], self.repo_dir)
        git(["config", "user.name", "Test User"], self.repo_dir)
        git(["config", "commit.gpgsign", "false"], self.repo_dir)
        with open(os.path.join(self.repo_dir, "README.md"), "w") as f:
            f.write("# Default Branch Test Repo")
        git(["add", "README.md"], self.repo_dir)
        git(["commit", "-m", "Initial commit"], self.repo_dir)

        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.script_path = os.path.abspath(os.path.join(self.repo_dir, "hammer"))
        os.symlink(os.path.join(project_root, "hammer"), self.script_path)
        git(["add", "hammer"], self.repo_dir)
        git(["commit", "-m", "Add hammer"], self.repo_dir)

        tasks_dir = os.path.join(self.repo_dir, ".tasks")
        os.makedirs(tasks_dir, exist_ok=True)
        with open(os.path.join(tasks_dir, "config.yaml"), "w") as f:
            json.dump(
                {
                    "repo": {
                        "lint": "noop",
                        "test": "noop",
                        "type_check": "noop",
                        "format": "noop",
                        "skip_push": True,
                    }
                },
                f,
            )

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def run_cmd(self, args, cwd=None):
        result = subprocess.run(  # noqa: PLW1510
            [self.script_path, "tasks", "-j"] + args,
            cwd=cwd or self.repo_dir,
            capture_output=True,
            text=True,
        )
        try:
            return json.loads(result.stdout)
        except json.JSONDecodeError:
            return {
                "success": False,
                "error": "JSON Decode Error",
                "stdout": result.stdout,
                "stderr": result.stderr,
            }

    def create_task(self, title="Master Repo Pipeline Under Verification"):
        res = self.run_cmd(
            [
                "create",
                title,
                "--story",
                "As a user on a master-named repo I need the pipeline to resolve the real default branch.",
                "--tech",
                "Gates, sync and merge paths must not hardcode main.",
                "--criteria",
                "Promotion succeeds on a repo whose default branch is master.",
                "--plan",
                "1. Create task. 2. Promote. 3. Verify merges landed on master.",
            ]
        )
        self.assertTrue(res["success"], f"create failed: {res}")
        return res["data"]

    def complete_criteria(self, task_file):
        for state in (
            "backlog",
            "ready",
            "progressing",
            "testing",
            "review",
            "staging",
            "done",
            "archived",
        ):
            criteria = os.path.join(
                self.repo_dir, ".tasks", state, task_file, "criteria.md"
            )
            if os.path.exists(criteria):
                with open(criteria) as f:
                    content = f.read()
                with open(criteria, "w") as f:
                    f.write(content.replace("- [ ]", "- [x]"))

    def promote(self, data):
        """Drive a task with real commits through the full promotion chain."""
        task_file = data["file"]
        task_id = str(data["id"])
        worktree_path = data.get("worktree") or os.path.join(
            self.repo_dir, ".task-worktrees", task_file
        )

        self.assertTrue(
            self.run_cmd(["move", task_file, "READY"])["success"],
            "move READY failed",
        )
        self.assertTrue(
            self.run_cmd(["modify", task_file, "--research", RESEARCH])["success"],
            "research record failed",
        )
        self.assertTrue(
            self.run_cmd(["move", task_file, "PROGRESSING"])["success"],
            "move PROGRESSING failed",
        )

        with open(os.path.join(worktree_path, "feature.py"), "w") as f:
            f.write("def feature():\n    return True\n")
        git(["add", "feature.py"], worktree_path)
        git(["commit", "-m", "Add feature"], worktree_path)

        self.assertTrue(
            self.run_cmd(["checkpoint", task_file])["success"], "checkpoint failed"
        )

        self.complete_criteria(task_file)
        self.assertTrue(
            self.run_cmd(["move", task_file, "TESTING"])["success"],
            "move TESTING failed",
        )

        self.assertTrue(
            self.run_cmd(["move", task_file, "REVIEW"])["success"],
            "move REVIEW failed",
        )

        for args in (
            ["audit", task_file],
            ["verify", task_file, "--proof", "Reviewed patches and criteria."],
            ["modify", task_file, "--reviewed"],
            ["modify", task_file, "--regression-check"],
        ):
            res = self.run_cmd(args)
            self.assertTrue(res["success"], f"{args} failed: {res}")

        for state in ("STAGING", "DONE", "ARCHIVED"):
            self.complete_criteria(task_file)
            res = self.run_cmd(
                ["move", task_file, state] + (["-y"] if state == "ARCHIVED" else [])
            )
            self.assertTrue(res["success"], f"move {state} failed: {res}")

        return task_id


class TestMasterNamedRepo(MasterRepoTestBase):
    def test_promotion_resolves_master(self):
        """create -> move -> checkpoint -> gate -> merge works on a master repo."""
        data = self.create_task()
        self.promote(data)

        # The promotion merges landed on master, not a nonexistent main.
        merged = subprocess.run(  # noqa: PLW1510
            ["git", "log", "--merges", "--oneline", "master"],
            cwd=self.repo_dir,
            capture_output=True,
            text=True,
        ).stdout
        self.assertIn("into master", merged, f"no promotion merge on master: {merged}")
        self.assertIn(
            data["branch"], merged, f"task branch not merged into master: {merged}"
        )

    def test_worktree_sync_merges_master(self):
        """The PROGRESSING sync hook merges master (not main) into the worktree."""
        data = self.create_task()
        task_file = data["file"]
        master_tip = git(["rev-parse", "master"], self.repo_dir).stdout.strip()

        self.assertTrue(
            self.run_cmd(["move", task_file, "READY"])["success"], "move READY failed"
        )
        self.assertTrue(
            self.run_cmd(["modify", task_file, "--research", RESEARCH])["success"],
            "research record failed",
        )
        self.assertTrue(
            self.run_cmd(["move", task_file, "PROGRESSING"])["success"],
            "move PROGRESSING failed",
        )

        worktree_path = os.path.join(self.repo_dir, ".task-worktrees", task_file)
        merged = subprocess.run(  # noqa: PLW1510
            ["git", "merge-base", "--is-ancestor", master_tip, "HEAD"],
            cwd=worktree_path,
            capture_output=True,
            text=True,
        )
        self.assertEqual(
            merged.returncode, 0, "master tip not merged into the worktree"
        )


class TestNoDefaultBranch(MasterRepoTestBase):
    default_branch = "trunk"

    def test_promotion_fails_with_actionable_error(self):
        """A repo with neither main nor master errors clearly, no git fatal."""
        data = self.create_task()
        task_file = data["file"]

        self.assertTrue(
            self.run_cmd(["move", task_file, "READY"])["success"], "move READY failed"
        )
        self.assertTrue(
            self.run_cmd(["modify", task_file, "--research", RESEARCH])["success"],
            "research record failed",
        )
        self.assertTrue(
            self.run_cmd(["move", task_file, "PROGRESSING"])["success"],
            "move PROGRESSING failed",
        )

        worktree_path = data["worktree"]
        with open(os.path.join(worktree_path, "feature.py"), "w") as f:
            f.write("def feature():\n    return True\n")
        git(["add", "feature.py"], worktree_path)
        git(["commit", "-m", "Add feature"], worktree_path)

        self.complete_criteria(task_file)
        self.assertTrue(
            self.run_cmd(["move", task_file, "TESTING"])["success"],
            "move TESTING failed",
        )
        self.assertTrue(
            self.run_cmd(["move", task_file, "REVIEW"])["success"],
            "move REVIEW failed",
        )
        for args in (
            ["audit", task_file],
            ["verify", task_file, "--proof", "Reviewed patches and criteria."],
            ["modify", task_file, "--reviewed"],
            ["modify", task_file, "--regression-check"],
        ):
            res = self.run_cmd(args)
            self.assertTrue(res["success"], f"{args} failed: {res}")

        res = self.run_cmd(["move", task_file, "DONE"])
        self.assertFalse(res["success"], f"DONE unexpectedly succeeded: {res}")
        # Actionable message, not a raw git fatal.
        self.assertIn("No default branch", res.get("error", ""))
        self.assertNotIn("Not a valid object name", json.dumps(res))


class TestGetDefaultBranch(unittest.TestCase):
    def setUp(self):
        self.test_dir = _make_test_root()
        self.repo_dir = os.path.join(self.test_dir, "repo")
        os.makedirs(self.repo_dir)
        git(["init", "-b", "master"], self.repo_dir)
        git(["config", "user.email", "test@example.com"], self.repo_dir)
        git(["config", "user.name", "Test User"], self.repo_dir)
        with open(os.path.join(self.repo_dir, "README.md"), "w") as f:
            f.write("# probe repo")
        git(["add", "README.md"], self.repo_dir)
        git(["commit", "-m", "Initial commit"], self.repo_dir)

        from tasks_ai.git_service import GitService

        context = types.SimpleNamespace(
            repo_root=self.repo_dir, main_repo_root=self.repo_dir, dev=False
        )
        self.git = GitService(context)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_returns_master_when_main_absent(self):
        self.assertEqual(self.git.get_default_branch(), "master")

    def test_prefers_main_when_both_exist(self):
        git(["branch", "main"], self.repo_dir)
        self.assertEqual(self.git.get_default_branch(), "main")

    def test_returns_none_when_neither_exists(self):
        git(["checkout", "-b", "trunk"], self.repo_dir)
        git(["branch", "-D", "master"], self.repo_dir, check=True)
        self.assertIsNone(self.git.get_default_branch())

    def test_is_merged_false_without_default_branch(self):
        git(["checkout", "-b", "trunk"], self.repo_dir)
        git(["branch", "-D", "master"], self.repo_dir, check=True)
        self.assertFalse(self.git.is_merged("trunk"))


class TestNoHardcodedMainInGatePaths(unittest.TestCase):
    # Allowed occurrences: the default-branch probe list and the actionable
    # NO_DEFAULT_BRANCH message that names both candidate branches.
    ALLOWED = ('["main", "master"]', "No 'main' or 'master'")

    def test_gate_files_have_no_main_literal(self):
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        files = [
            "tasks_ai/git_service.py",
            "tasks_ai/pipeline.py",
            "tasks_ai/commands/move.py",
            "tasks_ai/worktree_manager.py",
            "tasks_ai/commands/cleanup.py",
            "tasks_ai/pipeline_hooks.py",
            "tasks_ai/utils.py",
        ]
        for rel in files:
            with open(os.path.join(root, rel)) as f:
                for i, line in enumerate(f, 1):
                    if '"main"' in line or "'main'" in line:
                        self.assertTrue(
                            any(ok in line for ok in self.ALLOWED),
                            f"{rel}:{i} still hardcodes main: {line.strip()}",
                        )


if __name__ == "__main__":
    unittest.main()
