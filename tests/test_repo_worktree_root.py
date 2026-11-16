import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
REPO_SCRIPT = PROJECT_ROOT / "repo.py"


class TestRepoLinkedWorktreeRoot(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.main = os.path.join(self.tmp.name, "main")
        self.worktree = os.path.join(self.tmp.name, "task-worktree")
        os.makedirs(self.main)
        self.git("init", "-b", "main")
        self.git("config", "user.email", "test@example.com")
        self.git("config", "user.name", "Test User")
        self.write("README.md", "initial\n")
        self.git("add", "README.md")
        self.git("commit", "-m", "initial")
        os.makedirs(os.path.dirname(self.worktree), exist_ok=True)
        self.git("worktree", "add", "-b", "123-task-example", self.worktree)
        os.makedirs(os.path.join(self.main, ".tasks"), exist_ok=True)
        with open(
            os.path.join(self.main, ".tasks", "worktrees.json"), "w", encoding="utf-8"
        ) as handle:
            json.dump(
                {
                    "worktrees": {
                        "123": {
                            "branch": "123-task-example",
                            "path": self.worktree,
                        }
                    }
                },
                handle,
            )

    def tearDown(self):
        self.tmp.cleanup()

    def git(self, *args, cwd=None):
        result = subprocess.run(
            ["git", *args],
            cwd=cwd or self.main,
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode:
            self.fail(f"git {' '.join(args)} failed: {result.stderr}")
        return result

    def write(self, path, content):
        path = os.path.join(self.main, path)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(content)

    def make_check_stub(self, root):
        path = os.path.join(root, "check.py")
        with open(path, "w", encoding="utf-8") as handle:
            handle.write("raise SystemExit(0)\n")

    def test_repo_status_uses_the_invoked_linked_worktree(self):
        result = subprocess.run(
            [sys.executable, str(REPO_SCRIPT), "status"],
            cwd=self.worktree,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("On branch 123-task-example", result.stdout)

    def test_repo_merge_uses_registered_task_worktree(self):
        self.write("main.txt", "main change\n")
        self.git("add", "main.txt")
        self.git("commit", "-m", "main change")
        main_before = self.git("rev-parse", "HEAD").stdout.strip()

        result = subprocess.run(
            [
                sys.executable,
                str(REPO_SCRIPT),
                "merge",
                "-y",
                "main",
                "123-task-example",
            ],
            cwd=self.main,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(
            self.git("rev-parse", "--abbrev-ref", "HEAD").stdout.strip(), "main"
        )
        self.assertEqual(self.git("rev-parse", "HEAD").stdout.strip(), main_before)
        self.assertEqual(
            self.git(
                "merge-base", "--is-ancestor", "main", "123-task-example"
            ).returncode,
            0,
        )

    def test_repo_merge_refuses_dirty_task_worktree(self):
        self.write("main.txt", "main change\n")
        self.git("add", "main.txt")
        self.git("commit", "-m", "main change")
        dirty_path = os.path.join(self.worktree, "dirty.txt")
        with open(dirty_path, "w", encoding="utf-8") as handle:
            handle.write("uncommitted work\n")
        task_before = self.git("rev-parse", "123-task-example").stdout.strip()

        result = subprocess.run(
            [
                sys.executable,
                str(REPO_SCRIPT),
                "merge",
                "-y",
                "main",
                "123-task-example",
            ],
            cwd=self.main,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("uncommitted changes", result.stdout + result.stderr)
        with open(dirty_path, encoding="utf-8") as handle:
            self.assertEqual(handle.read(), "uncommitted work\n")
        self.assertEqual(
            self.git("rev-parse", "123-task-example").stdout.strip(), task_before
        )
        self.assertEqual(
            self.git("rev-parse", "--abbrev-ref", "HEAD").stdout.strip(), "main"
        )

    def test_repo_commit_uses_the_invoked_branch_and_ignores_tasks_repo(self):
        self.make_check_stub(self.main)
        self.make_check_stub(self.worktree)
        self.git("add", "check.py", cwd=self.worktree)
        self.git("commit", "-m", "test validator", cwd=self.worktree)
        tasks_repo = os.path.join(self.main, ".tasks-repo")
        os.makedirs(tasks_repo)
        self.git("init", cwd=tasks_repo)
        self.write(os.path.join(self.worktree, "change.txt"), "task change\n")

        main_before = self.git("rev-parse", "main").stdout.strip()
        result = subprocess.run(
            [sys.executable, str(REPO_SCRIPT), "commit", "-y", "task change"],
            cwd=self.worktree,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

        main_after = self.git("rev-parse", "main").stdout.strip()
        task_after = self.git("rev-parse", "123-task-example").stdout.strip()
        self.assertEqual(main_before, main_after)
        self.assertNotEqual(task_after, main_before)
        self.assertEqual(
            self.git("show", "--name-only", "--format=", task_after).stdout.split(),
            ["change.txt"],
        )
        self.assertNotIn(".tasks-repo", self.git("ls-files").stdout)

    def test_tasks_repo_is_ignored_by_repository_rules(self):
        ignore = (PROJECT_ROOT / ".gitignore").read_text(encoding="utf-8")
        self.write(os.path.join(self.main, ".gitignore"), ignore)
        self.git("add", ".gitignore")
        self.git("commit", "-m", "ignore rules")
        tasks_repo = os.path.join(self.main, ".tasks-repo")
        os.makedirs(tasks_repo)
        self.git("init", cwd=tasks_repo)
        self.write(os.path.join(self.main, "change.py"), "task change\n")

        status = self.git("status", "--porcelain").stdout
        self.assertNotIn(".tasks-repo", status)
        self.git("add", ".")
        staged = self.git("diff", "--cached", "--name-only").stdout
        self.assertNotIn(".tasks-repo", staged)
        self.assertIn("change.py", staged)


if __name__ == "__main__":
    unittest.main()
