#!/usr/bin/env python3
import os
import subprocess
import shutil
import tempfile
import unittest
import json
import sys
from datetime import datetime, timedelta

class TestTasksAI(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.repo_dir = os.path.join(self.test_dir, "repo")
        os.makedirs(self.repo_dir)
        subprocess.run(["git", "init"], cwd=self.repo_dir, capture_output=True)
        subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=self.repo_dir)
        subprocess.run(["git", "config", "user.name", "Test User"], cwd=self.repo_dir)
        with open(os.path.join(self.repo_dir, "README.md"), "w") as f: f.write("# Test Repo")
        subprocess.run(["git", "add", "README.md"], cwd=self.repo_dir)
        subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=self.repo_dir)
        self.script_path = os.path.abspath("tasks.py")

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def run_cmd(self, args):
        result = subprocess.run([sys.executable, self.script_path, "-j"] + args, 
                               cwd=self.repo_dir, capture_output=True, text=True)
        try:
            return json.loads(result.stdout)
        except json.JSONDecodeError:
            return {"success": False, "error": "JSON Decode Error", "stdout": result.stdout, "stderr": result.stderr}

    def test_full_lifecycle(self):
        res = self.run_cmd(["init"])
        self.assertTrue(res["success"], res)

        res = self.run_cmd(["create", "First Task", "--priority", "3"])
        self.assertTrue(res["success"], res)
        task_file = res["data"]["file"] # This is just filename

        res = self.run_cmd(["create", "Urgent Bug", "--type", "issue"])
        self.assertTrue(res["success"], res)
        issue_file = res["data"]["file"]

        # Move to READY (Required)
        res = self.run_cmd(["move", issue_file, "READY"])
        self.assertTrue(res["success"], res)
        
        # Verify it moved from backlog to ready
        self.assertFalse(os.path.exists(os.path.join(self.repo_dir, "tasks", "backlog", issue_file)))
        self.assertTrue(os.path.exists(os.path.join(self.repo_dir, "tasks", "ready", issue_file)))

        # Move to PROGRESSING
        res = self.run_cmd(["move", issue_file, "PROGRESSING"])
        self.assertTrue(res["success"], res)

        # Linking
        self.run_cmd(["move", task_file, "READY"])
        res = self.run_cmd(["link", task_file, issue_file])
        self.assertTrue(res["success"], res)
        
        # Verify blocked (Urgent Bug is in PROGRESSING, not ARCHIVED)
        res = self.run_cmd(["move", task_file, "PROGRESSING"])
        self.assertFalse(res["success"], res)
        self.assertIn("Blocked by", res.get("error", ""))

        # Move issue through states
        for state in ["TESTING", "REVIEW", "STAGING", "LIVE"]:
            _, branch = issue_file.rsplit('.', 1)[0].split('_', 1)
            subprocess.run(["git", "checkout", "-b", branch], cwd=self.repo_dir, capture_output=True)
            with open(os.path.join(self.repo_dir, "fix.txt"), "a") as f: f.write("fixed\n")
            subprocess.run(["git", "add", "fix.txt"], cwd=self.repo_dir, capture_output=True)
            subprocess.run(["git", "commit", "-m", "Work"], cwd=self.repo_dir, capture_output=True)
            subprocess.run(["git", "checkout", "main"], cwd=self.repo_dir, capture_output=True)
            
            res = self.run_cmd(["move", issue_file, state])
            self.assertTrue(res["success"], f"Failed move to {state}: {res}")

        # Archive (Needs a commit)
        res = self.run_cmd(["move", issue_file, "ARCHIVED"])
        self.assertTrue(res["success"], res)

        # Now unblocked
        res = self.run_cmd(["move", task_file, "PROGRESSING"])
        self.assertTrue(res["success"], res)

    def test_auto_archival(self):
        self.run_cmd(["init"])
        res = self.run_cmd(["create", "Old Task"])
        file = res["data"]["file"]
        
        self.run_cmd(["move", file, "READY"])
        self.run_cmd(["move", file, "PROGRESSING"])
        
        _, branch = file.rsplit('.', 1)[0].split('_', 1)
        subprocess.run(["git", "checkout", "-b", branch], cwd=self.repo_dir, capture_output=True)
        with open(os.path.join(self.repo_dir, "code.txt"), "w") as f: f.write("code")
        subprocess.run(["git", "add", "code.txt"], cwd=self.repo_dir, capture_output=True)
        subprocess.run(["git", "commit", "-m", "Work"], cwd=self.repo_dir, capture_output=True)
        subprocess.run(["git", "checkout", "main"], cwd=self.repo_dir, capture_output=True)
        
        for state in ["TESTING", "REVIEW", "STAGING", "LIVE"]:
            self.run_cmd(["move", file, state])
        
        # Backdate log
        log_path = os.path.join(self.repo_dir, "tasks", "logs", file)
        old_date = (datetime.now() - timedelta(days=8)).strftime('%y%m%d %H:%M')
        with open(log_path, "w") as f: f.write(f"- {old_date}: STAGING->LIVE\n")
            
        res = self.run_cmd(["list"])
        self.assertIn(f"Auto-archiving: {file}", res["messages"], res)
        self.assertTrue(os.path.exists(os.path.join(self.repo_dir, "tasks", "archived", file)))
        self.assertFalse(os.path.exists(os.path.join(self.repo_dir, "tasks", "live", file)))

if __name__ == "__main__":
    unittest.main()
