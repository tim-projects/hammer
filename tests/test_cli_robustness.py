import unittest
import subprocess
import os
import shutil
import tempfile


class TestCLIRobustness(unittest.TestCase):
    def setUp(self):
        self.repo_dir = tempfile.mkdtemp()
        self.hammer_path = os.path.abspath(os.path.join(self.repo_dir, "hammer"))
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        os.symlink(os.path.join(project_root, "hammer"), self.hammer_path)

    def tearDown(self):
        shutil.rmtree(self.repo_dir)

    def test_create_validation_missing_fields(self):
        """Task create should fail if required fields are missing."""
        subprocess.run(
            [self.hammer_path, "init"],
            cwd=self.repo_dir,
            capture_output=True,
        )

        # Test with missing fields
        result = subprocess.run(
            [
                self.hammer_path,
                "create",
                "Valid Task Title Here",
            ],
            cwd=self.repo_dir,
            capture_output=True,
            text=True,
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Missing:", result.stderr)

    def test_create_validation_short_fields(self):
        """Task create should fail if fields are too short."""
        subprocess.run(
            [self.hammer_path, "init"],
            cwd=self.repo_dir,
            capture_output=True,
        )

        # Test with too short fields
        result = subprocess.run(
            [
                self.hammer_path,
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
        self.assertIn("Too short:", result.stderr)


if __name__ == "__main__":
    unittest.main()
