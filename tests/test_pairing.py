import os
import shutil
import subprocess
import tempfile
import unittest


class TestTaskPairing(unittest.TestCase):

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.repo_dir = os.path.join(self.test_dir, 'repo')
        os.makedirs(self.repo_dir)
        subprocess.run(['git', 'init'], cwd=self.repo_dir, capture_output=True, check=False)
        subprocess.run(['git', 'config', 'user.email', 'test@example.com'], cwd=self.repo_dir, check=False)
        subprocess.run(['git', 'config', 'user.name', 'Test User'], cwd=self.repo_dir, check=False)
        self.tasks_script = os.path.abspath('tasks.py')
        subprocess.run(['python3', self.tasks_script, 'init'], cwd=self.repo_dir, check=False)

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def test_task_pairing(self):
        cmd = ['python3', self.tasks_script, 'create', 'New Feature Implementation', '--story', 'As a user, I want a new feature for the application.', '--tech', 'Python, Testing, and automated workflows.', '--criteria', 'Test criteria must be long enough.', '--plan', '1. Do work for this new feature.']
        result = subprocess.run(cmd, cwd=self.repo_dir, capture_output=True, text=True, check=False)
        print(f'STDOUT: {result.stdout}')
        print(f'STDERR: {result.stderr}')
        self.assertIn('Created: [1] task | New Feature Implementation', result.stdout)
        backlog_dir = os.path.join(self.repo_dir, '.tasks', 'backlog')
        files = os.listdir(backlog_dir)
        self.assertTrue(any('1-task-new-feature-implement' in f for f in files))
if __name__ == '__main__':
    unittest.main()