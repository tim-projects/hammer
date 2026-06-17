from tests.hammer_test_base import HammerTestBase


class TestCliEndpoints(HammerTestBase):
    def test_tasks_list(self):
        result = self.run_tasks(["list"])
        self.assertEqual(result.returncode, 0)

    def test_tasks_reconcile(self):
        # Reconcile should not fail in dev mode even if empty
        result = self.run_tasks(["reconcile"])
        self.assertEqual(result.returncode, 0)

    def test_tasks_doctor(self):
        # Doctor should not fail in dev mode
        result = self.run_tasks(["doctor"])
        self.assertEqual(result.returncode, 0)

    def test_tasks_create(self):
        # Create a task to ensure create works
        result = self.run_tasks(
            [
                "create",
                "New Task Title For Test",
                "--story",
                "Story is long enough...",
                "--tech",
                "Tech is long enough...",
                "--criteria",
                "1. Criteria is long enough...",
                "--plan",
                "1. Plan is long enough...",
            ]
        )
        self.assertEqual(result.returncode, 0)
        self.assertIn("Created:", result.stdout)

    def test_check_lint(self):
        # Should return success due to /bin/true config
        result = self.run_tasks(["check", "lint"])
        self.assertEqual(result.returncode, 0)
