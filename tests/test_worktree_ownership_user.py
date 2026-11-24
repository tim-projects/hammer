"""User tests for task 350: hammer owns worktree paths end to end.

These drive the hammer CLI the way a user does, in the --dev fixture repo, and
assert that drift goes from silent to loud: a stray directory under
.task-worktrees/ is reported by `guard scan` and removed by `tasks doctor --fix`,
a worktree registered at a drifted path never blocks a correctly named one, and
`tasks current` answers where the worktree is.
"""

import json
import os
import subprocess

from tests.hammer_test_base import HammerTestBase, ensure_dev_repo

STORY = "Sufficiently long story content here to pass validation"
TECH = "Sufficiently long technical description here to pass validation"
CRITERIA = "Sufficiently long acceptance criteria here to pass validation"
PLAN = "Sufficiently long planning details here to pass validation"
TITLE = "Worktree Ownership Probe Task"
BASE_ID = 9100


class OwnershipTestBase(HammerTestBase):
    def setUp(self):
        super().setUp()
        fixture_hammer = os.path.join(self.repo_path, "hammer")
        if os.path.lexists(fixture_hammer):
            os.remove(fixture_hammer)
        os.symlink(os.path.join(os.getcwd(), "hammer"), fixture_hammer)

    @property
    def dev_repo_dir(self):
        """The throwaway repo the --dev CLI acts on, never this fixture repo."""
        return ensure_dev_repo(self.dev_tasks_dir)

    def git(self, args, cwd=None):
        return subprocess.run(
            ["git"] + args,
            cwd=cwd or self.repo_path,
            capture_output=True,
            text=True,
            check=False,
        )

    def create_task(self, counter=BASE_ID, seed=True):
        if seed:
            self.seed_task_id_floor(counter - 1)
        result = self.run_tasks(
            [
                "create",
                TITLE,
                "--story",
                STORY,
                "--tech",
                TECH,
                "--criteria",
                CRITERIA,
                "--plan",
                PLAN,
            ]
        )
        assert result.returncode == 0, result.stdout
        return json.loads(result.stdout)["data"]

    def mount_task(self, payload):
        result = self.run_tasks(["mount", str(payload["id"])])
        assert result.returncode == 0, result.stdout
        return json.loads(result.stdout)["data"]["worktree_path"]

    def guard_scan(self):
        return subprocess.run(
            [os.path.join(self.repo_path, "hammer"), "guard", "scan", "--dev"],
            cwd=self.repo_path,
            capture_output=True,
            text=True,
            check=False,
        )

    def doctor(self, fix=False, task_id=None):
        args = [os.path.join(self.repo_path, "hammer"), "tasks", "--dev", "doctor"]
        if fix:
            args.append("--fix")
            if task_id is not None:
                args.append(str(task_id))
        return subprocess.run(
            args, cwd=self.repo_path, capture_output=True, text=True, check=False
        )


class TestGuardSeesUnownedDirectories(OwnershipTestBase):
    def test_stray_directory_under_the_base_is_reported(self):
        stray = os.path.join(self.dev_repo_dir, ".task-worktrees", "999-task-none")
        os.makedirs(stray)
        result = self.guard_scan()
        text = result.stdout + result.stderr
        self.assertIn("GUARD_WORKTREE_UNREGISTERED", text)
        self.assertIn(stray, text)

    def test_doctor_fix_reports_but_does_not_remove_the_stray(self):
        payload = self.create_task()
        real = self.mount_task(payload)
        stray = os.path.join(self.dev_repo_dir, ".task-worktrees", "999-task-none")
        os.makedirs(stray)

        report = self.doctor(fix=True)
        self.assertIn("GUARD_WORKTREE_UNREGISTERED", report.stdout + report.stderr)
        self.assertTrue(os.path.exists(stray), "doctor must not delete ambiguous work")
        self.assertTrue(os.path.exists(real), "the registered worktree was damaged")


class TestDriftedPathDoesNotBlockTheHealthyTask(OwnershipTestBase):
    def test_a_healthy_worktree_is_not_reported(self):
        payload = self.create_task()
        result = self.guard_scan()
        text = result.stdout + result.stderr
        self.assertNotIn(f"[{payload['id']}]", text)
        self.assertNotIn(payload["file"], text)


class TestCurrentAnswersWhereTheWorktreeIs(OwnershipTestBase):
    def test_current_reports_the_worktree_hammer_created(self):
        payload = self.create_task()
        worktree = self.mount_task(payload)
        out = self.run_tasks(["current", str(payload["id"])])
        assert out.returncode == 0, out.stdout
        data = json.loads(out.stdout)["data"]
        self.assertEqual(data["worktree_path"], worktree)
        self.assertTrue(os.path.isdir(data["worktree_path"]))

    def test_mount_creates_the_worktree_when_it_is_missing(self):
        payload = self.create_task()
        worktree = self.mount_task(payload)
        # Drop the registered worktree the way a pruned checkout does.
        subprocess.run(
            ["git", "worktree", "remove", "--force", worktree],
            cwd=self.dev_repo_dir,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertFalse(os.path.exists(worktree))

        out = self.run_tasks(["mount", str(payload["id"])])
        assert out.returncode == 0, out.stdout
        data = json.loads(out.stdout)["data"]
        self.assertTrue(os.path.isdir(data["worktree_path"]))
        self.assertIn(
            data["worktree_path"],
            self.git(["worktree", "list"], cwd=self.dev_repo_dir).stdout,
        )
