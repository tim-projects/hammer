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
        # Create dummy task data
        os.makedirs(os.path.join(self.dev_tasks, "backlog"), exist_ok=True)
        with open(os.path.join(self.dev_tasks, "backlog", "test.md"), "w") as f:
            f.write("dummy task content")

    def tearDown(self):
        if os.path.exists(self.dev_tasks):
            shutil.rmtree(self.dev_tasks)
        # Clean up /tmp backups created by the test
        repo_name = os.path.basename(self.repo_root)
        backup_dir = f"/tmp/{repo_name}"
        if os.path.exists(backup_dir):
            shutil.rmtree(backup_dir)

    def test_init_creates_backup(self):
        repo_name = os.path.basename(self.repo_root)

        # Run hammer init --dev
        subprocess.run(["./hammer", "tasks", "--dev", "init"], check=True)

        # Verify backup exists
        backup_dir = f"/tmp/{repo_name}"
        backups = [d for d in os.listdir(backup_dir) if d.startswith(".tasks.bak_")]
        self.assertTrue(len(backups) > 0, "Backup directory not found")

        # Verify backup content
        latest_backup = os.path.join(backup_dir, backups[0])
        self.assertTrue(
            os.path.exists(os.path.join(latest_backup, "backlog", "test.md"))
        )


if __name__ == "__main__":
    unittest.main()
