import errno
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest


def cleanup_path(path):
    """Remove a test-owned path, failing loudly if cleanup fails."""
    for attempt in range(5):
        if not os.path.lexists(path):
            return
        try:
            shutil.rmtree(path)
            return
        except OSError as error:
            if error.errno != errno.ENOTEMPTY or attempt == 4:
                raise
            time.sleep(0.1)


class HammerTestBase(unittest.TestCase):
    def setUp(self):
        self.test_root = tempfile.mkdtemp(prefix="hammer_test_")
        self.addCleanup(cleanup_path, self.test_root)
        self.repo_path = os.path.join(self.test_root, "repo")
        subprocess.run(
            ["git", "clone", os.getcwd(), self.repo_path],
            check=True,
            capture_output=True,
        )
        self.script_path = os.path.join(self.repo_path, "tasks.py")

        os.makedirs(os.path.join(self.repo_path, ".tasks"), exist_ok=True)
        with open(os.path.join(self.repo_path, ".tasks", ".task_counter"), "w") as f:
            f.write("0")
        with open(os.path.join(self.repo_path, ".tasks", "config.yaml"), "w") as f:
            json.dump(
                {
                    "repo": {
                        "lint": "/bin/true",
                        "test": "/bin/true",
                        "type_check": "/bin/true",
                        "format": "/bin/true",
                    }
                },
                f,
            )

        subprocess.run(
            [sys.executable, self.script_path, "--dev", "init"],
            cwd=self.repo_path,
            check=True,
            capture_output=True,
        )

    def run_tasks(self, args):
        return subprocess.run(  # noqa: PLW1510
            [sys.executable, self.script_path, "-j", "--dev"] + args,
            cwd=self.repo_path,
            capture_output=True,
            text=True,
        )
