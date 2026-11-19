import errno
import json
import os
import shutil
import subprocess
import tempfile
import time
import unittest


def dev_repo_path(tasks_dir):
    """Where the --dev CLI keeps its throwaway repo (see tasks_ai/context.py)."""
    return os.path.abspath(tasks_dir) + "-repo"


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


def cleanup_dev_store(tasks_dir):
    """Remove the dev repo clone and its store."""
    cleanup_path(dev_repo_path(tasks_dir))
    cleanup_path(tasks_dir)


def ensure_dev_repo(tasks_dir):
    """Path of the dev repo, creating it (a clone) on first use.

    The CLI creates it lazily on its first --dev invocation; tests that touch
    the repo before running a command need it to exist already.
    """
    import importlib

    context = importlib.import_module("tasks_ai.context")
    return context.ProjectContext(dev=True).repo_root


class MockGitRemote:
    def __init__(self, repo_dir):
        self._remote = tempfile.TemporaryDirectory(prefix="hammer_remote_")
        self.remote_dir = self._remote.name
        self.repo_dir = repo_dir
        subprocess.run(["git", "init", "--bare", self.remote_dir], check=True)

    def __enter__(self):
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
        self._remote.cleanup()


class HammerTestBase(unittest.TestCase):
    def setUp(self):
        self.test_root = tempfile.mkdtemp(prefix="hammer_test_")
        self.addCleanup(cleanup_path, self.test_root)
        self.dev_tasks_dir = tempfile.mkdtemp(prefix="hammer_tasks_")
        self.addCleanup(cleanup_dev_store, self.dev_tasks_dir)
        # Leak-proofing: register the restores BEFORE any mutation. A test that
        # failed mid-way used to skip tearDown and leak the env var (and a
        # deleted cwd) into every later test file in the same run.
        prev_env = os.environ.get("HAMMER_DEV_TASKS_DIR")
        prev_cwd = os.getcwd()

        def _restore_env():
            if prev_env is None:
                os.environ.pop("HAMMER_DEV_TASKS_DIR", None)
            else:
                os.environ["HAMMER_DEV_TASKS_DIR"] = prev_env

        def _restore_cwd():
            if os.path.isdir(prev_cwd):
                os.chdir(prev_cwd)

        self.addCleanup(_restore_env)
        self.addCleanup(_restore_cwd)
        os.environ["HAMMER_DEV_TASKS_DIR"] = self.dev_tasks_dir
        self.repo_path = os.path.join(self.test_root, "repo")
        subprocess.run(
            ["git", "clone", os.getcwd(), self.repo_path],
            check=True,
            capture_output=True,
            env={
                **os.environ,
                "GIT_CONFIG_COUNT": "1",
                "GIT_CONFIG_KEY_0": "maintenance.auto",
                "GIT_CONFIG_VALUE_0": "false",
            },
        )
        subprocess.run(
            ["git", "fetch", "origin", "tasks"],
            cwd=self.repo_path,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "branch", "tasks", "origin/tasks"],
            cwd=self.repo_path,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "checkout", "--detach"],
            cwd=self.repo_path,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "branch", "-f", "main", "origin/main"],
            cwd=self.repo_path,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "checkout", "main"],
            cwd=self.repo_path,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "remote", "set-head", "origin", "main"],
            cwd=self.repo_path,
            check=True,
            capture_output=True,
        )
        tasks_clone_path = os.path.join(self.repo_path, ".tasks")
        if os.path.exists(tasks_clone_path):
            shutil.rmtree(tasks_clone_path)
        self.script_path = os.path.join(self.repo_path, "hammer")
        if os.path.exists(self.dev_tasks_dir):
            shutil.rmtree(self.dev_tasks_dir)
        os.makedirs(self.dev_tasks_dir, exist_ok=True)
        tasks_dir = os.path.join(self.repo_path, ".tasks")
        os.makedirs(tasks_dir, exist_ok=True)
        with open(os.path.join(tasks_dir, "config.yaml"), "w") as f:
            json.dump({}, f)
        subprocess.run(
            [self.script_path, "tasks", "--dev", "init", "--force"],
            cwd=self.repo_path,
            check=True,
            capture_output=True,
        )
        ops_path = os.path.join(self.dev_tasks_dir, ".ops")
        if os.path.exists(ops_path):
            shutil.rmtree(ops_path)
        config_data = {
            "repo": {
                "lint": "ruff",
                "test": "noop",
                "type_check": "noop",
                "format": "ruff",
            }
        }
        with open(os.path.join(self.dev_tasks_dir, "config.yaml"), "w") as f:
            json.dump(config_data, f)

    def run_tasks(self, args):
        if len(args) > 2 and args[0] == "move" and "READY" in args[2].split(","):
            for task_ref in args[1].split(","):
                self._run_tasks(
                    [
                        "modify",
                        task_ref,
                        "--research",
                        "Read the relevant pipeline implementation and regression tests.",
                    ]
                )
        return self._run_tasks(args)

    def _run_tasks(self, args):
        return subprocess.run(
            [self.script_path, "tasks", "-j", "--dev"] + args,
            cwd=self.repo_path,
            capture_output=True,
            text=True,
            check=False,
        )

    def seed_counter(self, value):
        """Force the next task id, so fixtures never collide with real branches.

        The fixture clones this repo and therefore inherits its branches. A task
        created at a real id would be a genuine duplicate-in-branches violation
        and the guard correctly rejects it; tests that do not pin an id must
        stay above the highest real task id (see tests/test_guard.py BASE_ID).
        """
        counter = os.path.join(self.dev_tasks_dir, ".task_counter")
        if os.path.exists(counter):
            os.remove(counter)
        with open(counter, "w") as handle:
            handle.write(str(value))
