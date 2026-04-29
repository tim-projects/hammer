import unittest
import subprocess
import os
import shutil
import tempfile
import sys
import json

class HammerTestBase(unittest.TestCase):
    def setUp(self):
        self.test_root = tempfile.mkdtemp(prefix="hammer_test_")
        self.repo_path = os.path.join(self.test_root, "repo")
        # Use full local clone
        subprocess.run(["git", "clone", os.getcwd(), self.repo_path], check=True, capture_output=True)
        self.script_path = os.path.join(self.repo_path, "tasks.py")
        
        # Configure isolated dev environment
        os.makedirs(os.path.join(self.repo_path, ".tasks"), exist_ok=True)
        with open(os.path.join(self.repo_path, ".tasks", "config.yaml"), "w") as f:
            json.dump({"repo": {"lint": "/bin/true", "test": "/bin/true", "type_check": "/bin/true", "format": "/bin/true"}}, f)
        
        subprocess.run([sys.executable, self.script_path, "--dev", "init"], 
                       cwd=self.repo_path, check=True, capture_output=True)

    def tearDown(self):
        shutil.rmtree(self.test_root)

    def run_tasks(self, args):
        return subprocess.run([sys.executable, self.script_path, "-j", "--dev"] + args, 
                              cwd=self.repo_path, capture_output=True, text=True)
