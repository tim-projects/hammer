"""The REVIEW gate must push the task branch itself, not offload it to the user.

WorktreeCheckHook used to halt REVIEW/STAGING/DONE/ARCHIVED with
BRANCH_NOT_PUSHED whenever the task branch had no remote ref, leaving the user
to run `git push origin <branch>` by hand. Hammer now pushes the branch; a push
that fails (or a remote that still has no ref) must still halt the transition.
"""

import unittest

from tasks_ai.pipeline_hooks import WorktreeCheckHook

BRANCH = "344-task-pipeline-should-auto-push-branch"


class FakeResult:
    def __init__(self, returncode=0, stdout="", stderr=""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


class FakeWorktrees:
    def get_worktree_path(self, task_id):
        return None


class FakeGit:
    def __init__(self):
        self.worktrees = FakeWorktrees()


class FakeCLI:
    """The slice of the CLI the hook touches: git calls, console, errors."""

    def __init__(self, remote_refs=(), push_fails=False):
        self.dev = False
        self.remote_refs = set(remote_refs)
        self.push_fails = push_fails
        self.commands = []
        self.errors = []
        self.git = FakeGit()

    def _run_git(self, cmd, cwd=None, check=False):
        self.commands.append(list(cmd))
        if cmd[:2] == ["ls-remote", "--heads"]:
            branch = cmd[-1]
            present = branch in self.remote_refs
            return FakeResult(stdout=f"sha\trefs/heads/{branch}\n" if present else "")
        if cmd[0] == "push":
            if self.push_fails:
                return FakeResult(returncode=1, stderr="rejected")
            self.remote_refs.add(cmd[-1])
            return FakeResult()
        return FakeResult()

    def console(self, type_tag, action, result):
        pass

    def error(self, code, **kwargs):
        self.errors.append(code)
        raise SystemExit(1)


class FakeTask:
    def __init__(self):
        self.metadata = {"Id": 344, "Br": BRANCH}


class TestWorktreeCheckHook(unittest.TestCase):
    def _enter(self, new_status, **cli_kwargs):
        cli = FakeCLI(**cli_kwargs)
        WorktreeCheckHook().execute(cli, FakeTask(), "TESTING", new_status, "/tmp/x")
        return cli

    def _pushes(self, cli):
        return [c for c in cli.commands if c[0] == "push"]

    def test_review_pushes_branch_when_remote_ref_missing(self):
        cli = self._enter("REVIEW")
        self.assertEqual([], cli.errors)
        self.assertEqual([["push", "-u", "origin", BRANCH]], self._pushes(cli))
        self.assertIn(BRANCH, cli.remote_refs)

    def test_review_does_not_push_when_branch_already_remote(self):
        cli = self._enter("REVIEW", remote_refs=[BRANCH])
        self.assertEqual([], self._pushes(cli))

    def test_failed_push_still_halts_the_transition(self):
        with self.assertRaises(SystemExit):
            self._enter("REVIEW", push_fails=True)

    def test_dev_mode_never_touches_the_remote(self):
        cli = FakeCLI()
        cli.dev = True
        WorktreeCheckHook().execute(cli, FakeTask(), "TESTING", "REVIEW", "/tmp/x")
        self.assertEqual([], cli.commands)
