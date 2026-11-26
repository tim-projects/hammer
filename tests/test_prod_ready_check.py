import os
import shutil
import subprocess
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace
from unittest.mock import patch

from tasks_ai.cli_errors import PipelinePushError
from tasks_ai.commands.move import move_logic
from tasks_ai.file_manager import FM
from tasks_ai.git_service import GitService
from tasks_ai.hooks import HookRegistry, PipelineHook
from tasks_ai.pipeline_hooks import ProdReadyCheckHook


def git(*args, cwd, check=True):
    result = subprocess.run(
        ["git", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
    )
    if check and result.returncode:
        raise AssertionError(f"git {' '.join(args)} failed: {result.stderr}")
    return result


class FakeCLI:
    def __init__(self, git_service, fail_checks=False, during_validation=None):
        self.dev = False
        self.git = git_service
        self.context = git_service.context
        self.fail_checks = fail_checks
        self.during_validation = during_validation
        self.validations = []
        self.next_steps = []

    def run_tool(self, tool_name=None, fix=False, cwd=None, script_path=None):
        self.validations.append(
            (
                tool_name,
                cwd,
                os.path.exists(cwd),
                script_path,
                os.path.exists(script_path) if script_path else False,
            )
        )
        if self.during_validation:
            self.during_validation()
        return subprocess.CompletedProcess(
            args=["check.py", tool_name or "all"],
            returncode=1 if self.fail_checks else 0,
            stdout="",
            stderr="injected failure" if self.fail_checks else "",
        )

    def next_step(self, code, **kwargs):
        self.next_steps.append((code, kwargs))
        raise RuntimeError(code)

    def error(self, code, **kwargs):
        raise RuntimeError(code)

    def log(self, message):
        pass


class ProdReadyCheckTest(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="prod_ready_check_")
        self.remote = os.path.join(self.root, "remote.git")
        self.seed = os.path.join(self.root, "seed")
        self.repo = os.path.join(self.root, "repo")
        os.makedirs(self.seed)
        git("init", "-b", "main", cwd=self.seed)
        git("config", "user.email", "test@example.com", cwd=self.seed)
        git("config", "user.name", "Test User", cwd=self.seed)
        with open(os.path.join(self.seed, "README.md"), "w", encoding="utf-8") as f:
            f.write("base\n")
        with open(os.path.join(self.seed, "check.py"), "w", encoding="utf-8") as f:
            f.write("print('ok')\n")
        git("add", "README.md", "check.py", cwd=self.seed)
        git("commit", "-m", "base", cwd=self.seed)
        git("init", "--bare", self.remote, cwd=self.seed)
        git("remote", "add", "origin", self.remote, cwd=self.seed)
        git("push", "-u", "origin", "main", cwd=self.seed)
        git("clone", self.remote, self.repo, cwd=self.root)
        git("config", "user.email", "test@example.com", cwd=self.repo)
        git("config", "user.name", "Test User", cwd=self.repo)
        context = SimpleNamespace(
            repo_root=self.repo,
            main_repo_root=self.repo,
            tasks_path=os.path.join(self.repo, ".tasks"),
            dev=False,
        )
        self.git = GitService(context)
        self.task = SimpleNamespace(metadata={"Id": 499}, parts={})

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def add_provisioning_change(self):
        git("checkout", "-b", "provisioning", cwd=self.repo)
        with open(os.path.join(self.repo, "feature.txt"), "w", encoding="utf-8") as f:
            f.write("feature\n")
        git("add", "feature.txt", cwd=self.repo)
        git("commit", "-m", "feature", cwd=self.repo)
        git("checkout", "main", cwd=self.repo)

    def temp_worktrees(self):
        result = git("worktree", "list", "--porcelain", cwd=self.repo)
        return {
            line.removeprefix("worktree ")
            for line in result.stdout.splitlines()
            if line.startswith("worktree ")
        }

    def test_red_check_leaves_main_and_worktrees_unchanged(self):
        self.add_provisioning_change()
        before = git("rev-parse", "main", cwd=self.repo).stdout.strip()
        cli = FakeCLI(self.git, fail_checks=True)

        with self.assertRaises(RuntimeError):
            ProdReadyCheckHook().execute(
                cli, self.task, "PROVISIONING", "DONE", "/tmp/task"
            )

        self.assertEqual(before, git("rev-parse", "main", cwd=self.repo).stdout.strip())
        self.assertEqual(
            before,
            git("rev-parse", "origin/main", cwd=self.repo).stdout.strip(),
        )
        self.assertEqual(1, len(cli.validations))
        self.assertTrue(cli.validations[0][2])
        self.assertTrue(cli.validations[0][4])
        self.assertFalse(
            any("hammer-prod-check-" in path for path in self.temp_worktrees())
        )

    def test_remote_main_change_during_check_fails_closed(self):
        self.add_provisioning_change()
        before = git("rev-parse", "main", cwd=self.repo).stdout.strip()
        other = os.path.join(self.root, "other")

        def advance_remote():
            git("clone", self.remote, other, cwd=self.root)
            git("config", "user.email", "other@example.com", cwd=other)
            git("config", "user.name", "Other User", cwd=other)
            with open(
                os.path.join(other, "concurrent.txt"), "w", encoding="utf-8"
            ) as f:
                f.write("concurrent\n")
            git("add", "concurrent.txt", cwd=other)
            git("commit", "-m", "concurrent main", cwd=other)
            git("push", "origin", "main", cwd=other)

        cli = FakeCLI(self.git, during_validation=advance_remote)

        with self.assertRaises(RuntimeError):
            ProdReadyCheckHook().execute(
                cli, self.task, "PROVISIONING", "DONE", "/tmp/task"
            )

        self.assertEqual(before, git("rev-parse", "main", cwd=self.repo).stdout.strip())
        self.assertNotEqual(
            before,
            git("rev-parse", "origin/main", cwd=self.repo).stdout.strip(),
        )
        self.assertFalse(
            any("hammer-prod-check-" in path for path in self.temp_worktrees())
        )

    def test_green_check_advances_main_by_one_merge_and_pushes(self):
        self.add_provisioning_change()
        before = git("rev-parse", "main", cwd=self.repo).stdout.strip()
        cli = FakeCLI(self.git)

        ProdReadyCheckHook().execute(
            cli, self.task, "PROVISIONING", "DONE", "/tmp/task"
        )

        after = git("rev-parse", "main", cwd=self.repo).stdout.strip()
        self.assertNotEqual(before, after)
        self.assertEqual(
            "1",
            git(
                "rev-list",
                "--first-parent",
                "--count",
                f"{before}..{after}",
                cwd=self.repo,
            ).stdout.strip(),
        )
        self.assertEqual(
            "1",
            git(
                "rev-list",
                "--count",
                "--merges",
                f"{before}..{after}",
                cwd=self.repo,
            ).stdout.strip(),
        )
        parents = (
            git("rev-list", "--parents", "-n", "1", after, cwd=self.repo)
            .stdout.strip()
            .split()
        )
        self.assertEqual(3, len(parents))
        self.assertEqual(
            after, git("rev-parse", "origin/main", cwd=self.repo).stdout.strip()
        )
        self.assertFalse(
            any("hammer-prod-check-" in path for path in self.temp_worktrees())
        )

    def test_concurrent_merge_completes_while_production_check_runs(self):
        self.add_provisioning_change()
        git("branch", "testing", "main", cwd=self.repo)
        completed = []

        def merge_during_check():
            with ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(
                    self.git.merge_branches, "provisioning", "testing"
                )
                completed.append(future.result(timeout=5))

        cli = FakeCLI(self.git, during_validation=merge_during_check)

        ProdReadyCheckHook().execute(
            cli, self.task, "PROVISIONING", "DONE", "/tmp/task"
        )

        self.assertEqual(1, len(completed))
        self.assertTrue(completed[0]["created_commit"])
        self.assertEqual(
            "1",
            git(
                "rev-list",
                "--count",
                "--merges",
                "testing",
                cwd=self.repo,
            ).stdout.strip(),
        )

    def test_rejected_push_rolls_back_and_retry_merges_cleanly(self):
        self.add_provisioning_change()
        hook = os.path.join(self.remote, "hooks", "pre-receive")
        with open(hook, "w", encoding="utf-8") as f:
            f.write(
                "#!/bin/sh\n"
                'marker="$(dirname "$0")/../reject-first-push"\n'
                'if [ ! -e "$marker" ]; then touch "$marker"; exit 1; fi\n'
                "exit 0\n"
            )
        os.chmod(hook, 0o755)

        remote_head = git("rev-parse", "origin/main", cwd=self.repo).stdout.strip()
        source = git("rev-parse", "provisioning", cwd=self.repo).stdout.strip()

        with self.assertRaises(PipelinePushError):
            self.git.merge_branches(
                "provisioning",
                "main",
                message="[499] merge: provisioning into main",
                yes=True,
                pull=False,
                expected_source=source,
                expected_target=remote_head,
            )

        self.assertEqual(
            remote_head, git("rev-parse", "main", cwd=self.repo).stdout.strip()
        )
        self.assertEqual(
            remote_head,
            git("rev-parse", "origin/main", cwd=self.repo).stdout.strip(),
        )

        result = self.git.merge_branches(
            "provisioning",
            "main",
            message="[499] merge: provisioning into main",
            yes=True,
            pull=False,
            expected_source=source,
            expected_target=remote_head,
        )

        self.assertTrue(result["created_commit"])
        self.assertEqual(
            git("rev-parse", "main", cwd=self.repo).stdout.strip(),
            git("rev-parse", "origin/main", cwd=self.repo).stdout.strip(),
        )

    def test_rejected_push_uses_pre_merge_sha_when_fetch_fails(self):
        self.add_provisioning_change()
        before = git("rev-parse", "main", cwd=self.repo).stdout.strip()
        source = git("rev-parse", "provisioning", cwd=self.repo).stdout.strip()
        original_run = self.git.run

        def run(args, **kwargs):
            if args[:2] == ["push", "origin"]:
                return subprocess.CompletedProcess(
                    args=["git", *args], returncode=1, stdout="", stderr="rejected"
                )
            if args[:2] == ["fetch", "origin"]:
                return subprocess.CompletedProcess(
                    args=["git", *args], returncode=1, stdout="", stderr="unavailable"
                )
            return original_run(args, **kwargs)

        with (
            patch.object(self.git, "run", side_effect=run),
            self.assertRaises(PipelinePushError),
        ):
            self.git.merge_branches(
                "provisioning",
                "main",
                message="[499] merge: provisioning into main",
                yes=True,
                pull=False,
                expected_source=source,
                expected_target=before,
            )

        self.assertEqual(before, git("rev-parse", "main", cwd=self.repo).stdout.strip())

    def test_missing_provisioning_is_bootstrapped_from_origin_main(self):
        base = git("rev-parse", "origin/main", cwd=self.repo).stdout.strip()
        cli = FakeCLI(self.git)

        ProdReadyCheckHook().execute(
            cli, self.task, "PROVISIONING", "DONE", "/tmp/task"
        )

        self.assertTrue(self.git.branch_exists("provisioning", self.repo))
        self.assertEqual(
            base,
            git("rev-parse", "provisioning", cwd=self.repo).stdout.strip(),
        )
        self.assertFalse(
            any("hammer-prod-check-" in path for path in self.temp_worktrees())
        )


class FailingEnterHook(PipelineHook):
    def execute(self, cli, task, current_state, new_status, filepath):
        raise SystemExit(1)


class FakeMoveCLI:
    def __init__(self, tasks_path, task_path):
        self.tasks_path = tasks_path
        self.task_path = task_path
        self.pipeline = SimpleNamespace(
            get_allowed_transitions=lambda _task_type: {"PROVISIONING": ["DONE"]},
            validate_gate=lambda *args: True,
            git_merge_transition=lambda *args, **kwargs: None,
        )
        self.git = SimpleNamespace(get_default_branch=lambda: "main")
        self.hook_registry = HookRegistry()
        self.hook_registry.register_enter_hook("DONE", FailingEnterHook())
        self._last_move_force = False

    def find_task(self, filename):
        return self.task_path, "PROVISIONING"

    def log(self, message):
        pass

    def _validate_pipeline_gate(self, task, new_status, task_path=None):
        return True

    def _git_merge_transition(self, task, new_status, yes=False, force=False):
        return None

    def _atomic_write(self, path, task):
        FM.dump(task, path)


class AtomicDoneTransitionTest(unittest.TestCase):
    def test_expected_hook_exit_leaves_task_in_provisioning(self):
        root = tempfile.mkdtemp(prefix="prod_ready_state_")
        self.addCleanup(shutil.rmtree, root, True)
        task_path = os.path.join(root, "provisioning", "499-task-example")
        os.makedirs(task_path)
        task = SimpleNamespace(metadata={"Id": 499, "St": "PROVISIONING"}, parts={})
        FM.dump(task, task_path)
        cli = FakeMoveCLI(root, task_path)

        with self.assertRaises(SystemExit):
            move_logic(cli, "499-task-example", "DONE")

        self.assertTrue(os.path.isdir(task_path))
        self.assertEqual("PROVISIONING", FM.load(task_path).metadata.get("St"))
        self.assertFalse(
            os.path.exists(os.path.join(root, ".ops", "staging", "499-task-example"))
        )


if __name__ == "__main__":
    unittest.main()
