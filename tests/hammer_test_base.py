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
        self.worktree_path = os.path.join(self.test_root, "worktree")
        subprocess.run(["git", "worktree", "add", self.worktree_path], check=True, capture_output=True)
        self.script_path = os.path.join(self.worktree_path, "tasks.py")
        
        # Configure dummy validation tools
        os.makedirs(os.path.join(self.worktree_path, ".tasks"), exist_ok=True)
        config = {"repo": {}}
        with open(os.path.join("/tmp/.tasks", "config.yaml"), "w") as f:
            json.dump(config, f)
            
        subprocess.run([sys.executable, self.script_path, "--dev", "init"], 
                       cwd=self.worktree_path, check=True, capture_output=True)

    def tearDown(self):
        subprocess.run(["git", "worktree", "remove", self.worktree_path, "--force"], check=True, capture_output=True)
        shutil.rmtree(self.test_root)

    def run_tasks(self, args):
        return subprocess.run([sys.executable, self.script_path, "-j", "--dev"] + args, 
                              cwd=self.worktree_path, capture_output=True, text=True)
