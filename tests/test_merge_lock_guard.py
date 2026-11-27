import os
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import types
import unittest
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

from tasks_ai.git_service import GitService
from tasks_ai.utils import merge_lock

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def git(*args, cwd, check=True):
    return subprocess.run(
        ["git", *args], cwd=cwd, capture_output=True, text=True, check=check
    )


class MergeLockGuardTest(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="merge_lock_guard_")
        self.repo = os.path.join(self.root, "repo")
        os.makedirs(self.repo)
        git("init", "-b", "main", cwd=self.repo)
        git("config", "user.email", "test@example.com", cwd=self.repo)
        git("config", "user.name", "Test User", cwd=self.repo)
        git("config", "commit.gpgsign", "false", cwd=self.repo)
        with open(
            os.path.join(self.repo, "README.md"), "w", encoding="utf-8"
        ) as handle:
            handle.write("base\n")
        git("add", "README.md", cwd=self.repo)
        git("commit", "-m", "base", cwd=self.repo)
        git("branch", "provisioning", cwd=self.repo)
        context = types.SimpleNamespace(
            repo_root=self.repo,
            main_repo_root=self.repo,
            tasks_path=os.path.join(self.repo, ".tasks"),
            dev=True,
        )
        self.service = GitService(context)

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def create_branch(self, branch, filename):
        git("checkout", "-b", branch, "main", cwd=self.repo)
        with open(os.path.join(self.repo, filename), "w", encoding="utf-8") as handle:
            handle.write(f"{branch}\n")
        git("add", filename, cwd=self.repo)
        git("commit", "-m", branch, cwd=self.repo)
        git("checkout", "main", cwd=self.repo)
        return branch

    def test_two_concurrent_merges_create_two_commits(self):
        branch_a = self.create_branch("700-task-alpha", "alpha.txt")
        branch_b = self.create_branch("701-task-beta", "beta.txt")

        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [
                executor.submit(self.service.merge_branches, branch_a, "provisioning"),
                executor.submit(self.service.merge_branches, branch_b, "provisioning"),
            ]
            results = [future.result() for future in futures]

        self.assertTrue(all(result["created_commit"] for result in results))
        merge_count = git(
            "rev-list", "--count", "--merges", "provisioning", cwd=self.repo
        ).stdout.strip()
        self.assertEqual(merge_count, "2")
        self.assertNotIn(
            "index.lock",
            git("status", cwd=self.repo).stdout + git("status", cwd=self.repo).stderr,
        )

    def test_guard_rejection_prevents_merge(self):
        from tasks_ai.cli_errors import PipelineGuardRejected

        source = self.create_branch("800-task-good", "good.txt")
        self.create_branch("800-issue-duplicate", "duplicate.txt")
        before = git("rev-parse", "provisioning", cwd=self.repo).stdout.strip()

        guard = subprocess.run(
            [
                sys.executable,
                os.path.join(PROJECT_ROOT, "guard.py"),
                "check",
                "--branch",
                source,
            ],
            cwd=self.repo,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(guard.returncode, 1)
        self.assertIn("GUARD_DUPLICATE_ID", guard.stdout + guard.stderr)

        with self.assertRaises(PipelineGuardRejected) as caught:
            self.service.merge_branches(source, "provisioning")

        self.assertEqual(caught.exception.code, "GUARD_DUPLICATE_ID")
        after = git("rev-parse", "provisioning", cwd=self.repo).stdout.strip()
        self.assertEqual(before, after)

    def test_repo_merge_refuses_guard_rejected_source(self):
        source = self.create_branch("810-task-good", "good.txt")
        self.create_branch("810-issue-duplicate", "duplicate.txt")
        git("branch", "staging", cwd=self.repo)
        before = git("rev-parse", "staging", cwd=self.repo).stdout.strip()

        result = subprocess.run(
            [
                sys.executable,
                os.path.join(PROJECT_ROOT, "repo.py"),
                "merge",
                source,
                "staging",
                "-y",
            ],
            cwd=self.repo,
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(result.returncode, 1)
        self.assertIn("GUARD_DUPLICATE_ID", result.stdout + result.stderr)
        after = git("rev-parse", "staging", cwd=self.repo).stdout.strip()
        self.assertEqual(before, after)

    def test_linked_worktree_uses_shared_main_lock(self):
        worktree = os.path.join(self.root, "linked-worktree")
        git(
            "worktree",
            "add",
            "-b",
            "711-task-linked-worktree",
            worktree,
            cwd=self.repo,
        )
        self.assertTrue(os.path.isfile(os.path.join(worktree, ".git")))

        holder_ready = threading.Event()
        release_holder = threading.Event()
        waiter_acquired = threading.Event()

        def hold_main_lock():
            with merge_lock(self.repo):
                holder_ready.set()
                release_holder.wait(timeout=10)

        def acquire_from_worktree():
            with merge_lock(worktree):
                waiter_acquired.set()

        with ThreadPoolExecutor(max_workers=2) as executor:
            holder = executor.submit(hold_main_lock)
            try:
                self.assertTrue(holder_ready.wait(timeout=5))
                waiter = executor.submit(acquire_from_worktree)
                self.assertFalse(waiter_acquired.wait(timeout=0.2))
            finally:
                release_holder.set()
            self.assertTrue(waiter_acquired.wait(timeout=5))
            holder.result()
            waiter.result()

        lock_path = os.path.join(self.repo, ".git", "hammer-merge.lock")
        self.assertTrue(os.path.isfile(lock_path))

    def test_merge_lock_fallback_accepts_file_git_without_git(self):
        worktree = os.path.join(self.root, "linked-worktree-no-git")
        git(
            "worktree",
            "add",
            "-b",
            "712-task-no-git",
            worktree,
            cwd=self.repo,
        )
        self.assertTrue(os.path.isfile(os.path.join(worktree, ".git")))

        with (
            patch(
                "tasks_ai.utils.subprocess.check_output",
                side_effect=OSError("git unavailable"),
            ),
            merge_lock(worktree),
        ):
            pass

    def test_sigkill_releases_merge_lock(self):
        source = self.create_branch("702-task-kill", "kill.txt")
        script = (
            "import subprocess, sys, time\n"
            "from tasks_ai.utils import merge_lock\n"
            "with merge_lock(sys.argv[1]):\n"
            "    subprocess.run(['git', 'checkout', 'provisioning'], cwd=sys.argv[1], check=True)\n"
            "    print('locked', flush=True)\n"
            "    time.sleep(60)\n"
        )
        env = os.environ.copy()
        env["PYTHONPATH"] = PROJECT_ROOT + os.pathsep + env.get("PYTHONPATH", "")
        holder = subprocess.Popen(
            [sys.executable, "-c", script, self.repo],
            cwd=self.repo,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        self.assertEqual(holder.stdout.readline().strip(), "locked")
        os.kill(holder.pid, signal.SIGKILL)
        holder.wait(timeout=5)

        result = self.service.merge_branches(source, "provisioning")

        self.assertTrue(result["created_commit"])
        self.assertEqual(
            git(
                "rev-list", "--count", "--merges", "provisioning", cwd=self.repo
            ).stdout.strip(),
            "1",
        )


if __name__ == "__main__":
    unittest.main()
