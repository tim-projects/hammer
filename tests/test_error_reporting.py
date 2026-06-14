#!/usr/bin/env python3
import os
import subprocess
import shutil
import tempfile
import unittest
import json
import sys


class TestErrorReporting(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.repo_dir = os.path.join(self.test_dir, "repo")
        os.makedirs(self.repo_dir)
        subprocess.run(["git", "init"], cwd=self.repo_dir, capture_output=True)
        subprocess.run(
            ["git", "config", "user.email", "test@example.com"], cwd=self.repo_dir
        )
        subprocess.run(["git", "config", "user.name", "Test User"], cwd=self.repo_dir)
        # We need to find where 'tasks.py' is. It's in the project root.
        # Assuming the current working directory is the project root.
        self.script_path = os.path.abspath("tasks.py")

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def run_cmd(self, args):
        # Use --dev to avoid affecting real repo
        cmd = [sys.executable, self.script_path, "--dev"] + args
        result = subprocess.run(
            cmd,
            cwd=self.repo_dir,
            capture_output=True,
            text=True,
        )
        return result

    def test_trigger_generic_errors(self):
        errors_to_test = [
            (["create"], "Missing: --story"),
            (["move", "999", "DONE"], "not found"),
            (["link", "1", "1"], "Cannot link"),
        ]

        report = {}
        for args, expected_snippet in errors_to_test:
            res = self.run_cmd(args)
            print(f"Command: {' '.join(args)}")
            print(f"Stdout: {res.stdout}")
            print(f"Stderr: {res.stderr}")
            # Check if it has a HINT or formal report structure
            has_hint = "HINT:" in res.stderr or "HINT:" in res.stdout

            report[str(args)] = {
                "has_hint": has_hint,
                "stdout": res.stdout.strip(),
                "stderr": res.stderr.strip(),
            }

        with open("error_report.json", "w") as f:
            json.dump(report, f, indent=2)


if __name__ == "__main__":
    unittest.main()
