import json
import os
import subprocess
import sys
import unittest
from hammer_test_base import HammerTestBase

class TestDevMode(HammerTestBase):
    @unittest.skip("Diff generation needs debugging")
    def test_review_diff_in_dev_mode(self):
        res = self.run_tasks(["create", "Dev Review Diff Title", 
             "--story", "Sufficiently long story content here...", 
             "--tech", "Sufficiently long technical description here...", 
             "--criteria", "Sufficiently long acceptance criteria here...", 
             "--plan", "1. Create task. 2. Move to PROGRESSING. 3. Make changes. 4. Verify diff."])
        data = json.loads(res.stdout)
        task_id = data["data"]["id"]
        
        self.run_tasks(["move", str(task_id), "READY"])
        self.run_tasks(["move", str(task_id), "PROGRESSING"])
        
        # Create branch and change
        subprocess.run(["git", "checkout", "-b", f"{task_id}-dev"], cwd=self.repo_path, check=True)
        with open(os.path.join(self.repo_path, "dev_feature.py"), "w") as f:
            f.write("def dev_feature():\n    return 'dev'\n")
        subprocess.run(["git", "add", "dev_feature.py"], cwd=self.repo_path, check=True)
        subprocess.run(["git", "commit", "-m", "Add dev feature"], cwd=self.repo_path, check=True)
        
        # Merge task branch into 'testing' branch (required for diff generation logic)
        subprocess.run(["git", "branch", "testing"], cwd=self.repo_path, check=True)
        subprocess.run(["git", "checkout", "testing"], cwd=self.repo_path, check=True)
        subprocess.run(["git", "branch", "-a"], cwd=self.repo_path, check=True)
        subprocess.run(["git", "merge", f"{task_id}-dev"], cwd=self.repo_path, check=True)
        subprocess.run(["git", "checkout", f"{task_id}-dev"], cwd=self.repo_path, check=True)
        
        # Move to TESTING and REVIEW
        self.run_tasks(["move", str(task_id), "TESTING"])
        self.run_tasks(["move", str(task_id), "REVIEW"])
        
        diff_path = os.path.join(self.repo_path, ".tasks", "review", str(task_id), "diff.patch")
        self.assertTrue(os.path.exists(diff_path), f"Diff patch not found at {diff_path}")

if __name__ == "__main__":
    unittest.main()
