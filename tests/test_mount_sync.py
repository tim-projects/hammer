"""Tests for canonical worktree synchronization shared by mount and pipeline entry."""

import os
import subprocess
import tempfile
import unittest

from tasks_ai.commands import mount as mount_cmd
from tasks_ai.git_service import GitService
from tasks_ai.pipeline_hooks import WorktreeSyncHook


def git(args, cwd, check=True):
    return subprocess.run(
        ["git"] + args, cwd=cwd, capture_output=True, text=True, check=check
    )


class FakeContext:
    def __init__(self, root):
        self.main_repo_root = root
        self.repo_root = root


def write(path, content):
    with open(path, "w") as handle:
        handle.write(content)


class GitServiceSyncTest(unittest.TestCase):
    """The git helpers prefer local main and detect conflicts without writes."""

    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="worktree_sync_")
        self.remote = os.path.join(self.root, "remote")
        os.makedirs(self.remote)
        git(["init", "--bare", "-b", "main", self.remote], self.remote)
        self.main = os.path.join(self.root, "main")
        git(["clone", self.remote, self.main], self.root)
        git(["config", "user.email", "test@example.com"], self.main)
        git(["config", "user.name", "Test User"], self.main)
        git(["config", "commit.gpgsign", "false"], self.main)
        write(os.path.join(self.main, "shared.txt"), "base\n")
        git(["add", "."], self.main)
        git(["commit", "-m", "base"], self.main)
        git(["push", "origin", "main"], self.main)
        self.git = GitService(FakeContext(self.main))

        self.branch = "459-task-worktree-sync-probe"
        git(["branch", self.branch], self.main)
        self.wt = os.path.join(self.root, "wt")
        git(["worktree", "add", self.wt, self.branch], self.main)

    def tearDown(self):
        git(["worktree", "remove", "--force", self.wt], self.main, check=False)
        subprocess.run(["rm", "-rf", self.root], check=False)

    def test_sync_worktree_uses_local_main_before_origin_main(self):
        write(os.path.join(self.main, "new.txt"), "from main\n")
        git(["add", "."], self.main)
        git(["commit", "-m", "local main moves on"], self.main)

        source = self.git.sync_worktree(self.wt, "main", self.branch)

        self.assertEqual("main", source)
        self.assertTrue(os.path.exists(os.path.join(self.wt, "new.txt")))

    def test_conflicting_files_reports_paths_and_touches_nothing(self):
        write(os.path.join(self.wt, "shared.txt"), "branch side\n")
        git(["add", "."], self.wt)
        git(["commit", "-m", "branch edit"], self.wt)
        write(os.path.join(self.main, "shared.txt"), "main side\n")
        git(["add", "."], self.main)
        git(["commit", "-m", "main edit"], self.main)
        before = git(["status", "--porcelain"], self.wt).stdout
        with open(os.path.join(self.wt, "shared.txt")) as handle:
            content_before = handle.read()

        conflicts = self.git.conflicting_files(self.wt, "main")

        self.assertEqual(["shared.txt"], conflicts)
        self.assertEqual(before, git(["status", "--porcelain"], self.wt).stdout)
        with open(os.path.join(self.wt, "shared.txt")) as handle:
            self.assertEqual(content_before, handle.read())


class FakeResult:
    def __init__(self, stdout=""):
        self.returncode = 0
        self.stdout = stdout
        self.stderr = ""


class FakeWorktrees:
    def __init__(self, path="/wt", exists=True):
        self.path = path
        self.exists = exists
        self.created = []

    def has_worktree(self, task_id):
        return self.exists

    def get_worktree_path(self, task_id):
        return self.path

    def create_task_worktree(self, task_id, branch=None, base_ref=None):
        self.created.append((task_id, branch, base_ref))
        self.exists = True
        return self.path


class FakeGit:
    def __init__(self, conflicts=None, local_paths=None, diverged=False):
        self.worktrees = FakeWorktrees()
        self.conflicts = conflicts or []
        self.local_paths = local_paths or []
        self.diverged = diverged
        self.merged = []

    def get_default_branch(self):
        return "main"

    def resolve_merge_source(self, default_branch):
        return default_branch

    def main_branch_divergence(self, default_branch):
        return ("local-sha", "remote-sha", self.diverged)

    def conflicting_files(self, worktree_path, merge_source):
        return self.conflicts

    def uncommitted_files(self, worktree_path):
        return self.local_paths

    def run(self, args, cwd=None, check=False):
        return FakeResult("local-sha\n")

    def sync_worktree(self, worktree_path, default_branch, branch, merge_source=None):
        self.merged.append((worktree_path, default_branch, branch, merge_source))
        return merge_source


class FakeCLI:
    def __init__(self, git):
        self.git = git
        self.dev = False
        self.context = FakeContext("/repo")
        self.lines = []
        self.action_required_calls = []

    def console(self, type_tag, action, result):
        self.lines.append((type_tag, action, result))

    def log(self, message):
        self.lines.append(("log", "", message))

    def error(self, code, **kwargs):
        raise AssertionError(f"unexpected error: {code}")

    def action_required(self, code, **kwargs):
        self.action_required_calls.append((code, kwargs))
        raise SystemExit(1)

    def finish(self, data=None):
        self.finished = data


class WorktreeSyncHookTest(unittest.TestCase):
    def test_clean_worktree_syncs_from_local_main(self):
        git = FakeGit()
        cli = FakeCLI(git)

        WorktreeSyncHook().synchronize(cli, "459", "459-task-sync", "/wt")

        self.assertEqual([("/wt", "main", "459-task-sync", "main")], git.merged)
        self.assertEqual([], cli.action_required_calls)

    def test_conflict_blocker_contains_actionable_details(self):
        git = FakeGit(conflicts=["shared.txt", "app.py"])
        cli = FakeCLI(git)

        with self.assertRaises(SystemExit):
            WorktreeSyncHook().synchronize(cli, "459", "459-task-sync", "/wt")

        code, details = cli.action_required_calls[0]
        self.assertEqual("WORKTREE_SYNC_CONFLICT", code)
        self.assertEqual("459", details["task_id"])
        self.assertEqual("459-task-sync", details["branch"])
        self.assertEqual("local-sha", details["local_commit"])
        self.assertEqual("shared.txt, app.py", details["paths"])
        self.assertEqual("/wt", details["worktree_path"])
        self.assertEqual([], git.merged)

    def test_uncommitted_work_is_blocked_without_merging(self):
        git = FakeGit(local_paths=["scratch.txt"])
        cli = FakeCLI(git)

        with self.assertRaises(SystemExit):
            WorktreeSyncHook().synchronize(cli, "459", "459-task-sync", "/wt")

        code, details = cli.action_required_calls[0]
        self.assertEqual("WORKTREE_LOCAL_WORK", code)
        self.assertEqual("scratch.txt", details["paths"])
        self.assertEqual([], git.merged)

    def test_main_divergence_is_an_actionable_blocker(self):
        git = FakeGit(diverged=True)
        cli = FakeCLI(git)

        with self.assertRaises(SystemExit):
            WorktreeSyncHook().synchronize(cli, "459", "459-task-sync", "/wt")

        code, details = cli.action_required_calls[0]
        self.assertEqual("WORKTREE_MAIN_DIVERGED", code)
        self.assertEqual("459", details["task_id"])
        self.assertEqual("459-task-sync", details["branch"])
        self.assertEqual([], git.merged)

    def test_dev_mode_uses_diverged_local_main(self):
        git = FakeGit(diverged=True)
        cli = FakeCLI(git)
        cli.dev = True

        WorktreeSyncHook().synchronize(cli, "459", "459-task-sync", "/wt")

        self.assertEqual([], cli.action_required_calls)
        self.assertEqual([("/wt", "main", "459-task-sync", "main")], git.merged)

    def test_pipeline_entry_uses_the_canonical_hook(self):
        git = FakeGit()
        cli = FakeCLI(git)
        task = type("Task", (), {"metadata": {"Id": 459, "Br": "459-task-sync"}})()

        WorktreeSyncHook().execute(cli, task, "READY", "PROGRESSING", "/task")

        self.assertEqual([("/wt", "main", "459-task-sync", "main")], git.merged)

    def test_missing_branch_and_worktree_are_created_from_local_main(self):
        git = FakeGit()
        git.worktrees.exists = False
        cli = FakeCLI(git)

        WorktreeSyncHook().ensure_worktree(cli, "459", "459-task-sync")

        self.assertEqual([("459", "459-task-sync", "main")], git.worktrees.created)

    def test_mount_delegates_to_the_canonical_hook(self):
        git = FakeGit()
        cli = FakeCLI(git)
        cli.find_task = lambda task_id: ("/fake/459-task", "PROGRESSING")
        task = type("Task", (), {"metadata": {"Id": 459, "Br": "459-task-sync"}})()
        original_fm = mount_cmd.FM
        mount_cmd.FM = type("FM", (), {"load": staticmethod(lambda path: task)})
        try:
            mount_cmd.run(cli, 459)
        finally:
            mount_cmd.FM = original_fm

        self.assertEqual([("/wt", "main", "459-task-sync", "main")], git.merged)
        self.assertEqual("/wt", cli.finished["worktree_path"])


if __name__ == "__main__":
    unittest.main()
