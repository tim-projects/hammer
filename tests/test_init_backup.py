import json
import os
import shutil
import subprocess
import unittest


class TestInitBackup(unittest.TestCase):
    def setUp(self):
        self.repo_root = os.getcwd()
        self.dev_tasks = "/tmp/.tasks"
        # Ensure clean state
        if os.path.exists(self.dev_tasks):
            shutil.rmtree(self.dev_tasks)
        os.makedirs(self.dev_tasks, exist_ok=True)
        # Create dummy task data: folder with meta.json
        task_dir = os.path.join(self.dev_tasks, "backlog", "1-test-task")
        os.makedirs(task_dir, exist_ok=True)
        with open(os.path.join(task_dir, "meta.json"), "w") as f:
            json.dump({"Id": 1}, f)
        with open(os.path.join(self.dev_tasks, ".task_counter"), "w") as f:
            f.write("1")

    def tearDown(self):
        if os.path.exists(self.dev_tasks):
            shutil.rmtree(self.dev_tasks)
        # Clean up /tmp backups created by the test
        # Backups are created in /tmp/.tasks.bak_...
        import glob

        for f in glob.glob("/tmp/.tasks.bak_*"):
            shutil.rmtree(f)

    @unittest.skip("Skipping incompatible dev-mode backup test")
    def test_init_creates_backup(self):

        # Run hammer init --dev
        subprocess.run(["./hammer", "tasks", "--dev", "init"], check=True)

        # Verify backup exists
        backups = [d for d in os.listdir("/tmp") if d.startswith(".tasks.bak_")]
        self.assertTrue(len(backups) > 0, "Backup directory not found in /tmp")

        # Verify backup content
        backups = [d for d in os.listdir("/tmp") if d.startswith(".tasks.bak_")]
        latest_backup = os.path.join("/tmp", backups[-1])

        # Find any md file in backlog to verify contents
        backlog_path = os.path.join(latest_backup, "backlog")
        task_folders = [
            d
            for d in os.listdir(backlog_path)
            if os.path.isdir(os.path.join(backlog_path, d))
        ]
        self.assertTrue(len(task_folders) > 0, "No task found in backup backlog")

        task_dir = os.path.join(backlog_path, task_folders[0])
        self.assertTrue(os.path.exists(os.path.join(task_dir, "meta.json")))


if __name__ == "__main__":
    unittest.main()
