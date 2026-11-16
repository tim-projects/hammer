"""User tests for task 348: task names are derived once, and everyone says so.

These drive the hammer CLI the way a user (or an agent) does, in the --dev
fixture repo: create a task with a long title and check that the branch, the task
folder and the worktree directory are one and the same name, that `tasks current`
reports where the worktree is, and that `tasks doctor` flags a worktree that is
registered at a path which is not <worktrees_base>/<branch>.
"""

import hashlib
import json
import os
import subprocess

from tests.hammer_test_base import HammerTestBase, ensure_dev_repo

STORY = "Sufficiently long story content here to pass validation"
TECH = "Sufficiently long technical description here to pass validation"
CRITERIA = "Sufficiently long acceptance criteria here to pass validation"
PLAN = "Sufficiently long planning details here to pass validation"
LONG_TITLE = "Pipeline should auto-push branches instead of demanding manual push"
BASE_ID = 9100


class NamingTestBase(HammerTestBase):
    def setUp(self):
        super().setUp()
        fixture_hammer = os.path.join(self.repo_path, "hammer")
        if os.path.lexists(fixture_hammer):
            os.remove(fixture_hammer)
        os.symlink(os.path.join(os.getcwd(), "hammer"), fixture_hammer)

    @property
    def dev_repo_dir(self):
        return ensure_dev_repo(self.dev_tasks_dir)

    def git(self, args, cwd=None):
        return subprocess.run(
            ["git"] + args,
            cwd=cwd or self.repo_path,
            capture_output=True,
            text=True,
            check=False,
        )

    def seed_counter(self, value):
        with open(os.path.join(self.dev_tasks_dir, ".task_counter"), "w") as handle:
            handle.write(str(value))
        digest = hashlib.md5(str(value).encode()).hexdigest()
        with open(
            os.path.join(self.dev_tasks_dir, ".task_counter.hash"), "w"
        ) as handle:
            handle.write(digest)

    def create_task(self, title=LONG_TITLE, counter=BASE_ID):
        self.seed_counter(counter - 1)
        result = self.run_tasks(
            [
                "create",
                title,
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
        self.assertEqual(result.returncode, 0, f"create failed: {result.stdout}")
        return json.loads(result.stdout)


class TestDerivedNamesMatchEverywhere(NamingTestBase):
    """Branch, task folder, worktree directory and printed path are one name."""

    def mount_task(self, payload):
        result = self.run_tasks(["mount", str(payload["id"])])
        self.assertEqual(result.returncode, 0, result.stdout)
        return json.loads(result.stdout)["data"]["worktree_path"]

    def test_branch_folder_and_worktree_share_one_name(self):
        payload = self.create_task()["data"]
        name = payload["file"]
        worktree = self.mount_task(payload)

        # the folder hammer created in the store
        self.assertTrue(
            os.path.isdir(os.path.join(self.dev_tasks_dir, "backlog", name))
        )
        # the branch in the throwaway repo
        branches = self.git(["branch", "--list"], cwd=self.dev_repo_dir).stdout
        self.assertIn(name, branches)
        # the worktree directory, which must be that same branch name
        expected_wt = os.path.join(self.dev_repo_dir, ".task-worktrees", name)
        self.assertTrue(os.path.isdir(expected_wt))
        self.assertIn(
            expected_wt,
            self.git(["worktree", "list"], cwd=self.dev_repo_dir).stdout,
        )
        self.assertEqual(payload["branch"], name)
        self.assertEqual(worktree, expected_wt)

    def test_a_long_title_is_cut_the_same_way_everywhere(self):
        payload = self.create_task()["data"]
        name = payload["file"]
        # 30-char slug cap: the last words of the title are gone everywhere,
        # so no consumer ever sees two spellings.
        self.assertTrue(name.startswith(f"{BASE_ID}-task-"))
        self.assertLessEqual(len(name.split("-", 2)[2]), 30)
        self.assertEqual(name, payload["branch"])

    def test_create_prints_the_planned_branch(self):
        text_out = subprocess.run(
            [
                os.path.join(self.repo_path, "hammer"),
                "tasks",
                "--dev",
                "create",
                LONG_TITLE + " probe printed path",
                "--story",
                STORY,
                "--tech",
                TECH,
                "--criteria",
                CRITERIA,
                "--plan",
                PLAN,
            ],
            cwd=self.repo_path,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(text_out.returncode, 0, text_out.stderr)
        text = text_out.stdout + text_out.stderr
        planned = [
            line.split("Planned branch:", 1)[1].strip()
            for line in text.splitlines()
            if "Planned branch:" in line
        ]
        self.assertGreaterEqual(len(planned), 1)
        self.assertNotIn("Worktree path:", text)
        self.assertNotIn("Worktree branch:", text)
        self.assertIn("will be created", text)


class TestCurrentReportsTheWorktree(NamingTestBase):
    def test_current_shows_the_worktree_path_in_json_and_text(self):
        payload = self.create_task()["data"]
        task_id = payload["id"]
        mount = self.run_tasks(["mount", str(task_id)])
        self.assertEqual(mount.returncode, 0, mount.stdout)
        worktree = json.loads(mount.stdout)["data"]["worktree_path"]

        json_out = self.run_tasks(["current", str(task_id)])
        self.assertEqual(json_out.returncode, 0, json_out.stdout)
        data = json.loads(json_out.stdout)["data"]
        self.assertEqual(data["worktree_path"], worktree)

        text_out = subprocess.run(
            [
                os.path.join(self.repo_path, "hammer"),
                "tasks",
                "--dev",
                "current",
                str(task_id),
            ],
            cwd=self.repo_path,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertIn(worktree, text_out.stdout + text_out.stderr)


class TestDoctorFlagsWorktreePathDrift(NamingTestBase):
    """A worktree registered anywhere but <base>/<branch> is a finding."""

    def test_doctor_reports_a_worktree_registered_at_the_wrong_path(self):
        payload = self.create_task()["data"]
        name = payload["file"]
        task_id = payload["id"]
        mount = self.run_tasks(["mount", str(task_id)])
        self.assertEqual(mount.returncode, 0, mount.stdout)
        worktree = json.loads(mount.stdout)["data"]["worktree_path"]

        # Move the registered worktree to a path that is not the branch name,
        # the exact drift that used to go unnoticed.
        drifted = os.path.join(self.dev_repo_dir, ".task-worktrees", name + "-drifted")
        os.rename(worktree, drifted)
        manifest = os.path.join(self.dev_tasks_dir, "worktrees.json")
        with open(manifest) as handle:
            data = json.load(handle)
        data["worktrees"][str(task_id)]["path"] = drifted
        with open(manifest, "w") as handle:
            json.dump(data, handle)

        result = self.run_tasks(["doctor"])
        self.assertEqual(result.returncode, 0, result.stdout)
        text = result.stdout + result.stderr
        self.assertIn("worktree path", text)
        self.assertIn(drifted, text)
