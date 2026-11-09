"""User tests for the worktree-based task management system (task 87).

Runs without --dev so the production path is exercised: validate_path only
short-circuits in dev mode, which is why the dev-based tests never caught the
"Path outside repository" failure when resolving task paths from inside a
worktree (task metadata lives in the main repo's .tasks/, not the worktree).
"""
import json
import os
import shutil
import subprocess
import tempfile
import unittest


def git(args, cwd, check=False):
    return subprocess.run(
        ["git"] + args, cwd=cwd, capture_output=True, text=True, check=check
    )


def _make_test_root():
    """Create the test repo outside /tmp.

    validate_path short-circuits for any path starting with /tmp, so a repo under
    /tmp would silently skip the production path this file guards. Skip the whole
    module rather than pass without exercising the real code.
    """
    try:
        return tempfile.mkdtemp(prefix="worktree_test_", dir="/var/tmp")
    except OSError as exc:
        raise unittest.SkipTest(f"no writable non-/tmp temp dir (/var/tmp): {exc}")


class TestWorktreeSystem(unittest.TestCase):
    def setUp(self):
        self.test_dir = _make_test_root()
        self.repo_dir = os.path.join(self.test_dir, "repo")
        os.makedirs(self.repo_dir)
        git(["init"], self.repo_dir)
        git(["branch", "-m", "master", "main"], self.repo_dir)
        git(["config", "user.email", "test@example.com"], self.repo_dir)
        git(["config", "user.name", "Test User"], self.repo_dir)
        git(["config", "commit.gpgsign", "false"], self.repo_dir)
        with open(os.path.join(self.repo_dir, "README.md"), "w") as f:
            f.write("# Worktree Test Repo")
        git(["add", "README.md"], self.repo_dir)
        git(["commit", "-m", "Initial commit"], self.repo_dir)

        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.script_path = os.path.abspath(os.path.join(self.repo_dir, "hammer"))
        os.symlink(os.path.join(project_root, "hammer"), self.script_path)
        git(["add", "hammer"], self.repo_dir)
        git(["commit", "-m", "Add hammer"], self.repo_dir)

        # .tasks/config.yaml marks the repo as initialized; all checks are no-ops
        tasks_dir = os.path.join(self.repo_dir, ".tasks")
        os.makedirs(tasks_dir, exist_ok=True)
        with open(os.path.join(tasks_dir, "config.yaml"), "w") as f:
            json.dump(
                {
                    "repo": {
                        "lint": "/bin/true",
                        "test": "/bin/true",
                        "type_check": "/bin/true",
                        "format": "/bin/true",
                        "skip_push": True,
                    }
                },
                f,
            )

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def run_cmd(self, args, cwd=None):
        result = subprocess.run(  # noqa: PLW1510
            [self.script_path, "tasks", "-j"] + args,
            cwd=cwd or self.repo_dir,
            capture_output=True,
            text=True,
        )
        try:
            return json.loads(result.stdout)
        except json.JSONDecodeError:
            return {
                "success": False,
                "error": "JSON Decode Error",
                "stdout": result.stdout,
                "stderr": result.stderr,
            }

    def create_task(self, title="Worktree System Under Verification"):
        res = self.run_cmd(
            [
                "create",
                title,
                "--story",
                "As a developer I want a dedicated worktree per task so work stays isolated.",
                "--tech",
                "Verifies WorktreeManager create/list/remove, manifest persistence and mount.",
                "--criteria",
                "Worktree exists for the task and manifest entry is persisted.",
                "--plan",
                "1. Create task. 2. Verify worktree and manifest. 3. Move through states.",
                "--repro",
                "Run tasks create then inspect .task-worktrees and .tasks/worktrees.json.",
            ]
        )
        self.assertTrue(res["success"], f"create failed: {res}")
        return res["data"]

    def complete_criteria(self, task_file):
        """Mark criteria done in whatever state folder currently holds the task."""
        for state in (
            "backlog",
            "ready",
            "progressing",
            "testing",
            "review",
            "staging",
            "done",
            "archived",
        ):
            criteria = os.path.join(self.repo_dir, ".tasks", state, task_file, "criteria.md")
            if os.path.exists(criteria):
                with open(criteria) as f:
                    content = f.read()
                with open(criteria, "w") as f:
                    f.write(content.replace("- [ ]", "- [x]"))

    def manifest(self):
        with open(os.path.join(self.repo_dir, ".tasks", "worktrees.json")) as f:
            return json.load(f)["worktrees"]

    def test_worktree_created_with_manifest_entry(self):
        """Creating a task creates a worktree and records it in the manifest."""
        data = self.create_task()
        task_id = str(data["id"])
        worktree_path = data.get("worktree")
        self.assertTrue(worktree_path, f"no worktree returned: {data}")
        self.assertTrue(os.path.isdir(worktree_path), f"worktree dir missing: {worktree_path}")

        entry = self.manifest().get(task_id)
        self.assertIsNotNone(entry, f"manifest has no entry for {task_id}: {self.manifest()}")
        self.assertEqual(entry["path"], worktree_path)
        self.assertEqual(entry["branch"], data["branch"])

        # The worktree is a real git worktree on the task branch
        listing = git(["worktree", "list"], self.repo_dir).stdout
        self.assertIn(worktree_path, listing)
        self.assertEqual(
            git(["rev-parse", "--abbrev-ref", "HEAD"], worktree_path).stdout.strip(),
            data["branch"],
        )

    def test_task_operations_resolve_from_inside_worktree(self):
        """Regression test: task ops must resolve .tasks/ paths from a task worktree.

        validate_path only allowed cli.root, but task metadata lives in the main
        repo's .tasks/, so find_task returned nothing and every command that
        resolves a task failed with "Path outside repository".
        """
        data = self.create_task()
        worktree_path = data["worktree"]

        for args in (["show", str(data["id"])], ["list"]):
            res = self.run_cmd(args, cwd=worktree_path)
            self.assertTrue(res["success"], f"{args} failed from inside worktree: {res}")

        # mount also resolves and reports the worktree path
        res = self.run_cmd(["mount", str(data["id"])], cwd=worktree_path)
        self.assertTrue(res["success"], f"mount failed from inside worktree: {res}")

        # Pipeline gates enforce correctly when the transition is driven from
        # inside the worktree (MainBranchProtectionHook sees the task branch)
        res = self.run_cmd(["move", data["file"], "READY"], cwd=worktree_path)
        self.assertTrue(res["success"], f"move READY from inside worktree failed: {res}")

        # ...and the same commands still work from the main repo
        res = self.run_cmd(["show", str(data["id"])], cwd=self.repo_dir)
        self.assertTrue(res["success"], f"show failed from main repo: {res}")

    def test_mount_recreates_removed_worktree(self):
        """tasks mount recreates a worktree that was removed."""
        data = self.create_task()
        worktree_path = data["worktree"]
        git(["worktree", "remove", worktree_path], self.repo_dir)
        self.assertFalse(os.path.exists(worktree_path))

        res = self.run_cmd(["mount", str(data["id"])])
        self.assertTrue(res["success"], f"mount failed: {res}")
        self.assertEqual(res["data"]["worktree_path"], worktree_path)
        self.assertTrue(os.path.isdir(worktree_path))

    def test_worktree_removed_on_archived(self):
        """Archiving a task removes its worktree, git registration and manifest entry."""
        data = self.create_task()
        task_id = str(data["id"])
        task_file = data["file"]
        worktree_path = data["worktree"]
        self.assertTrue(os.path.isdir(worktree_path))

        self.run_cmd(["move", task_file, "READY"])
        res = self.run_cmd(["move", task_file, "PROGRESSING"])
        self.assertTrue(res["success"], f"move PROGRESSING failed: {res}")

        # Commit real work on the task branch from inside the worktree
        with open(os.path.join(worktree_path, "feature.py"), "w") as f:
            f.write("def feature():\n    return True\n")
        git(["add", "feature.py"], worktree_path)
        git(["commit", "-m", "Add feature"], worktree_path)

        self.complete_criteria(task_file)
        res = self.run_cmd(["move", task_file, "TESTING"])
        self.assertTrue(res["success"], f"move TESTING failed: {res}")

        # Merge the task branch into main so the archive merge guard passes
        git(["checkout", "main"], self.repo_dir)
        git(["merge", data["branch"]], self.repo_dir, check=True)

        self.complete_criteria(task_file)
        res = self.run_cmd(["move", task_file, "REVIEW"])
        self.assertTrue(res["success"], f"move REVIEW failed: {res}")

        # Mandatory review gate: audit, verify, per-patch review, summary, regression-check
        while True:
            res = self.run_cmd(["review", task_file])
            self.assertTrue(res["success"], f"review failed: {res}")
            if not res["data"]["remaining"]:
                break
        for args in (
            ["modify", task_file, "--reviewed", "Read every patch: the fix is scoped and the tests cover it."],
            ["audit", task_file],
            ["verify", task_file, "--proof", "Reviewed patches and criteria."],
            ["modify", task_file, "--regression-check"],
        ):
            res = self.run_cmd(args)
            self.assertTrue(res["success"], f"{args} failed: {res}")

        for state in ("STAGING", "DONE"):
            self.complete_criteria(task_file)
            res = self.run_cmd(["move", task_file, state])
            self.assertTrue(res["success"], f"move {state} failed: {res}")

        res = self.run_cmd(["move", task_file, "ARCHIVED", "-y"])
        self.assertTrue(res["success"], f"move ARCHIVED failed: {res}")

        # Worktree, its git registration and its manifest entry are all gone
        self.assertFalse(
            os.path.exists(worktree_path), f"worktree still on disk: {worktree_path}"
        )
        self.assertNotIn(worktree_path, git(["worktree", "list"], self.repo_dir).stdout)
        self.assertNotIn(task_id, self.manifest())


if __name__ == "__main__":
    unittest.main()
