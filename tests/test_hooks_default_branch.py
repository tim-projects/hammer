"""User tests for task 352: installed git hooks and the repo wrapper must
resolve the repo's actual default branch instead of hardcoding 'main'.

Hook scripts are generated text, so each case installs hooks into a temp repo
and drives real git operations through them.
"""
import importlib.util
import os
import shutil
import subprocess
import tempfile
import unittest


def git(args, cwd, check=False):
    return subprocess.run(
        ["git"] + args, cwd=cwd, capture_output=True, text=True, check=check
    )


def _make_test_root():
    """Repos outside /tmp (validate_path short-circuits under /tmp)."""
    try:
        return tempfile.mkdtemp(prefix="hooks_default_branch_", dir="/var/tmp")
    except OSError as exc:
        raise unittest.SkipTest(f"no writable non-/tmp temp dir (/var/tmp): {exc}")


class HookRepoTestCase(unittest.TestCase):
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
            f.write("# Hook test repo")
        git(["add", "README.md"], self.repo_dir)
        git(["commit", "-m", "Initial commit"], self.repo_dir)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def install_hooks(self, cwd=None):
        """Generate the hooks into cwd's repo via hammer's own installer."""
        from tasks_ai.cli import TasksCLI

        old_cwd = os.getcwd()
        os.chdir(cwd or self.repo_dir)
        try:
            TasksCLI(quiet=True).install_hooks()
        finally:
            os.chdir(old_cwd)

    def hook_body(self, name):
        with open(os.path.join(self.repo_dir, ".git", "hooks", name)) as f:
            return f.read()

    def commit_file(self, name="file.txt", branch=None):
        if branch:
            git(["checkout", branch], self.repo_dir)
        with open(os.path.join(self.repo_dir, name), "w") as f:
            f.write(f"content of {name}\n")
        git(["add", name], self.repo_dir)
        return git(["commit", "-m", f"Add {name}"], self.repo_dir)


class TestGeneratedHooksResolveDefaultBranch(HookRepoTestCase):
    def test_hooks_reference_resolved_branch_not_literal_main(self):
        self.install_hooks()
        for hook in ("pre-commit", "pre-merge-commit", "post-merge", "pre-receive"):
            body = self.hook_body(hook)
            self.assertIn(
                "default_branch=$(git symbolic-ref",
                body,
                f"{hook} does not resolve the default branch: {body[:200]}",
            )

    def test_pre_commit_compares_against_variable(self):
        self.install_hooks()
        body = self.hook_body("pre-commit")
        self.assertIn('"$target_branch" == "$default_branch"', body)
        self.assertNotIn('"$target_branch" == "main"', body)

    def test_hooks_use_real_git_hook_names(self):
        """'pre-merge' is not a git hook: git invokes pre-merge-commit."""
        self.install_hooks()
        hooks = os.listdir(os.path.join(self.repo_dir, ".git", "hooks"))
        self.assertIn("pre-merge-commit", hooks)
        self.assertNotIn("pre-merge", hooks)


class TestHookBehaviorOnMasterRepo(HookRepoTestCase):
    default_branch = "master"

    def test_commit_on_master_allowed(self):
        """The severe case: pre-commit must not reject the default branch."""
        self.install_hooks()
        res = self.commit_file()
        self.assertEqual(res.returncode, 0, f"commit on master rejected: {res.stderr}")

    def test_nonconformant_branch_still_blocked(self):
        self.install_hooks()
        git(["checkout", "-b", "not-a-conformant-branch"], self.repo_dir)
        res = self.commit_file()
        self.assertNotEqual(res.returncode, 0, "nonconformant branch was allowed")
        self.assertIn("does not conform", res.stderr)

    def test_direct_merge_into_master_blocked(self):
        self.install_hooks()
        git(["checkout", "-b", "42-task-topic-branch"], self.repo_dir)
        self.commit_file("topic.txt")
        git(["checkout", self.default_branch], self.repo_dir)
        # advance the default branch so the merge is a true merge: git only
        # invokes pre-merge-commit when a merge commit would be created
        self.commit_file("masterside.txt")
        res = git(["merge", "42-task-topic-branch"], self.repo_dir)
        self.assertNotEqual(res.returncode, 0, "direct merge into master was allowed")
        self.assertIn("Direct git merge into master detected", res.stderr)

    def test_hammer_internal_merge_into_master_allowed(self):
        """repo/pipeline merges into the default branch must not be blocked."""
        self.install_hooks()
        git(["checkout", "-b", "42-task-topic-branch"], self.repo_dir)
        self.commit_file("topic.txt")
        git(["checkout", self.default_branch], self.repo_dir)
        self.commit_file("masterside.txt")
        env = dict(os.environ, HAMMER_INTERNAL_CALL="1")
        res = subprocess.run(  # noqa: PLW1510
            ["git", "merge", "42-task-topic-branch"],
            cwd=self.repo_dir,
            capture_output=True,
            text=True,
            env=env,
        )
        self.assertEqual(res.returncode, 0, f"hammer merge blocked: {res.stderr}")

    def test_merge_out_of_default_branch_allowed(self):
        self.install_hooks()
        git(["checkout", "-b", "42-task-topic-branch"], self.repo_dir)
        git(["checkout", "-b", "43-task-other-branch"], self.repo_dir)
        self.commit_file("topic.txt")
        git(["checkout", "42-task-topic-branch"], self.repo_dir)
        res = git(["merge", "43-task-other-branch"], self.repo_dir)
        self.assertEqual(res.returncode, 0, f"merge between task branches failed: {res.stderr}")

    def test_post_merge_reports_sync_on_master(self):
        """post-merge must compare master (not a nonexistent main) to staging.

        A plain merge into the default branch is blocked by pre-merge-commit,
        so this drives it the way the pipeline does: hammer's own merge.
        """
        self.install_hooks()
        git(["branch", "staging"], self.repo_dir)
        git(["branch", "testing"], self.repo_dir)
        git(["checkout", "-b", "42-task-topic-branch"], self.repo_dir)
        self.commit_file("topic.txt")
        git(["checkout", self.default_branch], self.repo_dir)
        git(["checkout", "-b", "43-task-scratch-branch"], self.repo_dir)
        self.commit_file("scratch.txt")
        git(["checkout", self.default_branch], self.repo_dir)
        self.commit_file("masterside.txt")
        res = subprocess.run(  # noqa: PLW1510
            ["git", "merge", "--no-ff", "43-task-scratch-branch", "-m", "merge scratch"],
            cwd=self.repo_dir,
            capture_output=True,
            text=True,
            env=dict(os.environ, HAMMER_INTERNAL_CALL="1"),
        )
        self.assertEqual(res.returncode, 0, f"merge failed: {res.stderr}")
        # git routes hook output to stderr; the comparison must name master,
        # never a nonexistent main.
        self.assertNotIn("main", res.stderr, f"hook referenced main: {res.stderr}")
        self.assertIn("Pipeline branches are in sync", res.stderr)


class TestHookBehaviorOnMainRepo(HookRepoTestCase):
    """Regression: main-named repos must behave exactly as before."""

    default_branch = "main"

    def test_commit_on_main_allowed(self):
        self.install_hooks()
        res = self.commit_file()
        self.assertEqual(res.returncode, 0, f"commit on main rejected: {res.stderr}")

    def test_direct_merge_into_main_blocked(self):
        self.install_hooks()
        git(["checkout", "-b", "42-task-topic-branch"], self.repo_dir)
        self.commit_file("topic.txt")
        git(["checkout", "main"], self.repo_dir)
        self.commit_file("masterside.txt")
        res = git(["merge", "42-task-topic-branch"], self.repo_dir)
        self.assertNotEqual(res.returncode, 0, "direct merge into main was allowed")
        self.assertIn("Direct git merge into main detected", res.stderr)


class TestPreReceiveProtectsDefaultBranchDeletion(HookRepoTestCase):
    default_branch = "master"

    def _bare_remote_with_head_elsewhere(self):
        """Bare remote whose HEAD is not the default branch, so a delete of the
        default branch reaches the pre-receive hook instead of git's own
        denyDeleteCurrent refusal."""
        remote_dir = os.path.join(self.test_dir, "remote.git")
        git(["init", "--bare", remote_dir], self.repo_dir)
        git(["remote", "add", "origin", remote_dir], self.repo_dir)
        git(["push", "origin", self.default_branch], self.repo_dir)
        git(["checkout", "-b", "release"], self.repo_dir)
        self.commit_file("release.txt")
        git(["push", "origin", "release"], self.repo_dir)
        git(
            ["symbolic-ref", "HEAD", "refs/heads/release"],
            remote_dir,
        )
        return remote_dir

    def test_default_branch_deletion_blocked_on_remote(self):
        remote_dir = self._bare_remote_with_head_elsewhere()

        # pre-receive lives in the receiving (bare) repo
        self.install_hooks(cwd=remote_dir)

        res = git(["push", "origin", f":{self.default_branch}"], self.repo_dir)
        self.assertNotEqual(
            res.returncode, 0, f"deleting {self.default_branch} on the remote was allowed"
        )
        self.assertIn("Cannot delete critical pipeline branch", res.stderr)

    def test_feature_branch_deletion_allowed(self):
        remote_dir = self._bare_remote_with_head_elsewhere()
        git(["checkout", "-b", "42-task-topic-branch"], self.repo_dir)
        self.commit_file("topic.txt")
        git(["push", "origin", "42-task-topic-branch"], self.repo_dir)

        self.install_hooks(cwd=remote_dir)

        res = git(["push", "origin", ":42-task-topic-branch"], self.repo_dir)
        self.assertEqual(res.returncode, 0, f"feature branch delete failed: {res.stderr}")


class TestRepoWrapperPipeline(unittest.TestCase):
    """repo.py (the script 'hammer repo' runs) must resolve the pipeline's
    final branch from the default branch, not hardcode main."""

    def setUp(self):
        self.test_dir = _make_test_root()
        self.repo_dir = os.path.join(self.test_dir, "repo")
        os.makedirs(self.repo_dir)
        git(["init", "-b", "master"], self.repo_dir)
        git(["config", "user.email", "test@example.com"], self.repo_dir)
        git(["config", "user.name", "Test User"], self.repo_dir)
        with open(os.path.join(self.repo_dir, "README.md"), "w") as f:
            f.write("# repo wrapper test")
        git(["add", "README.md"], self.repo_dir)
        git(["commit", "-m", "Initial commit"], self.repo_dir)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def _load_repo_module(self):
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        spec = importlib.util.spec_from_file_location(
            "repo_under_test", os.path.join(project_root, "repo.py")
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_pipeline_ends_at_master(self):
        old_cwd = os.getcwd()
        os.chdir(self.repo_dir)
        try:
            repo = self._load_repo_module()
            self.assertEqual(repo.get_default_branch(), "master")
            self.assertEqual(repo.pipeline(), ["testing", "staging", "master"])
        finally:
            os.chdir(old_cwd)

    def test_pipeline_ends_at_main_when_main_exists(self):
        git(["branch", "main"], self.repo_dir)
        old_cwd = os.getcwd()
        os.chdir(self.repo_dir)
        try:
            repo = self._load_repo_module()
            self.assertEqual(repo.get_default_branch(), "main")
            self.assertEqual(repo.pipeline(), ["testing", "staging", "main"])
        finally:
            os.chdir(old_cwd)


if __name__ == "__main__":
    unittest.main()
