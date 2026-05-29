import unittest
import os
import shutil
import tempfile
import subprocess
from tasks_ai.cli import TasksCLI


class TestGitHookRestrictions(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.old_cwd = os.getcwd()
        os.chdir(self.tmp_dir)
        subprocess.run(["git", "init"], capture_output=True)
        # Create a dummy main file
        with open("README.md", "w") as f:
            f.write("# Main branch")
        subprocess.run(["git", "add", "README.md"], capture_output=True)
        subprocess.run(["git", "commit", "-m", "Initial commit"], capture_output=True)
        self.cli = TasksCLI(quiet=True)
        # Mock finish to avoid sys.exit(0)
        self.cli.finish = lambda data=None: None
        self.cli.init()

    def tearDown(self):
        os.chdir(self.old_cwd)
        shutil.rmtree(self.tmp_dir)

    def test_direct_commit_to_main_rejected(self):
        # This will be implemented once the hook is ready
        # For now, verify the test environment can detect the commit
        with open("main_file.txt", "w") as f:
            f.write("direct commit")
        subprocess.run(["git", "add", "main_file.txt"], capture_output=True)

        # We expect a custom hook (yet to be implemented) to reject this
        # This is a placeholder test for task 166
        pass


if __name__ == "__main__":
    unittest.main()
