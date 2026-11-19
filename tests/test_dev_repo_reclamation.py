import os
import shutil
import tempfile
import time
import unittest

from tasks_ai.context import HARNESS_STALE_AFTER, ProjectContext


def _mk(name, stale=False):
    """Create a harness-looking dir; old mtime when `stale`."""
    path = os.path.join(tempfile.gettempdir(), name)
    shutil.rmtree(path, ignore_errors=True)
    os.makedirs(path)
    with open(os.path.join(path, "marker"), "w") as f:
        f.write("x")
    if stale:
        old = time.time() - HARNESS_STALE_AFTER - 60
        os.utime(path, (old, old))
    return path


class TestReclaimStaleDevDirs(unittest.TestCase):
    def setUp(self):
        self.tracked = []
        self.addCleanup(self._cleanup)

    def _track(self, path):
        self.tracked.append(path)
        return path

    def _cleanup(self):
        for path in self.tracked:
            shutil.rmtree(path, ignore_errors=True)

    def test_stale_harness_dirs_are_removed(self):
        stale_store = self._track(_mk("hammer_tasks_staleA", stale=True))
        stale_repo = self._track(_mk("hammer_tasks_staleB-repo", stale=True))
        stale_test = self._track(_mk("hammer_test_staleC", stale=True))
        fresh_store = self._track(_mk("hammer_tasks_freshD"))
        foreign = self._track(_mk("hammer_tasks_sweptE", stale=True))
        ProjectContext.reclaim_stale_dev_dirs(
            self._track(tempfile.mkdtemp(prefix="hammer_tasks_live_"))
        )
        self.assertFalse(os.path.exists(stale_store))
        self.assertFalse(os.path.exists(stale_repo))
        self.assertFalse(os.path.exists(stale_test))
        self.assertTrue(os.path.isdir(fresh_store))
        # Anything carrying a harness prefix and old enough is swept; dirs with
        # no harness prefix are never touched.
        self.assertFalse(os.path.exists(foreign))
        untouched = self._track(_mk("outside_prefix_x", stale=True))
        self.assertTrue(os.path.isdir(untouched))

    def test_live_store_and_its_repo_are_never_touched(self):
        store = self._track(tempfile.mkdtemp(prefix="hammer_tasks_live_"))
        repo = self._track(_mk(os.path.basename(store) + "-repo", stale=True))
        old = time.time() - HARNESS_STALE_AFTER - 60
        os.utime(store, (old, old))
        ProjectContext.reclaim_stale_dev_dirs(store, now=time.time())
        self.assertTrue(os.path.isdir(store))
        self.assertTrue(os.path.isdir(repo))


class TestCleanupSurvivesSetupFailure(unittest.TestCase):
    """addCleanup (not tearDown) is what makes a setUp failure still clean up."""

    def test_cleanup_survives_a_setup_failure(self):
        """addCleanup (not tearDown) is what makes a setUp failure still clean up."""
        from tests.hammer_test_base import cleanup_path

        victim = tempfile.mkdtemp(prefix="hammer_test_setupfail_")
        self.addCleanup(lambda: shutil.rmtree(victim, ignore_errors=True))

        class FailsInSetUp(unittest.TestCase):
            def runTest(self):
                pass

        def broken_setup(self):
            self.addCleanup(cleanup_path, victim)

            raise AssertionError("setUp exploded")

        FailsInSetUp.setUp = broken_setup
        result = unittest.TestResult()
        unittest.TestSuite([FailsInSetUp()]).run(result)
        self.assertTrue(result.errors or result.failures)
        self.assertFalse(os.path.exists(victim))


if __name__ == "__main__":
    unittest.main()
