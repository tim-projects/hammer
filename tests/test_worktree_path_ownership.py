"""Hammer owns worktree paths: Git and .task-worktrees/ must agree.

Git's worktree registry is authoritative. The shared audit in
tasks_ai.utils.audit_worktrees is used by both the guard and WorktreeManager.
"""

import os
import shutil
import tempfile
import unittest

from tasks_ai.utils import audit_worktrees

BRANCH = "350-PROGRESSING"


class TestAuditWorktrees(unittest.TestCase):
    BASE = "/repo/.task-worktrees"
    GOOD = "/repo/.task-worktrees/" + BRANCH

    def test_registered_and_live_worktree_is_clean(self):
        self.assertEqual(
            audit_worktrees([{"branch": BRANCH, "path": self.GOOD}], self.BASE),
            [],
        )

    def test_recorded_legacy_task_branch_is_authoritative(self):
        legacy_branch = "350-task-example"
        legacy_path = os.path.join(self.BASE, legacy_branch)
        self.assertEqual(
            audit_worktrees(
                [{"branch": legacy_branch, "path": legacy_path}],
                self.BASE,
                {"350": legacy_branch},
            ),
            [],
        )

    def test_path_that_is_not_the_branch_name_is_drift(self):
        drifted = self.GOOD + "x"
        findings = audit_worktrees([{"branch": BRANCH, "path": drifted}], self.BASE)
        self.assertEqual([f[0] for f in findings], ["GUARD_WORKTREE_PATH_DRIFT"])
        self.assertIn("expected", findings[0][2])

    def test_path_outside_the_base_is_drift(self):
        findings = audit_worktrees(
            [{"branch": BRANCH, "path": "/elsewhere/350"}], self.BASE
        )
        self.assertEqual([f[0] for f in findings], ["GUARD_WORKTREE_PATH_DRIFT"])

    def test_local_task_store_is_reported(self):
        base = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, base, ignore_errors=True)
        worktree = os.path.join(base, BRANCH)
        os.makedirs(os.path.join(worktree, ".tasks"))
        findings = audit_worktrees([{"branch": BRANCH, "path": worktree}], base)
        self.assertIn("GUARD_WORKTREE_LOCAL_STORE", [f[0] for f in findings])

    def test_unregistered_directory_under_the_base(self):
        base = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, base, ignore_errors=True)
        worktrees_base = os.path.join(base, ".task-worktrees")
        os.makedirs(os.path.join(worktrees_base, BRANCH))
        os.makedirs(os.path.join(worktrees_base, "999-task-does-not-exist"))
        good = os.path.join(worktrees_base, BRANCH)
        findings = audit_worktrees([{"branch": BRANCH, "path": good}], worktrees_base)
        self.assertEqual(len(findings), 1)
        code, task_id, detail = findings[0]
        self.assertEqual(code, "GUARD_WORKTREE_UNREGISTERED")
        self.assertIsNone(task_id)
        self.assertIn("999-task-does-not-exist", detail)


class TestRemoveUnregisteredDir(unittest.TestCase):
    """The doctor repair: only paths Git does not own, never a real worktree."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.base = os.path.join(self.tmp, ".task-worktrees")
        self.tasks_path = os.path.join(self.tmp, ".tasks")
        os.makedirs(self.tasks_path)
        self.stray = os.path.join(self.base, "999-task-does-not-exist")
        self.registered = os.path.join(self.base, BRANCH)
        os.makedirs(self.stray)
        os.makedirs(self.registered)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _manager(self):
        from tasks_ai.worktree_manager import WorktreeManager

        base_dir, registered_dir = self.tmp, self.registered

        class Git:
            def run(self, args, cwd=None, **kwargs):
                class R:
                    returncode = 1
                    stdout = ""
                    stderr = "not a repo"

                if args[:2] == ["worktree", "list"]:
                    R.stdout = (
                        f"worktree {base_dir}\n\n"
                        f"worktree {registered_dir}\nbranch {BRANCH}\n"
                    )
                    R.returncode = 0
                return R()

        mgr = WorktreeManager.__new__(WorktreeManager)
        mgr.context = type(
            "C", (), {"main_repo_root": self.tmp, "tasks_path": self.tasks_path}
        )()
        mgr.git = Git()
        return mgr

    def test_removes_unregistered_directory(self):
        mgr = self._manager()
        self.assertTrue(mgr.remove_unregistered_dir(self.stray))
        self.assertFalse(os.path.exists(self.stray))
        self.assertTrue(os.path.exists(self.registered))

    def test_refuses_registered_directory(self):
        mgr = self._manager()
        self.assertFalse(mgr.remove_unregistered_dir(self.registered))

    def test_refuses_path_outside_the_base(self):
        mgr = self._manager()
        outside = os.path.join(self.tmp, "somewhere-else")
        os.makedirs(outside)
        self.assertFalse(mgr.remove_unregistered_dir(outside))

    def test_audit_and_repair_agree_on_the_same_repo(self):
        mgr = self._manager()
        findings = mgr.audit_worktrees()
        self.assertEqual([f[0] for f in findings], ["GUARD_WORKTREE_UNREGISTERED"])
        mgr.remove_unregistered_dir(findings[0][2].split(": ", 1)[-1])
        self.assertEqual(mgr.audit_worktrees(), [])
