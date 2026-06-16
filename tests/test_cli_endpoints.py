from tests.hammer_test_base import HammerTestBase
import subprocess

class TestCliEndpoints(HammerTestBase):
    def test_tasks_list(self):
        result = self.run_tasks(["list"])
        self.assertEqual(result.returncode, 0)

    def test_tasks_create(self):
        # Create a task to ensure create works
        result = self.run_tasks(["create", "New Task Title", "--story", "Story...", "--tech", "Tech...", "--criteria", "1. Criteria", "--plan", "1. Plan"])
        if result.returncode != 0:
            print(f"Stdout: {result.stdout}")
            print(f"Stderr: {result.stderr}")
        self.assertEqual(result.returncode, 0)
        self.assertIn("Created:", result.stdout)

    def test_check_lint(self):
        result = subprocess.run(
            ["python3", self.script_path.replace("tasks.py", "check.py"), "lint"],
            cwd=self.repo_path,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            print(f"Stdout: {result.stdout}")
            print(f"Stderr: {result.stderr}")
        self.assertEqual(result.returncode, 0)
