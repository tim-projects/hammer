#!/usr/bin/env python3
"""User tests for `hammer guard` (task 247/248).

Guard is the prevention counterpart of `doctor`: duplicate task IDs must never
pass a pipeline gate. These tests use the standard hammer fixture repo
(HammerTestBase) and drive the tool the way a user does: through the hammer
CLI and the guard CLI.

Fixture notes: the harness clones the repo then checks out `main`, so files
that exist only on the task branch are absent from the fixture working tree.
`_install_guard_into_fixture` copies them in after setUp. The fixture also
inherits the real `tasks` branch content, so created tasks use a high, unused
counter value to avoid colliding with real task ids.
"""

import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tests.hammer_test_base import HammerTestBase  # noqa: E402


def load_guard_engine():
    """Import the engine from THIS repo (not a fixture clone).

    Other test modules import `tasks_ai` from fixture clones, which can leave a
    stale entry in `sys.modules`. Load `tasks_ai` from this repo explicitly.
    """
    import importlib

    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    for name in [
        n for n in sys.modules if n == "tasks_ai" or n.startswith("tasks_ai.")
    ]:
        paths = list(getattr(sys.modules[name], "__path__", []))
        if not paths or not str(paths[0]).startswith(root):
            del sys.modules[name]
    if root not in sys.path:
        sys.path.insert(0, root)
    # Load the package itself first so relative imports resolve.
    spec = importlib.util.spec_from_file_location(
        "tasks_ai",
        os.path.join(root, "tasks_ai", "__init__.py"),
        submodule_search_locations=[os.path.join(root, "tasks_ai")],
    )
    package = importlib.util.module_from_spec(spec)
    sys.modules["tasks_ai"] = package
    spec.loader.exec_module(package)
    return importlib.import_module("tasks_ai.guard_engine")


STORY = "Sufficiently long story content here to pass validation"
TECH = "Sufficiently long technical description here to pass validation"
CRITERIA = "Sufficiently long acceptance criteria here to pass validation"
PLAN = "Sufficiently long planning details here to pass validation"
TITLE = "Comprehensive Guard Verification Task"

# IDs above the real repo's highest task id -> no collision with fixture data.
BASE_ID = 9001


class GuardTestBase(HammerTestBase):

    def setUp(self):
        super().setUp()
        self._install_guard_into_fixture()

    def _install_guard_into_fixture(self):
        """The harness checks out `main`; make the guard code available."""
        for rel in (
            "guard.py",
            "hammer",
            "repo.py",
            "tasks.py",
            "tasks_ai/guard_engine.py",
            "tasks_ai/pipeline_hooks.py",
            "tasks_ai/cli.py",
            "tasks_ai/commands/move.py",
            "data/errors.json",
            "data/hints.json",
        ):
            shutil.copy2(
                os.path.join(os.getcwd(), rel), os.path.join(self.repo_path, rel)
            )
        self.script_path = os.path.join(self.repo_path, "hammer")

    # --- helpers ---
    def run_guard(self, args, cwd=None):
        return subprocess.run(
            ["python3", os.path.join(self.repo_path, "guard.py")] + args,
            cwd=cwd or self.repo_path,
            capture_output=True,
            text=True,
            check=False,
        )

    def git(self, args, cwd=None):
        return subprocess.run(
            ["git"] + args,
            cwd=cwd or self.repo_path,
            capture_output=True,
            text=True,
            check=False,
        )

    def seed_counter(self, value):
        counter = os.path.join(self.dev_tasks_dir, ".task_counter")
        if os.path.exists(counter):
            os.remove(counter)
        with open(counter, "w") as handle:
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
        return self._find_folder(counter_value + 1, "backlog")

    def _find_folder(self, task_id, state):
        state_dir = os.path.join(self.dev_tasks_dir, state)
        for name in sorted(os.listdir(state_dir)):
            if name.startswith(f"{task_id}-"):
                return name
        return None

    def task_path(self, task_id, state, folder=None):
        folder = folder or self._find_folder(task_id, state)
        return os.path.join(self.dev_tasks_dir, state, folder)

    @property
    def guard_db(self):
        return os.path.join(self.repo_path, ".git", "hammer-guard", "guard.db")

    def scan_json(self):
        result = self.run_guard(["scan", "--json", "--dev"])
        self.assertEqual(result.returncode, 0, f"scan failed: {result.stderr}")
        return json.loads(result.stdout)

    def codes_for(self, task_id):
        return {
            (a["code"], a["task_id"])
            for a in self.scan_json()["anomalies"]
            if a["task_id"] == task_id
        }


class TestGuardScan(GuardTestBase):
    """Read-only reporting: the triage list, not a wall."""

    def test_scan_reports_duplicate_id(self):
        self.git(["branch", f"{BASE_ID}-task-alpha"])
        self.git(["branch", f"{BASE_ID}-issue-beta"])
        data = self.scan_json()
        duplicates = [
            a
            for a in data["anomalies"]
            if a["code"] == "GUARD_DUPLICATE_ID" and a["task_id"] == BASE_ID
        ]
        self.assertEqual(len(duplicates), 1, f"expected one duplicate, got {data}")
        self.assertIn(f"{BASE_ID}-task-alpha", duplicates[0]["detail"])
        self.assertIn(f"{BASE_ID}-issue-beta", duplicates[0]["detail"])

    def test_scan_never_mutates_tasks(self):
        backlog = os.path.join(self.dev_tasks_dir, "backlog")
        before = sorted(os.listdir(backlog))
        self.git(["branch", f"{BASE_ID}-task-alpha"])
        self.git(["branch", f"{BASE_ID}-issue-beta"])
        self.scan_json()
        self.assertEqual(before, sorted(os.listdir(backlog)))

    def test_rebuild_is_deterministic(self):
        self.git(["branch", f"{BASE_ID}-task-alpha"])
        self.git(["branch", f"{BASE_ID}-issue-beta"])
        first = self.run_guard(["rebuild", "--json", "--dev"])
        second = self.run_guard(["rebuild", "--json", "--dev"])
        self.assertEqual(first.returncode, 0, first.stderr)
        self.assertEqual(
            json.loads(first.stdout)["anomalies"], json.loads(second.stdout)["anomalies"]
        )

    def test_adding_a_branch_changes_exactly_one_verdict(self):
        folder = self.create_task(counter_value=BASE_ID - 1)
        self.assertTrue(folder.startswith(f"{BASE_ID}-"), folder)
        base = self.codes_for(BASE_ID)
        self.git(["branch", f"{BASE_ID}-issue-collision"])
        after = self.codes_for(BASE_ID)
        self.assertEqual(after - base, {("GUARD_DUPLICATE_ID", BASE_ID)})
        self.assertEqual(base - after, set())


class TestGuardGate(GuardTestBase):
    """The gate: a duplicate ID must never progress."""

    def test_duplicate_id_cannot_pass_gate(self):
        folder = self.create_task(counter_value=BASE_ID - 1)
        self.git(["branch", f"{BASE_ID}-issue-collision"])
        result = self.run_tasks(["move", str(BASE_ID), "READY"])
        self.assertEqual(result.returncode, 1, f"expected rejection: {result.stdout}")
        payload = json.loads(result.stdout)
        self.assertIn("GUARD", payload["error"])
        self.assertIn("duplicate", payload["error"].lower())
        # the task folder did not move
        self.assertTrue(os.path.isdir(self.task_path(BASE_ID, "backlog", folder)))
        self.assertFalse(
            os.path.isdir(os.path.join(self.dev_tasks_dir, "ready", folder))
        )

    def test_state_duplicate_is_rejected(self):
        folder = self.create_task(counter_value=BASE_ID - 1)
        src = self.task_path(BASE_ID, "backlog", folder)
        dst = os.path.join(self.dev_tasks_dir, "progressing", folder)
        subprocess.run(["cp", "-r", src, dst], check=True)
        result = self.run_tasks(["move", str(BASE_ID), "READY"])
        self.assertEqual(result.returncode, 1, f"expected rejection: {result.stdout}")
        self.assertIn("GUARD", json.loads(result.stdout)["error"])
        self.assertIn("GUARD_STATE_DUPLICATE", {c for c, _ in self.codes_for(BASE_ID)})
        self.assertTrue(os.path.isdir(src))
        self.assertTrue(os.path.isdir(dst))

    def test_force_overrides_and_is_recorded(self):
        folder = self.create_task(counter_value=BASE_ID - 1)
        self.git(["branch", f"{BASE_ID}-issue-collision"])
        forced = self.run_tasks(["move", str(BASE_ID), "READY", "--force"])
        self.assertEqual(forced.returncode, 0, f"force move failed: {forced.stdout}")
        data = self.scan_json()
        bypasses = [
            e
            for e in data["events"]
            if e["code"] == "GUARD_DUPLICATE_ID" and e["task_id"] == BASE_ID
        ]
        self.assertTrue(bypasses, f"forced bypass not recorded: {data['events']}")
        self.assertIn("forced", bypasses[0]["detail"].lower())
        self.assertTrue(os.path.isdir(self.task_path(BASE_ID, "ready", folder)))

    def test_clean_task_passes_gates(self):
        folder = self.create_task(counter_value=BASE_ID - 1)
        for target in ("READY", "PROGRESSING"):
            result = self.run_tasks(["move", str(BASE_ID), target])
            self.assertEqual(
                result.returncode,
                0,
                f"clean task blocked at {target}: {result.stdout} {result.stderr}",
            )
        self.assertTrue(os.path.isdir(self.task_path(BASE_ID, "progressing", folder)))

    def test_remote_duplicate_warns_but_does_not_block(self):
        self.create_task(counter_value=BASE_ID - 1)
        head = self.git(["rev-parse", "HEAD"]).stdout.strip()
        self.git(["update-ref", f"refs/remotes/origin/{BASE_ID}-remote-a", head])
        self.git(["update-ref", f"refs/remotes/origin/{BASE_ID}-remote-b", head])
        result = self.run_tasks(["move", str(BASE_ID), "READY"])
        self.assertEqual(result.returncode, 0, f"remote WARN blocked: {result.stdout}")
        codes = {c for c, _ in self.codes_for(BASE_ID)}
        self.assertIn("GUARD_DUPLICATE_REMOTE_ID", codes)


class TestGuardCache(GuardTestBase):
    """The cache is disposable: corruption self-heals, loss is loud."""

    def test_corrupt_cache_self_heals(self):
        self.create_task(counter_value=BASE_ID - 1)
        self.assertEqual(self.run_guard(["scan", "--dev"]).returncode, 0)
        self.assertTrue(os.path.exists(self.guard_db))
        with open(self.guard_db, "wb") as handle:
            handle.write(b"this is not a sqlite database at all")
        result = self.run_guard(["check", str(BASE_ID), "--to", "TESTING", "--dev"])
        self.assertEqual(result.returncode, 0, f"self-heal failed: {result.stderr}")
        with open(self.guard_db, "rb") as handle:
            self.assertNotIn(b"this is not", handle.read())

    def test_unwritable_cache_rejects_with_actionable_message(self):
        folder = self.create_task(counter_value=BASE_ID - 1)
        cache_dir = os.path.dirname(self.guard_db)
        os.makedirs(cache_dir, exist_ok=True)
        if os.path.isfile(self.guard_db):
            os.remove(self.guard_db)
        os.makedirs(self.guard_db, exist_ok=True)  # dir where the db belongs
        result = self.run_guard(["check", str(BASE_ID), "--to", "TESTING", "--dev"])
        self.assertEqual(result.returncode, 1, "guard must fail closed")
        self.assertIn("GUARD_UNAVAILABLE", result.stderr)
        self.assertIn("guard rebuild", result.stderr)
        self.assertIn("--force", result.stderr)
        # the pipeline gate rejects the same way and leaves the task in place
        moved = self.run_tasks(["move", str(BASE_ID), "READY"])
        self.assertEqual(moved.returncode, 1, f"gate must reject: {moved.stdout}")
        self.assertIn("GUARD", json.loads(moved.stdout)["error"])
        self.assertTrue(os.path.isdir(self.task_path(BASE_ID, "backlog", folder)))

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

            engine_mod = load_guard_engine()
            GuardEngine, GuardUnavailable = engine_mod.GuardEngine, engine_mod.GuardUnavailable

            GuardEngine(repo_root=tmp, tasks_path=None).scan()
            self.git(["checkout", "--detach"], cwd=tmp)
            self.git(["branch", "-D", "main"], cwd=tmp)

            with self.assertRaises(GuardUnavailable) as caught:
                GuardEngine(repo_root=tmp, tasks_path=None).scan()
            self.assertIn("total ref loss", str(caught.exception))

    def test_cache_survives_in_common_dir_from_worktree(self):
        self.create_task(counter_value=BASE_ID - 1)
        branch = self._find_folder(BASE_ID, "backlog")
        worktree_path = os.path.join(self.repo_path, ".task-worktrees", branch)
        self.assertTrue(os.path.isdir(worktree_path), f"no worktree for {branch}")
        self.git(["branch", f"{BASE_ID}-issue-collision"])
        root = self.run_guard(["check", str(BASE_ID), "--dev"])
        inner = self.run_guard(["check", str(BASE_ID), "--dev"], cwd=worktree_path)
        self.assertEqual(root.returncode, inner.returncode)
        self.assertEqual(root.stdout, inner.stdout)
        self.assertNotEqual(root.returncode, 0)  # duplicate detected inside wt too

    def test_duplicate_worktree_for_one_task_is_reported(self):
        self.create_task(counter_value=BASE_ID - 1)
        second = os.path.join(
            self.repo_path, ".task-worktrees", f"{BASE_ID}-issue-second"
        )
        self.git(["worktree", "add", second, "-b", f"{BASE_ID}-issue-second"])
        codes = {c for c, _ in self.codes_for(BASE_ID)}
        self.assertIn("GUARD_WORKTREE_ORPHAN", codes)

    def test_verdict_is_fast_enough_for_a_gate(self):
        GuardEngine = load_guard_engine().GuardEngine

        self.create_task(counter_value=BASE_ID - 1)
        branch = self._find_folder(BASE_ID, "backlog")
        engine = GuardEngine(
            repo_root=self.repo_path,
            tasks_path=self.dev_tasks_dir,
            dev=True,
            cwd=self.repo_path,
        )
        # warm the cache once, then measure the steady-state gate cost
        engine.verdict(BASE_ID, "BACKLOG", "READY", branch)
        start = time.monotonic()
        engine.verdict(BASE_ID, "BACKLOG", "READY", branch)
        elapsed = time.monotonic() - start
        self.assertLess(elapsed, 1.0, f"guard verdict took {elapsed:.2f}s")


class TestGuardIntegration(GuardTestBase):
    """Git hooks and the hammer dispatcher."""

    def test_hooks_install_into_common_dir_from_worktree(self):
        self.create_task(counter_value=BASE_ID - 1)
        branch = self._find_folder(BASE_ID, "backlog")
        worktree_path = os.path.join(self.repo_path, ".task-worktrees", branch)
        result = subprocess.run(
            [
                "python3",
                os.path.join(self.repo_path, "hammer"),
                "tasks",
                "--dev",
                "init-hooks",
            ],
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
        result = subprocess.run(
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
