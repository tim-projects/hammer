import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from types import SimpleNamespace

from tasks_ai.approval import approval_is_current, approval_patch_dir
from tasks_ai.git_service import GitService
from tasks_ai.pipeline import PipelineError, PipelineService


def git(*args, cwd, check=True):
    result = subprocess.run(
        ["git", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
    )
    if check and result.returncode:
        raise AssertionError(f"git {' '.join(args)} failed: {result.stderr}")
    return result


class FakeWorktrees:
    def __init__(self, path):
        self.path = path

    def get_worktree_path(self, task_id):
        return self.path


class FakeCLI:
    def __init__(self, git_service, tasks_path):
        self.git = git_service
        self.context = SimpleNamespace(
            repo_root=git_service.context.main_repo_root,
            main_repo_root=git_service.context.main_repo_root,
        )
        self.tasks_path = tasks_path
        self.validations = []
        self.writes = []

    def run_tool(self, tool_name=None, fix=False, cwd=None):
        self.validations.append((tool_name, cwd))

    def _atomic_write(self, path, task):
        self.writes.append((path, dict(task.metadata)))
        with open(os.path.join(path, "meta.json"), "w", encoding="utf-8") as handle:
            json.dump(task.metadata, handle)


class PRMergeViabilityTest(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="pr_merge_viability_")
        self.repo = os.path.join(self.root, "repo")
        self.tasks = os.path.join(self.repo, ".tasks")
        os.makedirs(self.repo)
        git("init", "-b", "main", cwd=self.repo)
        git("config", "user.email", "test@example.com", cwd=self.repo)
        git("config", "user.name", "Test User", cwd=self.repo)
        self.write("base.txt", "base\n")
        git("add", "base.txt", cwd=self.repo)
        git("commit", "-m", "base", cwd=self.repo)
        base = git("rev-parse", "main", cwd=self.repo).stdout.strip()
        git("update-ref", "refs/remotes/origin/main", base, cwd=self.repo)
        context = SimpleNamespace(
            repo_root=self.repo,
            main_repo_root=self.repo,
            dev=False,
        )
        self.git = GitService(context)
        self.git._worktree_manager = FakeWorktrees(self.repo)
        self.cli = FakeCLI(self.git, self.tasks)

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def write(self, name, content):
        with open(os.path.join(self.repo, name), "w", encoding="utf-8") as handle:
            handle.write(content)

    def make_task(self, task_id="9001"):
        path = os.path.join(self.tasks, "pr", f"{task_id}-task-test")
        os.makedirs(path, exist_ok=True)
        metadata = {
            "Id": int(task_id),
            "Ti": "PR merge viability test",
            "St": "PR",
            "Br": f"{task_id}-task-test",
        }
        with open(os.path.join(path, "meta.json"), "w", encoding="utf-8") as handle:
            json.dump(metadata, handle)
        return path, metadata

    def test_merge_tree_reports_conflict_paths_without_creating_a_commit(self):
        git("branch", "pr", cwd=self.repo)
        git("checkout", "pr", cwd=self.repo)
        self.write("conflict.txt", "pr\n")
        git("add", "conflict.txt", cwd=self.repo)
        git("commit", "-m", "pr change", cwd=self.repo)
        git("checkout", "main", cwd=self.repo)
        git("branch", "provisioning", cwd=self.repo)
        git("checkout", "provisioning", cwd=self.repo)
        self.write("conflict.txt", "provisioning\n")
        git("add", "conflict.txt", cwd=self.repo)
        git("commit", "-m", "provisioning change", cwd=self.repo)
        before = git("rev-parse", "provisioning", cwd=self.repo).stdout.strip()

        conflicts = self.git.merge_tree_conflicts("pr", "provisioning")

        self.assertEqual(["conflict.txt"], conflicts)
        self.assertEqual(
            before,
            git("rev-parse", "provisioning", cwd=self.repo).stdout.strip(),
        )

    def test_stale_validation_base_reruns_validation_and_refreshes_base(self):
        git("branch", "9001-PR", cwd=self.repo)
        git("branch", "provisioning", cwd=self.repo)
        task_path, metadata = self.make_task()
        metadata.update({"Tp": True, "TpBase": "stale"})
        with open(
            os.path.join(task_path, "meta.json"), "w", encoding="utf-8"
        ) as handle:
            json.dump(metadata, handle)

        pipeline = PipelineService(self.git, logger=self.cli)
        with self.assertRaises(PipelineError) as raised:
            pipeline.validate_pr_exit(
                self.cli, SimpleNamespace(metadata=metadata), task_path
            )

        self.assertEqual("PR_APPROVAL_REQUIRED", raised.exception.code)
        self.assertEqual(
            [("all", self.git.worktrees.get_worktree_path("9001"))],
            self.cli.validations,
        )
        self.assertEqual(
            git("rev-parse", "origin/main", cwd=self.repo).stdout.strip(),
            metadata["TpBase"],
        )

    def test_edited_patch_invalidates_approval(self):
        task_path, metadata = self.make_task()
        patches_dir = approval_patch_dir(self.cli, task_path)
        os.makedirs(patches_dir, exist_ok=True)
        patch_path = os.path.join(patches_dir, "base.txt.patch")
        with open(patch_path, "wb") as handle:
            handle.write(b"approved content\n")
        metadata.update(
            {
                "Ap": "APPROVED",
                "ApMd5": {
                    "base.txt.patch": hashlib.md5(b"approved content\n").hexdigest()
                },
                "ApBase": git("rev-parse", "main", cwd=self.repo).stdout.strip(),
            }
        )
        task = SimpleNamespace(metadata=metadata)
        with open(patch_path, "wb") as handle:
            handle.write(b"edited content\n")

        self.assertFalse(approval_is_current(self.cli, task, patches_dir))


if __name__ == "__main__":
    unittest.main()
