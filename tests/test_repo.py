from tests.hammer_test_base import HammerTestBase, MockGitRemote
import subprocess
import os

class TestRepo(HammerTestBase):
    def test_repo_git_status(self):
        """Test 'repo git status' command."""
        result = subprocess.run(
            ["python3", self.script_path.replace("tasks.py", "repo.py"), "git", "status"],
            cwd=self.repo_path,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert (
            "nothing to commit" in result.stdout.lower()
            or "working tree clean" in result.stdout.lower()
        )

    def test_repo_git_branch(self):
        """Test 'repo git branch' command."""
        result = subprocess.run(
            ["python3", self.script_path.replace("tasks.py", "repo.py"), "git", "branch"],
            cwd=self.repo_path,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert "299-task-" in result.stdout

    def test_repo_save_with_mock_remote(self):
        with MockGitRemote(self.repo_path) as remote_dir:
            # Configure origin in the .tasks folder
            tasks_path = os.path.join(self.repo_path, ".tasks")
            # Ensure origin is set
            subprocess.run(["git", "remote", "remove", "origin"], cwd=tasks_path, check=False)
            subprocess.run(["git", "remote", "add", "origin", remote_dir], cwd=tasks_path, check=True)
            
            # DEBUG
            remotes = subprocess.run(["git", "remote", "-v"], cwd=tasks_path, capture_output=True, text=True)
            is_git = subprocess.run(["git", "rev-parse", "--is-inside-work-tree"], cwd=tasks_path, capture_output=True, text=True)
            print(f"DEBUG: Remotes in {tasks_path}: {remotes.stdout}")
            print(f"DEBUG: Is inside work tree {tasks_path}: {is_git.stdout.strip()}")

            result = self.run_tasks(["save", "-y"])
            self.assertEqual(result.returncode, 0, f"Stdout: {result.stdout}, Stderr: {result.stderr}")
            self.assertIn("Pushed .tasks", result.stdout)
