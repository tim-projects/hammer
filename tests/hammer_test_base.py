import unittest
import subprocess
import os
import shutil
import tempfile
import sys
import json


class MockGitRemote:
    def __init__(self, repo_dir):
        self.remote_dir = tempfile.mkdtemp(prefix="hammer_remote_")
        self.repo_dir = repo_dir
        subprocess.run(["git", "init", "--bare", self.remote_dir], check=True)

    def __enter__(self):
        # Configure the repo to use this as origin
        subprocess.run(
            ["git", "remote", "remove", "origin"],
            cwd=self.repo_dir,
            check=False,
            capture_output=True,
        )
        subprocess.run(
            ["git", "remote", "add", "origin", self.remote_dir],
            cwd=self.repo_dir,
            check=True,
        )
        return self.remote_dir

    def __exit__(self, exc_type, exc_val, exc_tb):
        shutil.rmtree(self.remote_dir)


class HammerTestBase(unittest.TestCase):
    def setUp(self):
        self.test_root = tempfile.mkdtemp(prefix="hammer_test_")
        self.dev_tasks_dir = tempfile.mkdtemp(prefix="hammer_tasks_")
        os.environ["HAMMER_DEV_TASKS_DIR"] = self.dev_tasks_dir

        self.repo_path = os.path.join(self.test_root, "repo")
        # Use full local clone
        subprocess.run(
            ["git", "clone", os.getcwd(), self.repo_path],
            check=True,
            capture_output=True,
        )
        # Remove cloned .tasks to prevent pre-initialization
        tasks_clone_path = os.path.join(self.repo_path, ".tasks")
        if os.path.exists(tasks_clone_path):
            shutil.rmtree(tasks_clone_path)

        self.script_path = os.path.join(self.repo_path, "tasks.py")

        # Configure isolated dev environment
        if os.path.exists(self.dev_tasks_dir):
            shutil.rmtree(self.dev_tasks_dir)
        os.makedirs(self.dev_tasks_dir, exist_ok=True)

        # Write config to dev_tasks_dir
        config_data = {
            "repo": {
                "lint": "ruff",
                "test": "/bin/true",
                "type_check": "/bin/true",
                "format": "ruff",
            }
        }
        with open(os.path.join(self.dev_tasks_dir, "config.yaml"), "w") as f:
            json.dump(config_data, f)

        # Ensure .tasks config is minimal or doesn't conflict
        tasks_dir = os.path.join(self.repo_path, ".tasks")
        os.makedirs(tasks_dir, exist_ok=True)
        # We want hammer to use HAMMER_DEV_TASKS_DIR, so ensure config doesn't override it
        with open(os.path.join(tasks_dir, "config.yaml"), "w") as f:
            json.dump({}, f)

        subprocess.run(
            [sys.executable, self.script_path, "--dev", "init", "--force"],
            cwd=self.repo_path,
            check=True,
            capture_output=True,
        )

    def tearDown(self):
        shutil.rmtree(self.test_root)
        shutil.rmtree(self.dev_tasks_dir)
        del os.environ["HAMMER_DEV_TASKS_DIR"]

    def run_tasks(self, args):
        return subprocess.run(
            [sys.executable, self.script_path, "-j", "--dev"] + args,
            cwd=self.repo_path,
            capture_output=True,
            text=True,
        )
