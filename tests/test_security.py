import os
import shutil
import tempfile
import unittest
from tasks_ai.cli import TasksCLI

class TestSecurity(unittest.TestCase):

    def setUp(self):
        import sys
        sys._called_from_test = True
        self.tmp_dir = tempfile.mkdtemp()
        self.old_cwd = os.getcwd()
        os.chdir(self.tmp_dir)
        import subprocess
        subprocess.run(['git', 'init'], capture_output=True, check=False)
        self.cli = TasksCLI(quiet=True)
        self.cli.init()

    def tearDown(self):
        os.chdir(self.old_cwd)
        shutil.rmtree(self.tmp_dir)

    def test_directory_traversal(self):
        path, state = self.cli.find_task('../../../etc/passwd')
        self.assertIsNone(path)
        path, _state = self.cli.find_task('.._.._etc_passwd')
        self.assertIsNone(path)

    def test_invalid_task_ids(self):
        invalid_ids = ['1; rm -rf /', "task' OR '1'='1", '$(whoami)', 'task\nnewline', 'task\x00null']
        for tid in invalid_ids:
            path, _state = self.cli.find_task(tid)
            self.assertIsNone(path, f"ID '{tid}' should be rejected")

    def test_id_cleaning_on_create(self):
        self.cli.create('Task with <script>alert(1)</script>', story='...', tech='...', criteria='...', plan='...')
        backlog = os.path.join(self.cli.tasks_path, 'backlog')
        items = os.listdir(backlog)
        task_dir = next((item for item in items if 'script' in item))
        self.assertFalse('<' in task_dir)
        self.assertFalse('>' in task_dir)
        self.assertFalse('(' in task_dir)
        self.assertFalse(')' in task_dir)
        self.assertTrue(task_dir.startswith('1-task-task-with-script-alert-1-'))
if __name__ == '__main__':
    unittest.main()