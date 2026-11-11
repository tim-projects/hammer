"""User tests for dev-mode isolation (task 338).

`--dev` used to swap only the STORE. The repo it acts on stayed the repo it was
invoked from, so a dev create left real branches and worktrees behind; a dev
branch at a colliding id then made the guard reject the REAL promotion. These
tests pin both halves: a dev cycle writes nothing into the invoked repo, and a
dev create cannot block a real task.
"""

import hashlib
import json
import os
import shutil
import subprocess
import unittest

from tests.hammer_test_base import HammerTestBase, dev_repo_path, ensure_dev_repo

STORY = "Sufficiently long story content here to pass validation"
TECH = "Sufficiently long technical description here to pass validation"
CRITERIA = "Sufficiently long acceptance criteria here to pass validation"
PLAN = "Sufficiently long planning details here to pass validation"
TITLE = "Dev Isolation Probe Task"

# Above the real repo's highest task id, so the fixture's inherited branches
# never collide with the ids these tests create.
BASE_ID = 9100


class DevIsolationTestBase(HammerTestBase):
    def setUp(self):
        super().setUp()
        # The fixture is a clone of the committed tree; point its entry point at
        # this working copy so the --dev CLI under test is the edited one.
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

    def repo_state(self):
        return (
            self.git(["branch", "--list"]).stdout,
            self.git(["worktree", "list", "--porcelain"]).stdout,
        )

    def reseal_counter_hash(self, value):
        """Keep the counter hash consistent with the seeded counter.

        Without this the counter protector takes its recovery path, which
        raises the id past any existing branch -- the opposite of the
        colliding id this suite needs.
        """
        counter = os.path.join(self.dev_tasks_dir, ".task_counter")
        with open(counter, "w") as handle:
            handle.write(str(value))
        digest = hashlib.md5(str(value).encode()).hexdigest()
        with open(
            os.path.join(self.dev_tasks_dir, ".task_counter.hash"), "w"
        ) as handle:
            handle.write(digest)

    def create_dev_task(self, counter_value=None, title=TITLE):
        if counter_value is not None:
            self.seed_counter(counter_value)
            self.reseal_counter_hash(counter_value)
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
        payload = json.loads(result.stdout)
        return payload["data"]["id"], payload["data"]["file"]


class TestDevLeavesTheInvokedRepoAlone(DevIsolationTestBase):
    """A full dev create/mount/checkpoint cycle must not write a single ref."""

    def test_dev_cycle_leaves_branches_and_worktrees_identical(self):
        task_id, _ = self.create_dev_task(counter_value=BASE_ID - 1)
        before = self.repo_state()

        self.run_tasks(["mount", str(task_id)])
        self.run_tasks(["checkpoint", str(task_id)])

        after = self.repo_state()
        self.assertEqual(
            after,
            before,
            "a --dev create/mount/checkpoint cycle mutated the invoked repo",
        )

    def test_dev_task_lives_in_the_throwaway_repo(self):
        _, task_file = self.create_dev_task(counter_value=BASE_ID - 1)
        self.assertTrue(
            os.path.isdir(
                os.path.join(self.dev_repo_dir, ".task-worktrees", task_file)
            ),
            f"no dev worktree for {task_file} in {self.dev_repo_dir}",
        )
        # the dev branch exists only there
        branches = self.git(["branch", "--list"], cwd=self.dev_repo_dir).stdout
        self.assertIn(task_file, branches)
        self.assertNotIn(task_file, self.git(["branch", "--list"]).stdout)

    def test_dev_repo_is_reused_across_invocations(self):
        self.create_dev_task(counter_value=BASE_ID - 1)
        first = os.path.getmtime(os.path.join(self.dev_repo_dir, ".git", "HEAD"))
        self.run_tasks(["list"])
        second = os.path.getmtime(os.path.join(self.dev_repo_dir, ".git", "HEAD"))
        self.assertLessEqual(
            second,
            first,
            "the dev repo must be keyed on the store, not rebuilt per command",
        )


class TestDevCannotBlockARealTask(DevIsolationTestBase):
    """Dev-created state must not reach the verdict of a real task."""

    def test_dev_create_at_a_real_id_leaves_the_real_verdict_clean(self):
        # A real task id, with its branch in the repo the user works in.
        real_branch = f"{BASE_ID}-task-real-task"
        self.git(["branch", real_branch])
        # Re-seed the dev repo so it mirrors the branch just created.
        shutil.rmtree(self.dev_repo_dir, ignore_errors=True)

        task_id, _ = self.create_dev_task(counter_value=BASE_ID - 1)
        self.assertEqual(task_id, BASE_ID)

        # The dev promotion of the colliding task is rejected: the dev repo
        # holds both branches for that id, exactly as the real repo would.
        blocked = self.run_tasks(["move", str(task_id), "READY"])
        self.assertEqual(blocked.returncode, 1, blocked.stdout)
        self.assertIn("GUARD", json.loads(blocked.stdout)["error"])

        # ...and the real task is still promotable: guard reads the real repo.
        self._write_real_task(real_branch)
        promoted = self.run_real_tasks(["move", str(BASE_ID), "READY"])
        self.assertEqual(
            promoted.returncode,
            0,
            f"the real promotion was blocked by dev-created state: {promoted.stdout}",
        )
        self.assertTrue(
            os.path.isdir(os.path.join(self.repo_path, ".tasks", "ready", real_branch)),
            "the real task never left backlog",
        )

    def _write_real_task(self, branch):
        """Seed a task in the REAL store (the one a real promotion moves)."""
        from tasks_ai.constants import TASKS_DIR
        from tasks_ai.file_manager import FM
        from tasks_ai.models import Task

        # The fixture's .gitignore hides the store by convention, so a real
        # promotion could never commit to it: drop that one line.
        gitignore = os.path.join(self.repo_path, ".gitignore")
        if os.path.exists(gitignore):
            with open(gitignore) as handle:
                kept = [
                    line
                    for line in handle.read().splitlines()
                    if line.strip().lstrip("/") not in (".tasks", ".tasks/")
                ]
            with open(gitignore, "w") as handle:
                handle.write("\n".join(kept) + "\n")

        task_dir = os.path.join(self.repo_path, TASKS_DIR, "backlog", branch)
        os.makedirs(task_dir, exist_ok=True)
        FM.dump(
            Task(
                metadata={
                    "Id": BASE_ID,
                    "Ti": "Real Promotion Task",
                    "Ty": "task",
                    "Br": branch,
                    "Pr": 2,
                    "Bl": [],
                },
                parts={
                    "story": STORY,
                    "tech": TECH,
                    "criteria": CRITERIA,
                    "plan": PLAN,
                },
            ),
            task_dir,
        )

    def run_real_tasks(self, args):
        """Run the CLI without --dev, in the repo the test was invoked from."""
        env = {k: v for k, v in os.environ.items() if k != "HAMMER_DEV_TASKS_DIR"}
        return subprocess.run(
            [self.script_path, "tasks", "-j"] + args,
            cwd=self.repo_path,
            capture_output=True,
            text=True,
            check=False,
            env=env,
        )


class TestDevRefusesWhatItCannotIsolate(DevIsolationTestBase):
    """When dev mode cannot be isolated it stops: it never falls back."""

    def test_unusable_dev_repo_path_refuses_with_a_clear_error(self):
        store = os.path.join(self.test_root, "dev-store")
        # The dev repo path is already taken by something that is not a repo.
        with open(dev_repo_path(store), "w") as handle:
            handle.write("not a repo\n")

        result = subprocess.run(
            [self.script_path, "tasks", "-j", "--dev", "list"],
            cwd=self.repo_path,
            capture_output=True,
            text=True,
            check=False,
            env={**os.environ, "HAMMER_DEV_TASKS_DIR": store},
        )
        self.assertNotEqual(result.returncode, 0, result.stdout)
        payload = json.loads(result.stdout)
        self.assertIn("Dev mode cannot be isolated", payload["error"])
        self.assertIn("list", payload["hint"])
        self.assertIn("WITHOUT --dev", payload["hint"])

    def test_save_is_refused_in_dev_mode(self):
        result = self.run_tasks(["save"])
        self.assertEqual(result.returncode, 1, result.stdout)
        payload = json.loads(result.stdout)
        self.assertIn("save", payload["error"])
        self.assertIn("without --dev", payload["hint"])


class TestDevInitOnAFreshStore(DevIsolationTestBase):
    """`--dev init` must initialize a store the CLI itself only pre-created.

    The CLI opens every dev command by creating the store directory, so init
    must judge the store by its contents -- its git repo, or task records --
    never by the directory's existence. A fresh path has to initialize, and
    only a genuinely initialized store may refuse.
    """

    def run_against_store(self, args, store):
        """Run the --dev CLI with the store pointed at a separate path."""
        env = {**os.environ, "HAMMER_DEV_TASKS_DIR": store}
        return subprocess.run(
            [self.script_path, "tasks", "-j", "--dev"] + args,
            cwd=self.repo_path,
            capture_output=True,
            text=True,
            check=False,
            env=env,
        )

    def fresh_store(self, name):
        """A store path that does not exist yet, as the repro starts from."""
        store = os.path.join(self.test_root, name)
        self.assertFalse(os.path.exists(store), f"{store} must start as a fresh path")
        return store

    def seed_store_counter(self, store, value):
        counter = os.path.join(store, ".task_counter")
        with open(counter, "w") as handle:
            handle.write(str(value))
        with open(os.path.join(store, ".task_counter.hash"), "w") as handle:
            handle.write(hashlib.md5(str(value).encode()).hexdigest())

    def test_fresh_path_initializes_into_a_git_repo(self):
        store = self.fresh_store("fresh-init")
        result = self.run_against_store(["init"], store)
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertTrue(
            os.path.isdir(os.path.join(store, ".git")),
            f"initialized store is not a git repo: {result.stdout}",
        )

    def test_initialized_store_refuses_without_force_and_resets_with_force(self):
        store = self.fresh_store("fresh-refuse")
        self.assertEqual(self.run_against_store(["init"], store).returncode, 0)

        again = self.run_against_store(["init"], store)
        self.assertEqual(again.returncode, 1, again.stdout)
        self.assertIn("already initialized", json.loads(again.stdout)["error"])

        forced = self.run_against_store(["init", "--force"], store)
        self.assertEqual(forced.returncode, 0, forced.stdout)
        self.assertTrue(os.path.isdir(os.path.join(store, ".git")))

    def test_store_records_without_a_git_repo_are_refused_not_clobbered(self):
        store = os.path.join(self.test_root, "record-store")
        os.makedirs(store)
        counter = os.path.join(store, ".task_counter")
        with open(counter, "w") as handle:
            handle.write("7")

        refused = self.run_against_store(["init"], store)
        self.assertEqual(refused.returncode, 1, refused.stdout)
        self.assertTrue(
            os.path.exists(counter),
            "a refused init destroyed the task records it found",
        )

        forced = self.run_against_store(["init", "--force"], store)
        self.assertEqual(forced.returncode, 0, forced.stdout)
        self.assertTrue(os.path.isdir(os.path.join(store, ".git")))

    def test_create_and_checkpoint_commit_against_a_fresh_store(self):
        store = self.fresh_store("fresh-cycle")
        self.assertEqual(self.run_against_store(["init"], store).returncode, 0)
        self.seed_store_counter(store, BASE_ID - 1)

        created = self.run_against_store(
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
            ],
            store,
        )
        self.assertEqual(created.returncode, 0, f"create failed: {created.stdout}")
        payload = json.loads(created.stdout)
        task_file = payload["data"]["file"]

        checkpointed = self.run_against_store(
            ["checkpoint", str(payload["data"]["id"])], store
        )
        self.assertEqual(checkpointed.returncode, 0, checkpointed.stdout)

        history = self.git(["log", "--all", "--oneline"], cwd=store).stdout
        self.assertIn(
            task_file,
            history,
            f"the create/checkpoint cycle never reached the store's git log:\n{history}",
        )


if __name__ == "__main__":
    unittest.main()
