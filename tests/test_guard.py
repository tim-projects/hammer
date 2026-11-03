#!/usr/bin/env python3
"""User tests for `hammer guard` (task 247/248).

Guard is the prevention counterpart of `doctor`: duplicate task IDs must never
pass a pipeline gate. These tests use the standard hammer fixture repo
(HammerTestBase) and drive the tool the way a user does: through the hammer
CLI and the guard CLI.
"""

import json
import os
import subprocess
import tempfile
import time
import unittest

from tests.hammer_test_base import HammerTestBase

STORY = "Sufficiently long story content here to pass validation"
TECH = "Sufficiently long technical description here to pass validation"
CRITERIA = "Sufficiently long acceptance criteria here to pass validation"
PLAN = "Sufficiently long planning details here to pass validation"
TITLE = "Comprehensive Guard Verification Task"


class GuardTestBase(HammerTestBase):

    def run_guard(self, args, cwd=None):
        return subprocess.run(  # noqa: PLW1510
            ["python3", os.path.join(self.repo_path, "guard.py")] + args,
            cwd=cwd or self.repo_path,
            capture_output=True,
            text=True,
            check=False,
        )

    def git(self, args, cwd=None):
        return subprocess.run(  # noqa: PLW1510
            ["git"] + args,
            cwd=cwd or self.repo_path,
            capture_output=True,
            text=True,
            check=False,
        )

    def seed_counter(self, value):
        with open(os.path.join(self.dev_tasks_dir, ".task_counter"), "w") as handle:
            handle.write(str(value))

    def create_task(self, counter_value=None, title=TITLE):
        """Create a task with a predictable Id (counter -> counter + 1)."""
        if counter_value is not None:
            self.seed_counter(counter_value)
        result = self.run_tasks(
            [
                "create",
                title,
                "--story",
                STORY,
                "--tech",
                TECH,
                "--criteria",
                CRITERIA,
                "--plan",
                PLAN,
            ]
        )
        self.assertEqual(
            result.returncode, 0, f"create failed: {result.stdout} {result.stderr}"
        )
        task_id = int(counter_value) + 1 if counter_value is not None else None
        return self._find_folder(task_id, "backlog")

    def _find_folder(self, task_id, state):
        state_dir = os.path.join(self.dev_tasks_dir, state)
        for name in sorted(os.listdir(state_dir)):
            if task_id is None or name.startswith(f"{task_id}-"):
                return name
        return None

    @property
    def guard_db(self):
        return os.path.join(self.repo_path, ".git", "hammer-guard", "guard.db")

    def scan_json(self):
        result = self.run_guard(["scan", "--json", "--dev"])
        self.assertEqual(result.returncode, 0, f"scan failed: {result.stderr}")
        return json.loads(result.stdout)


class TestGuardScan(GuardTestBase):
    """Read-only reporting: the triage list, not a wall."""

    def test_scan_reports_duplicate_id(self):
        self.git(["branch", "178-task-alpha"])
        self.git(["branch", "178-issue-beta"])
        data = self.scan_json()
        duplicates = [
            a
            for a in data["anomalies"]
            if a["code"] == "GUARD_DUPLICATE_ID" and a["task_id"] == 178
        ]
        self.assertEqual(len(duplicates), 1, f"expected one duplicate, got {data}")
        self.assertIn("178-task-alpha", duplicates[0]["detail"])
        self.assertIn("178-issue-beta", duplicates[0]["detail"])

    def test_scan_never_mutates_tasks(self):
        before = sorted(os.listdir(os.path.join(self.dev_tasks_dir, "backlog")))
        self.git(["branch", "178-task-alpha"])
        self.git(["branch", "178-issue-beta"])
        self.scan_json()
        after = sorted(os.listdir(os.path.join(self.dev_tasks_dir, "backlog")))
        self.assertEqual(before, after)

    def test_rebuild_is_deterministic(self):
        self.git(["branch", "178-task-alpha"])
        self.git(["branch", "178-issue-beta"])
        first = self.run_guard(["rebuild", "--json", "--dev"])
        second = self.run_guard(["rebuild", "--json", "--dev"])
        self.assertEqual(first.returncode, 0, first.stderr)
        self.assertEqual(
            json.loads(first.stdout)["anomalies"], json.loads(second.stdout)["anomalies"]
        )

    def test_adding_a_branch_changes_exactly_one_verdict(self):
        folder = self.create_task(counter_value=177)
        task_id = 178
        base = {
            (a["code"], a["task_id"]) for a in self.scan_json()["anomalies"]
        }
        self.git(["branch", f"{task_id}-issue-collision"])
        after = {(a["code"], a["task_id"]) for a in self.scan_json()["anomalies"]}
        self.assertEqual(after - base, {("GUARD_DUPLICATE_ID", task_id)})
        self.assertEqual(base - after, set())
        self.assertTrue(folder.startswith("178-"))


class TestGuardGate(GuardTestBase):
    """The gate: a duplicate ID must never progress."""

    def test_duplicate_id_cannot_pass_gate(self):
        folder = self.create_task(counter_value=177)
        self.git(["branch", "178-issue-collision"])
        result = self.run_tasks(["move", "178", "READY"])
        self.assertEqual(result.returncode, 1, f"expected rejection: {result.stdout}")
        payload = json.loads(result.stdout)
        self.assertIn("GUARD", payload["error"])
        self.assertIn("duplicate", payload["error"].lower())
        # the task folder did not move
        self.assertTrue(
            os.path.isdir(os.path.join(self.dev_tasks_dir, "backlog", folder))
        )
        self.assertFalse(
            os.path.isdir(os.path.join(self.dev_tasks_dir, "ready", folder))
        )

    def test_state_duplicate_is_rejected(self):
        folder = self.create_task(counter_value=177)
        src = os.path.join(self.dev_tasks_dir, "backlog", folder)
        dst = os.path.join(self.dev_tasks_dir, "progressing", folder)
        subprocess.run(["cp", "-r", src, dst], check=True)  # noqa: PLW1510
        result = self.run_tasks(["move", "178", "READY"])
        self.assertEqual(result.returncode, 1, f"expected rejection: {result.stdout}")
        self.assertIn("GUARD", json.loads(result.stdout)["error"])
        self.assertTrue(os.path.isdir(src))
        self.assertTrue(os.path.isdir(dst))

    def test_force_overrides_and_is_recorded(self):
        folder = self.create_task(counter_value=177)
        self.git(["branch", "178-issue-collision"])
        forced = self.run_tasks(["move", "178", "READY", "--force"])
        self.assertEqual(forced.returncode, 0, f"force move failed: {forced.stdout}")
        # the bypass is never silent: it lands in the event log
        data = self.scan_json()
        bypasses = [
            e
            for e in data["events"]
            if e["code"] == "GUARD_DUPLICATE_ID" and e["task_id"] == 178
        ]
        self.assertTrue(bypasses, f"forced bypass not recorded: {data['events']}")
        self.assertIn("forced", bypasses[0]["detail"].lower())
        self.assertTrue(os.path.isdir(os.path.join(self.dev_tasks_dir, "ready", folder)))

    def test_clean_task_passes_gates(self):
        folder = self.create_task(counter_value=177)
        for target in ("READY", "PROGRESSING"):
            result = self.run_tasks(["move", "178", target])
            self.assertEqual(
                result.returncode,
                0,
                f"clean task blocked at {target}: {result.stdout} {result.stderr}",
            )
        self.assertTrue(
            os.path.isdir(os.path.join(self.dev_tasks_dir, "progressing", folder))
        )

    def test_remote_duplicate_warns_but_does_not_block(self):
        self.create_task(counter_value=177)
        head = self.git(["rev-parse", "HEAD"]).stdout.strip()
        self.git(["update-ref", "refs/remotes/origin/178-remote-a", head])
        self.git(["update-ref", "refs/remotes/origin/178-remote-b", head])
        result = self.run_tasks(["move", "178", "READY"])
        self.assertEqual(result.returncode, 0, f"remote WARN blocked move: {result.stdout}")
        codes = {a["code"] for a in self.scan_json()["anomalies"]}
        self.assertIn("GUARD_DUPLICATE_REMOTE_ID", codes)


class TestGuardCache(GuardTestBase):
    """The cache is disposable: corruption self-heals, loss is loud."""

    def test_corrupt_cache_self_heals(self):
        self.create_task(counter_value=177)
        self.assertTrue(
            self.run_guard(["scan", "--dev"]).returncode == 0,
            "scan should create the cache",
        )
        self.assertTrue(os.path.exists(self.guard_db))
        with open(self.guard_db, "wb") as handle:
            handle.write(b"this is not a sqlite database at all")
        result = self.run_guard(["check", "178", "--to", "TESTING", "--dev"])
        self.assertEqual(result.returncode, 0, f"self-heal failed: {result.stderr}")
        self.assertFalse(b"this is not" in open(self.guard_db, "rb").read())

    def test_unwritable_cache_rejects_with_actionable_message(self):
        folder = self.create_task(counter_value=177)
        cache_dir = os.path.dirname(self.guard_db)
        os.makedirs(cache_dir, exist_ok=True)
        if os.path.isfile(self.guard_db):
            os.remove(self.guard_db)
        os.makedirs(self.guard_db, exist_ok=True)  # a directory where the db belongs
        result = self.run_guard(["check", "178", "--to", "TESTING", "--dev"])
        self.assertEqual(result.returncode, 1, "guard must fail closed")
        self.assertIn("GUARD_UNAVAILABLE", result.stderr)
        self.assertIn("guard rebuild", result.stderr)
        self.assertIn("--force", result.stderr)
        # the pipeline gate rejects the same way and leaves the task in place
        moved = self.run_tasks(["move", "178", "READY"])
        self.assertEqual(moved.returncode, 1, f"gate must reject: {moved.stdout}")
        self.assertIn("GUARD", json.loads(moved.stdout)["error"])
        self.assertTrue(os.path.isdir(os.path.join(self.dev_tasks_dir, "backlog", folder)))

    def test_total_ref_loss_is_not_an_empty_repo(self):
        with tempfile.TemporaryDirectory() as tmp:
            for args in (
                ["init", "-b", "main"],
                ["config", "user.email", "test@example.com"],
                ["config", "user.name", "Test"],
            ):
                self.git(args, cwd=tmp)
            with open(os.path.join(tmp, "README.md"), "w") as handle:
                handle.write("x")
            self.git(["add", "."], cwd=tmp)
            self.git(["commit", "-m", "init"], cwd=tmp)

            from tasks_ai.guard_engine import GuardEngine, GuardUnavailable

            GuardEngine(repo_root=tmp, tasks_path=None).scan()
            self.git(["checkout", "--detach"], cwd=tmp)
            self.git(["branch", "-D", "main"], cwd=tmp)

            with self.assertRaises(GuardUnavailable) as caught:
                GuardEngine(repo_root=tmp, tasks_path=None).scan()
            self.assertIn("total ref loss", str(caught.exception))

    def test_cache_survives_in_common_dir_from_worktree(self):
        self.create_task(counter_value=177)
        worktrees = os.path.join(self.repo_path, ".task-worktrees")
        branch = self._find_folder(178, "backlog")
        worktree_path = os.path.join(worktrees, branch)
        self.assertTrue(os.path.isdir(worktree_path), f"no worktree for {branch}")
        self.git(["branch", "178-issue-collision"])
        root = self.run_guard(["check", "178", "--dev"])
        inner = self.run_guard(["check", "178", "--dev"], cwd=worktree_path)
        self.assertEqual(root.returncode, inner.returncode)
        self.assertEqual(root.stdout, inner.stdout)
        self.assertNotEqual(root.returncode, 0)  # duplicate still detected inside wt

    def test_duplicate_worktree_for_one_task_is_reported(self):
        self.create_task(counter_value=177)
        second = os.path.join(self.repo_path, ".task-worktrees", "178-issue-second")
        self.git(["worktree", "add", second, "-b", "178-issue-second"])
        codes = {a["code"] for a in self.scan_json()["anomalies"]}
        self.assertIn("GUARD_WORKTREE_ORPHAN", codes)

    def test_verdict_is_fast_enough_for_a_gate(self):
        from tasks_ai.guard_engine import GuardEngine

        self.create_task(counter_value=177)
        engine = GuardEngine(
            repo_root=self.repo_path,
            tasks_path=self.dev_tasks_dir,
            dev=True,
            cwd=self.repo_path,
        )
        start = time.monotonic()
        engine.verdict(178, "BACKLOG", "READY", "178-task-comprehensive-guard-veri")
        elapsed = time.monotonic() - start
        self.assertLess(elapsed, 1.0, f"guard verdict took {elapsed:.2f}s")


class TestGuardIntegration(GuardTestBase):
    """Git hooks and the hammer dispatcher."""

    def test_hooks_install_into_common_dir_from_worktree(self):
        self.create_task(counter_value=177)
        branch = self._find_folder(178, "backlog")
        worktree_path = os.path.join(self.repo_path, ".task-worktrees", branch)
        result = subprocess.run(  # noqa: PLW1510
            ["python3", os.path.join(self.repo_path, "hammer"), "tasks", "--dev", "init-hooks"],
            cwd=worktree_path,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        # .git is a file inside a worktree: hooks must land in the COMMON dir
        self.assertTrue(os.path.isfile(os.path.join(worktree_path, ".git")))
        self.assertTrue(
            os.path.isfile(os.path.join(self.repo_path, ".git", "hooks", "pre-commit"))
        )

    def test_guard_cli_is_reachable_via_hammer(self):
        result = subprocess.run(  # noqa: PLW1510
            ["python3", os.path.join(self.repo_path, "hammer"), "guard", "scan", "--dev"],
            cwd=self.repo_path,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_guard_hooks_install_writes_wrappers(self):
        result = self.run_guard(["hooks", "--install"])
        self.assertEqual(result.returncode, 0, result.stderr)
        hook = os.path.join(self.repo_path, ".git", "hooks", "pre-commit")
        self.assertTrue(os.path.isfile(hook))
        with open(hook) as handle:
            self.assertIn("guard check --branch", handle.read())


if __name__ == "__main__":
    unittest.main()
