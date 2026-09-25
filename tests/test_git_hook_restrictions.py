import os
import shutil
import subprocess
import tempfile
import unittest
from tasks_ai.cli import TasksCLI

class TestGitHookRestrictions(unittest.TestCase):

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.old_cwd = os.getcwd()
        os.chdir(self.tmp_dir)
        subprocess.run(['git', 'init'], capture_output=True, check=False)
        with open('README.md', 'w') as f:
            f.write('# Main branch')
        subprocess.run(['git', 'add', 'README.md'], capture_output=True, check=False)
        subprocess.run(['git', 'commit', '-m', 'Initial commit'], capture_output=True, check=False)
        self.cli = TasksCLI(quiet=True)
        self.cli.finish = lambda data=None: None
        self.cli.init()

    def tearDown(self):
        os.chdir(self.old_cwd)
        shutil.rmtree(self.tmp_dir)

    def test_direct_commit_to_main_rejected(self):
        with open('main_file.txt', 'w') as f:
            f.write('direct commit')
        subprocess.run(['git', 'add', 'main_file.txt'], capture_output=True, check=False)
if __name__ == '__main__':
    unittest.main()