"""User tests for task 415: mount syncs a clean worktree, warns about conflicts.

Two layers:
1. tasks_ai.git_service helpers against a real git repo (fast-forward sync,
   conflict listing, local-work detection).
2. tasks_ai.commands.mount._sync_or_warn with a fake CLI, asserting a worktree
   with local work is never merged (no conflict markers in the user's files) and
   that the conflicting paths are reported.
"""

import os
import subprocess
import tempfile
import unittest

from tasks_ai.commands import mount as mount_cmd
from tasks_ai.git_service import GitService


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
    """Real repo: clean worktree fast-forwards, conflicts are only reported."""

    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="mount_sync_")
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

        self.branch = "415-task-mount-sync-probe"
        git(["branch", self.branch], self.main)
        self.wt = os.path.join(self.root, "wt")
        git(["worktree", "add", self.wt, self.branch], self.main)

    def tearDown(self):
        git(["worktree", "remove", "--force", self.wt], self.main, check=False)
        subprocess.run(["rm", "-rf", self.root], check=False)

    def test_sync_worktree_fast_forwards_clean_worktree(self):
        write(os.path.join(self.main, "new.txt"), "from main\n")
        git(["add", "."], self.main)
        git(["commit", "-m", "main moves on"], self.main)
        git(["push", "origin", "main"], self.main)

        source = self.git.sync_worktree(self.wt, "main", self.branch)

        self.assertEqual("origin/main", source)
        self.assertTrue(os.path.exists(os.path.join(self.wt, "new.txt")))
        self.assertEqual(
            git(["rev-parse", "main"], self.main).stdout.strip(),
            git(["rev-parse", "HEAD"], self.wt).stdout.strip(),
        )

    def test_has_local_work_is_false_for_untouched_worktree(self):
        self.assertFalse(self.git.has_local_work(self.wt, "origin/main"))

    def test_has_local_work_is_true_for_untracked_file(self):
        write(os.path.join(self.wt, "scratch.txt"), "wip\n")
        self.assertTrue(self.git.has_local_work(self.wt, "origin/main"))

    def test_has_local_work_is_true_for_commits_ahead(self):
        write(os.path.join(self.wt, "own.txt"), "mine\n")
        git(["add", "."], self.wt)
        git(["commit", "-m", "own work"], self.wt)
        self.assertTrue(self.git.has_local_work(self.wt, "origin/main"))

    def test_conflicting_files_reports_paths_and_touches_nothing(self):
        write(os.path.join(self.wt, "shared.txt"), "branch side\n")
        git(["add", "."], self.wt)
        git(["commit", "-m", "branch edit"], self.wt)
        git(["push", "origin", self.branch], self.wt)
        write(os.path.join(self.main, "shared.txt"), "main side\n")
        git(["add", "."], self.main)
        git(["commit", "-m", "main edit"], self.main)
        git(["push", "origin", "main"], self.main)
        before = git(["status", "--porcelain"], self.wt).stdout
        with open(os.path.join(self.wt, "shared.txt")) as handle:
            content_before = handle.read()

        conflicts = self.git.conflicting_files(self.wt, "origin/main")

        self.assertEqual(["shared.txt"], conflicts)
        # merge-tree must not write conflict markers or stage anything
        self.assertEqual(before, git(["status", "--porcelain"], self.wt).stdout)
        with open(os.path.join(self.wt, "shared.txt")) as handle:
            self.assertEqual(content_before, handle.read())

    def test_conflicting_files_empty_when_merge_would_apply(self):
        write(os.path.join(self.main, "new.txt"), "from main\n")
        git(["add", "."], self.main)
        git(["commit", "-m", "main moves on"], self.main)
        git(["push", "origin", "main"], self.main)

        self.assertEqual([], self.git.conflicting_files(self.wt, "origin/main"))

    def test_sync_worktree_aborts_on_conflict(self):
        write(os.path.join(self.wt, "shared.txt"), "branch side\n")
        git(["add", "."], self.wt)
        git(["commit", "-m", "branch edit"], self.wt)
        write(os.path.join(self.main, "shared.txt"), "main side\n")
        git(["add", "."], self.main)
        git(["commit", "-m", "main edit"], self.main)
        git(["push", "origin", "main"], self.main)

        try:
            self.git.sync_worktree(self.wt, "main", self.branch)
        except Exception as exc:  # noqa: BLE001
            # Other test files import tasks_ai twice in one pytest process, so
            # the exception class identity is not reliable: match the message.
            self.assertIn("Merge conflict", str(exc))
        else:
            self.fail("expected a merge-conflict error from a conflicted sync")

        status = git(["status", "--porcelain"], self.wt, check=False).stdout
        self.assertEqual("", status)
        with open(os.path.join(self.wt, "shared.txt")) as handle:
            self.assertNotIn("conflict", handle.read())


class FakeGit:
    def __init__(self, local_work, conflicts, default_branch="main"):
        self.local_work = local_work
        self.conflicts = conflicts
        self.default_branch = default_branch
        self.merged = []
        self.checks = []

    def get_default_branch(self):
        return self.default_branch

    def resolve_merge_source(self, default_branch):
        return f"origin/{default_branch}"

    def has_local_work(self, wt_path, merge_source):
        self.checks.append((wt_path, merge_source))
        return self.local_work

    def conflicting_files(self, wt_path, merge_source):
        self.checks.append((wt_path, merge_source))
        return self.conflicts

    def sync_worktree(self, wt_path, default_branch, branch):
        self.merged.append((wt_path, default_branch, branch))
        return f"origin/{default_branch}"


class FakeCLI:
    def __init__(self, git):
        self.git = git
        self.lines = []
        self.errors = []

    def console(self, type_tag, action, result):
        self.lines.append((type_tag, action, result))

    def log(self, message):
        self.lines.append(("log", "", message))

    def error(self, code, **kwargs):
        self.errors.append(code)
        raise SystemExit(1)


class MountWarnTest(unittest.TestCase):
    """mount decides between syncing and warning; it never merges local work."""

    def _mount(self, local_work, conflicts, default_branch="main"):
        git = FakeGit(local_work, conflicts, default_branch)
        cli = FakeCLI(git)
        mount_cmd._sync_or_warn(cli, "/wt", "415-branch")
        return cli, git

    def test_clean_worktree_is_synced(self):
        cli, git = self._mount(local_work=False, conflicts=[])
        self.assertEqual([("/wt", "main", "415-branch")], git.merged)
        self.assertEqual([], cli.errors)
        self.assertIn(("worktree", "sync", "origin/main -> complete"), cli.lines)

    def test_local_work_is_never_merged_and_conflicts_are_named(self):
        cli, git = self._mount(local_work=True, conflicts=["shared.txt", "app.py"])
        self.assertEqual([], git.merged)
        self.assertIn(
            ("worktree", "conflicts", "2 file(s) conflict with origin/main:"), cli.lines
        )
        self.assertIn(("conflict", "file", "shared.txt"), cli.lines)
        self.assertIn(("conflict", "file", "app.py"), cli.lines)

    def test_local_work_without_conflicts_reports_up_to_date(self):
        cli, git = self._mount(local_work=True, conflicts=[])
        self.assertEqual([], git.merged)
        self.assertIn(("worktree", "sync", "up to date with origin/main"), cli.lines)

    def test_no_default_branch_skips_the_whole_step(self):
        cli, git = self._mount(local_work=False, conflicts=[], default_branch=None)
        self.assertEqual([], git.merged)
        self.assertEqual([], git.checks)
        self.assertIn(("worktree", "sync", "skipped (no default branch)"), cli.lines)

    def test_no_mergeable_ref_skips_the_whole_step(self):
        git = FakeGit(local_work=False, conflicts=[])
        git.resolve_merge_source = lambda db: None
        cli = FakeCLI(git)
        mount_cmd._sync_or_warn(cli, "/wt", "415-branch")
        self.assertEqual([], git.merged)
        self.assertIn(("worktree", "sync", "skipped (no main/master ref)"), cli.lines)
