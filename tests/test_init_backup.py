import json
import os
import shutil
import subprocess
import unittest


class TestInitBackup(unittest.TestCase):

    def setUp(self):
        self.repo_root = os.getcwd()
        self.dev_tasks = '/tmp/.tasks'
        if os.path.exists(self.dev_tasks):
            shutil.rmtree(self.dev_tasks)
        os.makedirs(self.dev_tasks, exist_ok=True)
        task_dir = os.path.join(self.dev_tasks, 'backlog', '1-test-task')
        os.makedirs(task_dir, exist_ok=True)
        with open(os.path.join(task_dir, 'meta.json'), 'w') as f:
            json.dump({'Id': 1}, f)
        with open(os.path.join(self.dev_tasks, '.task_counter'), 'w') as f:
            f.write('1')

    def tearDown(self):
        if os.path.exists(self.dev_tasks):
            shutil.rmtree(self.dev_tasks)
        backup_root = os.path.join(os.path.dirname(self.dev_tasks), '.tasks.backup')
        if os.path.exists(backup_root):
            shutil.rmtree(backup_root)

    def test_init_creates_backup_in_dev_mode(self):
        subprocess.run(['./hammer', 'tasks', '--dev', 'init', '--force'], check=True)
        backup_root = os.path.join(os.path.dirname(self.dev_tasks), '.tasks.backup')
        self.assertTrue(os.path.exists(backup_root), 'Backup root directory not found')
        backups = os.listdir(backup_root)
        self.assertTrue(len(backups) > 0, 'No timestamped backup directories found')
        latest_backup = os.path.join(backup_root, backups[-1])
        backed_tasks = os.path.join(latest_backup, '.tasks')
        self.assertTrue(os.path.exists(backed_tasks), 'Backed up .tasks directory not found')
        backlog_path = os.path.join(backed_tasks, 'backlog')
        task_folders = [d for d in os.listdir(backlog_path) if os.path.isdir(os.path.join(backlog_path, d))]
        self.assertTrue(len(task_folders) > 0, 'No task found in backup backlog')
        task_dir = os.path.join(backlog_path, task_folders[0])
        self.assertTrue(os.path.exists(os.path.join(task_dir, 'meta.json')))

    def test_init_adds_tasks_backup_to_gitignore(self):
        subprocess.run(['./hammer', 'tasks', '--dev', 'init', '--force'], check=True)
        gitignore_path = os.path.join(self.repo_root, '.gitignore')
        with open(gitignore_path, 'r') as f:
            content = f.read()
        self.assertIn('/.tasks.backup/', content)
if __name__ == '__main__':
    unittest.main()