import unittest
import subprocess
import sys
import os
import shutil
import tempfile


class TestCLIRobustness(unittest.TestCase):
    def setUp(self):
        self.repo_dir = tempfile.mkdtemp()
        self.tasks_py = os.path.join(os.getcwd(), "tasks.py")

    def tearDown(self):
        shutil.rmtree(self.repo_dir)

    def test_create_validation_missing_fields(self):
        """Task create should fail if required fields are missing."""
        subprocess.run(
            [sys.executable, self.tasks_py, "init"],
            cwd=self.repo_dir,
            capture_output=True,
        )

        # Test with missing fields
        result = subprocess.run(
            [
                sys.executable,
                self.tasks_py,
                "create",
                "Valid Task Title Here",
            ],
            cwd=self.repo_dir,
            capture_output=True,
            text=True,
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("MISSING_PARTS", result.stderr)

    def test_create_validation_short_fields(self):
        """Task create should fail if fields are too short."""
        subprocess.run(
            [sys.executable, self.tasks_py, "init"],
            cwd=self.repo_dir,
            capture_output=True,
        )

        # Test with too short fields
        result = subprocess.run(
            [
                sys.executable,
                self.tasks_py,
                "create",
                "Valid Task Title Here",
                "--story",
                "Short",
                "--tech",
                "Short",
                "--criteria",
                "Short",
                "--plan",
                "Short",
            ],
            cwd=self.repo_dir,
            capture_output=True,
            text=True,
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("TOO_SHORT", result.stderr)


if __name__ == "__main__":
    unittest.main()
