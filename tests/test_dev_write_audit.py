"""Dev mode must not write outside its two roots (task 364).

Invariant: every path a --dev workflow creates or modifies lies under
<HAMMER_DEV_TASKS_DIR> (the store) or <store>-repo (the throwaway repo).
Production - the repo the command was invoked from, and its remote - is
read-only in dev mode.

This is the standing regression guard for the invariant: a full dev workflow
runs, and the invoked repo must be byte-identical afterwards, the store must
never be wired to the invoked repo's remote, and system-level commands are
refused.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

STORY = "Sufficiently long story content here to pass validation"
TECH = "Sufficiently long technical description here to pass validation"
ACCEPT = "Sufficiently long acceptance criteria here to pass validation"
PLAN = "Sufficiently long planning details here to pass validation"


class TestDevWriteAudit(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="hammer_dev_audit_")
        self.prod = os.path.join(self.test_dir, "prod")
        os.makedirs(self.prod)
        for args in (["init"], ["config", "user.email", "test@example.com"],
                     ["config", "user.name", "Test User"]):
            subprocess.run(["git"] + args, cwd=self.prod, capture_output=True)  # noqa: PLW1510
        with open(os.path.join(self.prod, "README.md"), "w") as handle:
            handle.write("# Production stand-in\n")
        for args in (["add", "README.md"], ["commit", "-m", "initial"]):
            subprocess.run(["git"] + args, cwd=self.prod, capture_output=True)  # noqa: PLW1510
        # The dev store is cloned from the invoked repo's 'tasks' branch, so the
        # stand-in needs one, exactly like every real repo has.
        subprocess.run(["git", "checkout", "--orphan", "tasks"], cwd=self.prod, capture_output=True)  # noqa: PLW1510
        with open(os.path.join(self.prod, "config.yaml"), "w") as handle:
            handle.write("{}\n")
        for args in (["add", "config.yaml"], ["commit", "-m", "store seed"]):
            subprocess.run(["git"] + args, cwd=self.prod, capture_output=True)  # noqa: PLW1510
        subprocess.run(["git", "checkout", "main"], cwd=self.prod, capture_output=True)  # noqa: PLW1510
        self.store = os.path.join(self.test_dir, "store", ".tasks")
        self.dev_repo = self.store + "-repo"
        self.env = dict(os.environ, HAMMER_DEV_TASKS_DIR=self.store)
        self.script_path = os.path.join(PROJECT_ROOT, "hammer")

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def git(self, *args, cwd=None):
        return subprocess.run(  # noqa: PLW1510
            ["git"] + list(args), cwd=cwd or self.prod, capture_output=True, text=True
        )

    def run_dev(self, args, tool="tasks"):
        return subprocess.run(  # noqa: PLW1510
            [self.script_path, tool, "-j", "--dev"] + args,
            cwd=self.prod, env=self.env, capture_output=True, text=True,
        )

    def payload(self, result):
        try:
            return json.loads(result.stdout)
        except json.JSONDecodeError:
            return {"success": False, "stdout": result.stdout, "stderr": result.stderr}

    def snapshot_prod(self):
        """Every observable production state a stray write would change."""
        def git(*args):
            out = self.git(*args)
            return "\n".join(sorted(out.stdout.splitlines()))

        return {
            "worktrees": git("worktree", "list"),
            "branches": git("branch", "--list"),
            "refs": git("show-ref"),
            "status": git("status", "--porcelain"),
            "log": git("log", "--all", "--oneline"),
        }

    def make_task(self, title):
        res = self.payload(self.run_dev([
            "create", title, "--story", STORY, "--tech", TECH,
            "--criteria", ACCEPT, "--plan", PLAN,
        ]))
        self.assertTrue(res["success"], res)
        return res["data"]["id"], res["data"]["file"]

    def test_full_dev_workflow_writes_nothing_outside_the_dev_roots(self):
        before = self.snapshot_prod()
        # 'init' needs --force: the CLI pre-creates the store directory before
        # checking it (task 356); an empty fresh dir still initializes then.
        self.assertTrue(self.payload(self.run_dev(["init", "--force"]))["success"])

        id_a, file_a = self.make_task("Alpha dev audit task")
        id_b, file_b = self.make_task("Beta dev audit task")
        for state in ("READY", "PROGRESSING"):
            for task_file in (file_a, file_b):
                self.assertTrue(self.payload(self.run_dev(["move", task_file, state]))["success"])
        self.assertTrue(self.payload(self.run_dev(["mount", str(id_a)]))["success"])
        self.assertTrue(self.payload(self.run_dev(["checkpoint", str(id_a)]))["success"])
        self.assertTrue(self.payload(self.run_dev(["link", str(id_a), str(id_b)]))["success"])
        self.assertTrue(self.payload(self.run_dev(["unlink", str(id_a), str(id_b)]))["success"])
        self.payload(self.run_dev(["save", "-y"]))
        self.payload(self.run_dev(["undo", str(id_a)]))
        self.payload(self.run_dev(["doctor"]))
        self.payload(self.run_dev(["guard", "scan"], tool="guard"))

        self.assertEqual(before, self.snapshot_prod(),
                         "a --dev workflow must leave the invoked repo untouched")

    def test_dev_save_never_wires_the_store_to_the_production_remote(self):
        self.assertTrue(self.payload(self.run_dev(["init", "--force"]))["success"])
        self.make_task("Alpha dev remote probe task")
        self.payload(self.run_dev(["save", "-y"]))
        origin = self.git("remote", "get-url", "origin", cwd=self.store)
        wired = origin.returncode == 0 and origin.stdout.strip()
        self.assertFalse(
            wired and os.path.realpath(wired) == os.path.realpath(self.prod),
            f"the dev store must not be wired to the production repo's remote: {wired}",
        )

    def test_dev_upgrade_is_refused(self):
        refused = self.payload(self.run_dev(["upgrade"]))
        self.assertFalse(refused["success"], refused)
        self.assertIn("blocked a write to production", refused.get("error", ""),
                      "upgrade installs into the live installation and must be blocked")

    def test_dev_artifacts_live_under_the_dev_roots(self):
        self.assertTrue(self.payload(self.run_dev(["init", "--force"]))["success"])
        _, file_a = self.make_task("Alpha dev roots probe task")
        moved = self.payload(self.run_dev(["move", file_a, "READY"]))
        self.assertTrue(moved["success"], moved)
        moved = self.payload(self.run_dev(["move", file_a, "PROGRESSING"]))
        self.assertTrue(moved["success"], moved)
        with open(os.path.join(self.store, "worktrees.json")) as handle:
            paths = [entry["path"] for entry in json.load(handle)["worktrees"].values()]
        self.assertTrue(paths, "the task must have a worktree")
        for path in paths:
            self.assertTrue(
                os.path.commonpath([os.path.realpath(path), os.path.realpath(self.dev_repo)])
                == os.path.realpath(self.dev_repo),
                f"worktree {path} must live in the throwaway repo",
            )
