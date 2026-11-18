"""Validation must run against a fresh task worktree, not stale branch code."""

import os
import subprocess
import tempfile
import unittest
from types import SimpleNamespace

from tasks_ai.git_service import GitService
from tasks_ai.messages import MessageRegistry
from tasks_ai.pipeline_hooks import ValidationHook


def git(args, cwd):
    return subprocess.run(
        ["git", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=True,
    )


class FakeWorktrees:
    def __init__(self, path):
        self.path = path

    def get_worktree_path(self, task_id):
        return self.path


class FakeCLI:
    def __init__(self, git_service, worktree_path):
        self.git = git_service
        self.git._worktree_manager = FakeWorktrees(worktree_path)
        self.context = SimpleNamespace(
            repo_root=git_service.context.main_repo_root,
            main_repo_root=git_service.context.main_repo_root,
        )
        self.validations = []
        self.next_step_calls = []

    def console(self, *args):
        pass

    def log(self, message):
        pass

    def error(self, code, **kwargs):
        raise RuntimeError(code)

    def next_step(self, code, **kwargs):
        self.next_step_calls.append((code, kwargs))
        raise SystemExit(1)

    def run_tool(self, tool_name=None, fix=False, cwd=None):
        self.validations.append((tool_name, cwd))

    def _atomic_write(self, path, task):
        pass


class ValidationFreshnessTest(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="validation_sync_")
        self.main = os.path.join(self.root, "main")
        self.branch = "461-task-stale-validation"
        self.task_id = "461"
        os.makedirs(self.main)
        git(["init", "-b", "main"], self.main)
        git(["config", "user.email", "test@example.com"], self.main)
        git(["config", "user.name", "Test User"], self.main)
        with open(os.path.join(self.main, "base.txt"), "w", encoding="utf-8") as handle:
            handle.write("base\n")
        git(["add", "."], self.main)
        git(["commit", "-m", "base"], self.main)
        git(["branch", self.branch], self.main)
        self.worktree = os.path.join(self.root, "worktree")
        git(["worktree", "add", self.worktree, self.branch], self.main)

        context = SimpleNamespace(
            repo_root=self.main,
            main_repo_root=self.main,
            dev=False,
        )
        self.git = GitService(context)
        self.cli = FakeCLI(self.git, self.worktree)
        self.task = SimpleNamespace(
            metadata={"Id": self.task_id, "Br": self.branch},
            parts={},
        )
        self.task_dir = tempfile.mkdtemp(prefix="validation_task_")
        for name in ("criteria.md", "progress.md"):
            with open(
                os.path.join(self.task_dir, name), "w", encoding="utf-8"
            ) as handle:
                handle.write("ok\n")

    def tearDown(self):
        subprocess.run(
            ["git", "worktree", "remove", "--force", self.worktree],
            cwd=self.main,
            capture_output=True,
            check=False,
        )
        subprocess.run(["rm", "-rf", self.root], check=False)
        subprocess.run(["rm", "-rf", self.task_dir], check=False)

    def advance_main(self, filename, content):
        with open(os.path.join(self.main, filename), "w", encoding="utf-8") as handle:
            handle.write(content)
        git(["add", "."], self.main)
        git(["commit", "-m", "advance main"], self.main)

    def validate(self):
        ValidationHook().execute(
            self.cli,
            self.task,
            "PROGRESSING",
            "TESTING",
            self.task_dir,
        )

    def test_stale_clean_branch_is_synchronized_before_validation(self):
        self.advance_main("from-main.txt", "new main code\n")

        self.validate()

        self.assertTrue(os.path.exists(os.path.join(self.worktree, "from-main.txt")))
        self.assertEqual([("all", self.worktree)], self.cli.validations)

    def test_stale_branch_with_local_work_blocks_without_touching_files(self):
        self.advance_main("from-main.txt", "new main code\n")
        tracked = os.path.join(self.worktree, "base.txt")
        untracked = os.path.join(self.worktree, "scratch.txt")
        with open(tracked, "w", encoding="utf-8") as handle:
            handle.write("local edit\n")
        with open(untracked, "w", encoding="utf-8") as handle:
            handle.write("untracked work\n")

        with self.assertRaises(SystemExit):
            self.validate()

        self.assertEqual([], self.cli.validations)
        code, details = self.cli.next_step_calls[0]
        self.assertEqual("WORKTREE_LOCAL_WORK", code)
        self.assertEqual(self.task_id, details["task_id"])
        self.assertEqual(self.branch, details["branch"])
        self.assertEqual("main", details["default"])
        self.assertTrue(details["local_commit"])
        self.assertEqual("base.txt, scratch.txt", details["paths"])
        self.assertEqual(self.worktree, details["worktree_path"])
        hint = MessageRegistry().get_next_step_hint(code, **details)
        self.assertIn("Commit or stash the local work", hint)
        self.assertIn("./hammer tasks mount 461", hint)
        with open(tracked, encoding="utf-8") as handle:
            self.assertEqual("local edit\n", handle.read())
        with open(untracked, encoding="utf-8") as handle:
            self.assertEqual("untracked work\n", handle.read())
        self.assertFalse(os.path.exists(os.path.join(self.worktree, "from-main.txt")))

    def test_stale_conflict_blocks_before_validation(self):
        shared = os.path.join(self.worktree, "base.txt")
        with open(shared, "w", encoding="utf-8") as handle:
            handle.write("branch side\n")
        git(["add", "."], self.worktree)
        git(["commit", "-m", "branch edit"], self.worktree)
        self.advance_main("base.txt", "main side\n")

        with self.assertRaises(SystemExit):
            self.validate()

        self.assertEqual([], self.cli.validations)
        code, details = self.cli.next_step_calls[0]
        self.assertEqual("WORKTREE_SYNC_CONFLICT", code)
        self.assertEqual(self.task_id, details["task_id"])
        self.assertEqual(self.branch, details["branch"])
        self.assertEqual("main", details["default"])
        self.assertTrue(details["local_commit"])
        self.assertEqual("base.txt", details["paths"])
        self.assertEqual(self.worktree, details["worktree_path"])
        hint = MessageRegistry().get_next_step_hint(code, **details)
        self.assertIn("Resolve every conflicting path manually", hint)
        self.assertIn("git add <paths>", hint)
        self.assertIn("./hammer tasks mount 461", hint)
        with open(shared, encoding="utf-8") as handle:
            self.assertEqual("branch side\n", handle.read())

    def test_validation_runs_in_task_worktree_after_sync(self):
        self.advance_main("from-main.txt", "new main code\n")

        self.validate()

        validation_cwd = self.cli.validations[0][1]
        self.assertEqual(self.worktree, validation_cwd)
        self.assertTrue(os.path.exists(os.path.join(validation_cwd, "from-main.txt")))


if __name__ == "__main__":
    unittest.main()
