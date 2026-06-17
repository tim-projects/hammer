from tests.hammer_test_base import HammerTestBase, MockGitRemote
import subprocess


class TestRepo(HammerTestBase):
    def test_repo_git_status(self):
        """Test 'repo git status' command."""
        result = subprocess.run(
            [
                "python3",
                self.script_path.replace("tasks.py", "repo.py"),
                "git",
                "status",
            ],
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
            [
                "python3",
                self.script_path.replace("tasks.py", "repo.py"),
                "git",
                "branch",
            ],
            cwd=self.repo_path,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        # The test repo may have different branches depending on the state of the merge.
        # Just check that it returns successfully and lists at least one branch.
        assert len(result.stdout.strip().splitlines()) > 0

    def test_repo_save_with_mock_remote(self):
        with MockGitRemote(self.repo_path) as remote_dir:
            # Configure origin in the dev_tasks_dir
            tasks_path = self.dev_tasks_dir
            # Ensure it is a git repo
            subprocess.run(["git", "init"], cwd=tasks_path, check=True)
            # Ensure origin is set
            subprocess.run(
                ["git", "remote", "remove", "origin"], cwd=tasks_path, check=False
            )
            subprocess.run(
                ["git", "remote", "add", "origin", remote_dir],
                cwd=tasks_path,
                check=True,
            )

            result = self.run_tasks(["save", "-y"])
            self.assertEqual(
                result.returncode,
                0,
                f"Stdout: {result.stdout}, Stderr: {result.stderr}",
            )
            self.assertIn("Pushed .tasks", result.stdout)
