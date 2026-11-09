import os
import shutil
import subprocess

from tests.hammer_test_base import HammerTestBase, MockGitRemote


# The harness checks out main, so these files must come from the branch under
# test for save/push behavior to be the branch's.
class TestRepo(HammerTestBase):
    def setUp(self):
        super().setUp()
        # The harness checks out main; install the branch's code as a whole so
        # the fixture never mixes main's commands with the branch's utils.
        for rel in ("hammer", "tasks.py"):
            shutil.copy2(
                os.path.join(os.getcwd(), rel), os.path.join(self.repo_path, rel)
            )
        for rel in ("tasks_ai", "data"):
            src = os.path.join(os.getcwd(), rel)
            dst = os.path.join(self.repo_path, rel)
            shutil.rmtree(dst, ignore_errors=True)
            shutil.copytree(src, dst, ignore=shutil.ignore_patterns("__pycache__"))
        # Commit the copies: 'repo git status' asserts a clean tree.
        subprocess.run(["git", "add", "-A"], cwd=self.repo_path, capture_output=True)  # noqa: PLW1510
        subprocess.run(  # noqa: PLW1510
            ["git", "commit", "-m", "branch code under test"],
            cwd=self.repo_path,
            capture_output=True,
        )

    def test_repo_git_status(self):
        """Test 'repo git status' command."""
        result = subprocess.run(  # noqa: PLW1510
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
        result = subprocess.run(  # noqa: PLW1510
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
            # Ensure the tasks branch is pushed so auto-archive and save do not fail
            subprocess.run(
                ["git", "push", "-u", "origin", "tasks"],
                cwd=tasks_path,
                check=False,
            )

            result = self.run_tasks(["save", "-y"])
            self.assertEqual(
                result.returncode,
                0,
                f"Stdout: {result.stdout}, Stderr: {result.stderr}",
            )
            self.assertIn("Pushed .tasks", result.stdout)
