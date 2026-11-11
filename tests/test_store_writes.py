"""checkpoint and move must own their own slice of the shared .tasks store.

Locked down here:

1. Scope: 'tasks checkpoint <id>' and 'tasks move' stage only that task's paths,
   so one agent's write never commits another agent's uncommitted work.
2. Loudness: a failing 'git add' or 'git commit' in the store fails the command
   (error, non-zero exit, no 'Done.') instead of silently losing the record.
3. Cleanliness: after a move the store has nothing pending for the moved task -
   no .ops/staging copy, no old-state-folder deletions.
4. Sync: all task markdown parts reach the record, from any cwd (main repo root
   or a task worktree).
"""

import fcntl
import json
import os
import shutil
import subprocess
import tempfile
import time
import unittest

STORY = "Sufficiently long story content here to pass validation"
TECH = "Sufficiently long technical description here to pass validation"
CRITERIA = "Sufficiently long acceptance criteria here to pass validation"
PLAN = "Sufficiently long planning details here to pass validation"

STORE_CONFIG = {
    "repo": {
        "lint": "/bin/true",
        "test": "/bin/true",
        "type_check": "/bin/true",
        "format": "/bin/true",
        "skip_push": True,
    }
}


class TestCheckpointStoreWrites(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.repo_dir = os.path.join(self.test_dir, "repo")
        os.makedirs(self.repo_dir)
        subprocess.run(["git", "init"], cwd=self.repo_dir, capture_output=True)  # noqa: PLW1510
        subprocess.run(
            ["git", "config", "user.email", "test@example.com"], cwd=self.repo_dir
        )  # noqa: PLW1510
        subprocess.run(["git", "config", "user.name", "Test User"], cwd=self.repo_dir)  # noqa: PLW1510
        with open(os.path.join(self.repo_dir, "README.md"), "w") as handle:
            handle.write("# Test Repo")
        subprocess.run(
            ["git", "add", "README.md"], cwd=self.repo_dir, capture_output=True
        )  # noqa: PLW1510
        subprocess.run(
            ["git", "commit", "-m", "Initial commit"],
            cwd=self.repo_dir,
            capture_output=True,
        )  # noqa: PLW1510
        # The symlinked hammer resolves to the working tree under test, so these
        # tests exercise the branch code, not a clone of main.
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.script_path = os.path.join(self.repo_dir, "hammer")
        os.symlink(os.path.join(project_root, "hammer"), self.script_path)
        subprocess.run(["git", "add", "hammer"], cwd=self.repo_dir, capture_output=True)  # noqa: PLW1510
        subprocess.run(
            ["git", "commit", "-m", "Add hammer"],
            cwd=self.repo_dir,
            capture_output=True,
        )  # noqa: PLW1510
        # The store is a real git repo of its own (branch 'tasks'), mirroring
        # production: .tasks is gitignored in the main repo and never merged.
        self.seed_tasks_branch()
        res = self.run_cmd(["init"])
        self.assertTrue(res["success"], f"init must build a store repo: {res}")
        self.assertTrue(
            os.path.isdir(os.path.join(self.repo_dir, ".tasks", ".git")),
            "the .tasks store must be a git repository",
        )
        self.assertTrue(
            os.path.exists(os.path.join(self.repo_dir, ".gitignore")),
            "init must gitignore the store in the main repo",
        )

    def seed_tasks_branch(self):
        """Create an orphan 'tasks' branch carrying the store default config.

        Built with plumbing (no checkout) so the fixture's working tree - and the
        symlinked hammer - survives untouched.
        """
        index = os.path.join(self.test_dir, "seed_index")
        config_path = os.path.join(self.test_dir, "seed_config.yaml")
        with open(config_path, "w") as handle:
            json.dump(STORE_CONFIG, handle)
        env = dict(os.environ, GIT_INDEX_FILE=index)

        def git(*args, **kwargs):
            return subprocess.run(  # noqa: PLW1510
                ["git"] + list(args),
                cwd=self.repo_dir,
                capture_output=True,
                text=True,
                env=env if kwargs.get("indexed") else None,
            ).stdout.strip()

        blob = git("hash-object", "-w", config_path, indexed=True)
        tree = git(
            "update-index",
            "--add",
            "--cacheinfo",
            f"100644,{blob},config.yaml",
            indexed=True,
        ) or git("write-tree", indexed=True)
        commit = subprocess.run(  # noqa: PLW1510
            ["git", "commit-tree", tree, "-m", "Store default config"],
            cwd=self.repo_dir,
            capture_output=True,
            text=True,
        ).stdout.strip()
        subprocess.run(
            ["git", "branch", "tasks", commit], cwd=self.repo_dir, capture_output=True
        )  # noqa: PLW1510

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    # --- helpers ---

    @property
    def store(self):
        return os.path.join(self.repo_dir, ".tasks")

    def run_cmd(self, args, cwd=None, env=None):
        run_env = dict(os.environ)
        if env:
            run_env.update(env)
        result = subprocess.run(  # noqa: PLW1510
            [self.script_path, "tasks", "-j"] + args,
            cwd=cwd or self.repo_dir,
            capture_output=True,
            text=True,
            env=run_env,
        )
        try:
            payload = json.loads(result.stdout)
        except json.JSONDecodeError:
            return {
                "success": False,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "returncode": result.returncode,
            }
        payload["returncode"] = result.returncode
        return payload

    def store_git(self, *args):
        return subprocess.run(  # noqa: PLW1510
            ["git"] + list(args), cwd=self.store, capture_output=True, text=True
        )

    def make_processing_task(self, title):
        res = self.run_cmd(
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
        self.assertTrue(res["success"], res)
        task_file = res["data"]["file"]
        for state in ("READY", "PROGRESSING"):
            moved = self.run_cmd(["move", task_file, state])
            self.assertTrue(moved["success"], moved)
        return res["data"]["id"], task_file

    def make_task(self, title):
        res = self.run_cmd(
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
        self.assertTrue(res["success"], res)
        return res["data"]["id"], res["data"]["file"]

    def task_dir(self, task_file, state="progressing"):
        return os.path.join(self.store, state, task_file)

    def write_part(self, task_file, part, text, state="progressing"):
        path = os.path.join(self.task_dir(task_file, state), f"{part}.md")
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(text)
        return path

    def commit_files(self, rev="HEAD"):
        # --no-renames: a move must show up as the new path added *and* the old
        # state folder deleted, not as a silent rename that hides the deletion.
        out = self.store_git(
            "show", "--name-only", "--no-renames", "--format=", rev
        ).stdout
        return [line for line in out.splitlines() if line.strip()]

    # --- tests ---

    def test_checkpoint_commits_only_its_own_task(self):
        _, file_a = self.make_processing_task("Alpha task for checkpoint scoping")
        _, file_b = self.make_processing_task("Beta task for checkpoint scoping")
        self.write_part(file_a, "story", f"{STORY}\nagent A edit")
        b_edit = f"{STORY}\nagent B uncommitted edit"
        self.write_part(file_b, "story", b_edit)
        b_stray = os.path.join(self.task_dir(file_b), "patches", "b-pending.diff")
        os.makedirs(os.path.dirname(b_stray), exist_ok=True)
        with open(b_stray, "w") as handle:
            handle.write("uncommitted by B")

        res = self.run_cmd(["checkpoint", file_a])
        self.assertTrue(res["success"], res)

        subject = self.store_git("log", "-1", "--format=%s").stdout.strip()
        self.assertEqual(subject, f"Cp: {file_a}")
        committed = self.commit_files()
        a_paths = [p for p in committed if file_a in p]
        b_paths = [p for p in committed if file_b in p]
        self.assertTrue(a_paths, f"task A's own changes must be committed: {committed}")
        self.assertFalse(
            b_paths, f"task B's pending changes must stay out: {committed}"
        )
        self.assertIn(f"progressing/{file_a}/story.md", committed)

        status = self.store_git(
            "status", "--porcelain", "--untracked-files=all"
        ).stdout.splitlines()
        self.assertTrue(
            any(f"{file_b}/story.md" in line for line in status),
            f"task B must still be pending: {status}",
        )
        self.assertTrue(
            any("b-pending.diff" in line for line in status),
            f"task B must still be pending: {status}",
        )
        with open(os.path.join(self.task_dir(file_b), "story.md")) as handle:
            self.assertEqual(handle.read(), b_edit, "B must keep its uncommitted edit")

        # B's own checkpoint commits only B, so no write ever lands in A's commit.
        res_b = self.run_cmd(["checkpoint", file_b])
        self.assertTrue(res_b["success"], res_b)
        self.assertEqual(
            self.store_git("log", "-1", "--format=%s").stdout.strip(), f"Cp: {file_b}"
        )
        committed_b = self.commit_files()
        self.assertFalse([p for p in committed_b if file_a in p], committed_b)
        self.assertTrue(
            [p for p in committed_b if f"{file_b}/story.md" in p], committed_b
        )
        self.assertIn(
            f"progressing/{file_b}/patches/b-pending.diff",
            committed_b,
            "untracked files inside the task dir must be committed too",
        )
        # Leftovers under old state folders and .ops/ come from the move path's
        # own store-wide add (tracked separately, not checkpoint scope): only the
        # live records must be fully committed by their own checkpoints.
        leftover = [
            line
            for line in self.store_git("status", "--porcelain").stdout.splitlines()
            if f"progressing/{file_a}/" in line or f"progressing/{file_b}/" in line
        ]
        self.assertEqual(leftover, [], "both task records must be fully committed")

    def test_checkpoint_add_failure_is_fatal(self):
        _, file_a = self.make_processing_task("Gamma task for checkpoint failure")
        self.write_part(file_a, "story", f"{STORY}\nagent edit before lock")
        lock = os.path.join(self.store, ".git", "index.lock")
        with open(lock, "w") as handle:
            handle.write("")
        try:
            res = self.run_cmd(["checkpoint", file_a])
        finally:
            os.remove(lock)

        self.assertNotEqual(
            res["returncode"], 0, "a failed store add must exit non-zero"
        )
        self.assertFalse(res["success"], res)
        self.assertIn("Store write failed", res.get("error", ""), res)
        self.assertNotIn("Done.", json.dumps(res.get("messages", [])), res)
        pending = self.store_git("status", "--porcelain").stdout
        self.assertIn(
            "story.md", pending, "the failed checkpoint must leave the edit pending"
        )

        retry = self.run_cmd(["checkpoint", file_a])
        self.assertTrue(retry["success"], retry)
        self.assertIn(
            f"progressing/{file_a}/story.md",
            self.commit_files(),
            "retry after the lock clears must commit the pending edit",
        )

    def test_checkpoint_commit_failure_is_fatal(self):
        _, file_a = self.make_processing_task("Delta task for commit failure")
        self.write_part(file_a, "story", f"{STORY}\nagent edit before bad date")
        res = self.run_cmd(["checkpoint", file_a], env={"GIT_COMMITTER_DATE": "bogus"})

        self.assertNotEqual(
            res["returncode"], 0, "a failed store commit must exit non-zero"
        )
        self.assertFalse(res["success"], res)
        self.assertIn("Store write failed", res.get("error", ""), res)
        self.assertNotIn("Done.", json.dumps(res.get("messages", [])), res)
        self.assertIn(
            "story.md",
            self.store_git("status", "--porcelain").stdout,
            "the uncommitted edit must survive the failed commit",
        )

    def test_hand_edited_parts_reach_the_record(self):
        _, file_a = self.make_processing_task("Epsilon task for part sync")
        criteria = "Hand written criteria the agent edited straight on disk"
        tech = "Hand written technical notes the agent edited straight on disk"
        self.write_part(file_a, "criteria", criteria)
        self.write_part(file_a, "tech", tech)

        res = self.run_cmd(["checkpoint", file_a])
        self.assertTrue(res["success"], res)

        committed = self.commit_files()
        self.assertIn(f"progressing/{file_a}/criteria.md", committed, committed)
        self.assertIn(f"progressing/{file_a}/tech.md", committed, committed)
        for part, text in (("criteria", criteria), ("tech", tech)):
            shown = self.store_git(
                "show", f"HEAD:progressing/{file_a}/{part}.md"
            ).stdout
            self.assertEqual(
                shown.strip(), text, f"{part} must be synced into the record"
            )

    def test_sync_and_checkpoint_work_from_task_worktree_cwd(self):
        """The sync path must not depend on the process cwd."""
        _, file_a = self.make_processing_task("Zeta task for worktree cwd")
        worktree = os.path.join(self.test_dir, "wt")
        base = subprocess.run(  # noqa: PLW1510
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=self.repo_dir,
            capture_output=True,
            text=True,
        ).stdout.strip()
        added = subprocess.run(  # noqa: PLW1510
            ["git", "worktree", "add", "--detach", worktree, base],
            cwd=self.repo_dir,
            capture_output=True,
            text=True,
        )
        self.assertEqual(added.returncode, 0, added.stderr)
        self.assertTrue(os.path.exists(os.path.join(worktree, "hammer")))

        plan = "Plan edited while hammer ran from the task worktree"
        self.write_part(file_a, "plan", plan)
        res = self.run_cmd(["checkpoint", file_a], cwd=worktree)

        self.assertTrue(res["success"], res)
        committed = self.commit_files()
        self.assertIn(f"progressing/{file_a}/plan.md", committed, committed)
        shown = self.store_git("show", f"HEAD:progressing/{file_a}/plan.md").stdout
        self.assertEqual(shown.strip(), plan)

    # --- move path ---

    def test_move_does_not_commit_other_task_pending_changes(self):
        _, file_a = self.make_task("Alpha task for move scoping")
        _, file_b = self.make_task("Beta task for move scoping")
        b_edit = f"{STORY}\nagent B uncommitted edit"
        self.write_part(file_b, "story", b_edit, state="backlog")

        res = self.run_cmd(["move", file_a, "READY"])
        self.assertTrue(res["success"], res)

        subject = self.store_git("log", "-1", "--format=%s").stdout.strip()
        self.assertEqual(subject, f"Mv {file_a} -> READY")
        committed = self.commit_files()
        self.assertTrue([p for p in committed if file_a in p], committed)
        self.assertFalse([p for p in committed if file_b in p], committed)
        self.assertIn(
            f"ready/{file_a}/story.md",
            committed,
            "the moved record must be in the move commit",
        )
        self.assertIn(
            f"backlog/{file_a}/story.md",
            committed,
            "the old state folder must be recorded as deleted",
        )

        status = self.store_git("status", "--porcelain", "--untracked-files=all").stdout
        self.assertIn(
            f"backlog/{file_b}/story.md",
            status,
            f"task B must still be pending: {status}",
        )
        with open(os.path.join(self.task_dir(file_b, "backlog"), "story.md")) as handle:
            self.assertEqual(handle.read(), b_edit, "B must keep its uncommitted edit")

    def test_store_has_no_pending_leftovers_after_move(self):
        _, file_a = self.make_task("Gamma task for move cleanliness")
        res = self.run_cmd(["move", file_a, "READY"])
        self.assertTrue(res["success"], res)

        status = self.store_git("status", "--porcelain", "--untracked-files=all").stdout
        ops_leftovers = [line for line in status.splitlines() if ".ops/" in line]
        self.assertEqual(
            ops_leftovers, [], f"the .ops staging copy must not linger: {status}"
        )
        stale = [line for line in status.splitlines() if f"backlog/{file_a}/" in line]
        self.assertEqual(
            stale, [], f"the old state folder must be committed as deleted: {status}"
        )
        moved = [line for line in status.splitlines() if f"ready/{file_a}/" in line]
        self.assertEqual(moved, [], f"the new record must be committed: {status}")

    def test_move_leaves_the_store_clean_for_both_agents(self):
        """The move commit must close out the move, leaving nothing pending.

        'tasks undo' cannot assert this end to end: it silently no-ops in this
        fixture (a pre-existing defect, independent of the store write), so the
        cleanup is asserted straight from the store instead.
        """
        _, file_a = self.make_task("Delta task for move cleanliness")
        _, file_b = self.make_task("Epsilon task for move cleanliness")
        self.write_part(
            file_b, "story", f"{STORY}\nagent B uncommitted edit", state="backlog"
        )

        moved = self.run_cmd(["move", file_a, "READY"])
        self.assertTrue(moved["success"], moved)

        committed = self.commit_files()
        self.assertIn(f"ready/{file_a}/story.md", committed, committed)
        self.assertIn(f"backlog/{file_a}/story.md", committed, committed)
        status = self.store_git("status", "--porcelain", "--untracked-files=all").stdout
        self.assertFalse(
            [line for line in status.splitlines() if file_a in line],
            f"nothing may stay pending for the moved task: {status}",
        )
        self.assertTrue(
            [line for line in status.splitlines() if file_b in line],
            f"task B must still be pending: {status}",
        )

    def test_move_clears_legacy_ops_copy(self):
        """A .ops staging copy committed by the legacy add -f . must be closed.

        The move deletes the copy, so its deletion has to land in the move commit
        instead of staying pending where nothing scoped will ever pick it up.
        """
        _, file_a = self.make_task("Zeta task for legacy ops cleanup")
        staging = os.path.join(self.store, ".ops", "staging", file_a)
        os.makedirs(staging, exist_ok=True)
        shutil.copy2(
            os.path.join(self.task_dir(file_a, "backlog"), "meta.json"), staging
        )
        self.assertTrue(self.store_git("add", "--", ".ops/staging").returncode == 0)
        self.store_git("commit", "-m", "legacy staging commit")

        moved = self.run_cmd(["move", file_a, "READY"])
        self.assertTrue(moved["success"], moved)

        self.assertIn(
            f".ops/staging/{file_a}/meta.json",
            self.commit_files(),
            "the legacy .ops deletion must be committed by the move",
        )
        status = self.store_git("status", "--porcelain", "--untracked-files=all").stdout
        self.assertFalse(
            [line for line in status.splitlines() if ".ops/" in line],
            f"no .ops residue may stay pending: {status}",
        )

    def test_audit_commits_its_own_review_artifacts(self):
        """tasks audit must close out the audit file and patches it writes.

        Both used to sit untracked in the shared store until some other
        command's store-wide add swept them up.
        """
        _, file_a = self.make_processing_task("Iota task for audit store write")
        with open(os.path.join(self.task_dir(file_a), "criteria.md"), "w") as handle:
            handle.write("- [x] done\n- [x] also done\n")
        for state in ("TESTING", "REVIEW"):
            self.assertTrue(self.run_cmd(["move", file_a, state])["success"], state)

        audited = self.run_cmd(["audit", file_a])
        self.assertTrue(audited["success"], audited)
        audit_rel = f"review/{file_a}.audit"

        self.assertIn(audit_rel, self.commit_files(), "audit output must be committed")
        subject = self.store_git("log", "-1", "--format=%s").stdout.strip()
        self.assertEqual(subject, f"Audit {file_a}")
        pending = [
            line
            for line in self.store_git(
                "status", "--porcelain", "--untracked-files=all"
            ).stdout.splitlines()
            if file_a in line
        ]
        self.assertEqual(pending, [], f"audit must leave nothing pending: {pending}")

    def test_move_commits_the_audit_sibling(self):
        """A move into READY/PROGRESSING cleans review artifacts; that deletion
        must land in the move commit when the audit file was committed."""
        _, file_a = self.make_processing_task("Kappa task for audit sibling")
        with open(os.path.join(self.task_dir(file_a), "criteria.md"), "w") as handle:
            handle.write("- [x] done\n- [x] also done\n")
        for state in ("TESTING", "REVIEW"):
            self.assertTrue(self.run_cmd(["move", file_a, state])["success"], state)
        self.assertTrue(self.run_cmd(["audit", file_a])["success"])

        moved = self.run_cmd(["move", file_a, "PROGRESSING"])
        self.assertTrue(moved["success"], moved)

        committed = self.commit_files()
        self.assertTrue(
            [
                p
                for p in committed
                if f"ready/{file_a}/" in p or f"progressing/{file_a}/" in p
            ],
            committed,
        )
        pending = [
            line
            for line in self.store_git(
                "status", "--porcelain", "--untracked-files=all"
            ).stdout.splitlines()
            if file_a in line or ".ops/" in line
        ]
        self.assertEqual(
            pending, [], f"the move must close out its artifacts: {pending}"
        )


if __name__ == "__main__":
    unittest.main()


class TestStoreCommitsAreScopedPerCommand(unittest.TestCase):
    """unlink, delete, doctor --fix and the archive hook must own their own slice.

    Every one of them used to run a store-wide 'git add --all' in the shared
    .tasks repo, so a second agent's uncommitted edit landed in their commit
    under their message - and the archive hook pushed that mixed state. Each
    test below keeps a pending edit from a second task in the store and asserts
    the commit's name-status contains nothing from it.
    """

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.repo_dir = os.path.join(self.test_dir, "repo")
        os.makedirs(self.repo_dir)
        subprocess.run(
            ["git", "init", "-b", "main"], cwd=self.repo_dir, capture_output=True
        )  # noqa: PLW1510
        subprocess.run(
            ["git", "config", "user.email", "test@example.com"], cwd=self.repo_dir
        )  # noqa: PLW1510
        subprocess.run(["git", "config", "user.name", "Test User"], cwd=self.repo_dir)  # noqa: PLW1510
        with open(os.path.join(self.repo_dir, "README.md"), "w") as handle:
            handle.write("# Test Repo")
        subprocess.run(
            ["git", "add", "README.md"], cwd=self.repo_dir, capture_output=True
        )  # noqa: PLW1510
        subprocess.run(
            ["git", "commit", "-m", "Initial commit"],
            cwd=self.repo_dir,
            capture_output=True,
        )  # noqa: PLW1510
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.script_path = os.path.join(self.repo_dir, "hammer")
        os.symlink(os.path.join(project_root, "hammer"), self.script_path)
        subprocess.run(["git", "add", "hammer"], cwd=self.repo_dir, capture_output=True)  # noqa: PLW1510
        subprocess.run(
            ["git", "commit", "-m", "Add hammer"],
            cwd=self.repo_dir,
            capture_output=True,
        )  # noqa: PLW1510
        self.seed_tasks_branch()
        res = self.run_cmd(["init"])
        self.assertTrue(res["success"], f"init must build a store repo: {res}")
        # A real remote so the archive hook's store push can be observed.
        self.bare = os.path.join(self.test_dir, "origin.git")
        subprocess.run(
            ["git", "init", "--bare", "-b", "main", self.bare], capture_output=True
        )  # noqa: PLW1510
        for args in (
            ["remote", "add", "origin", self.bare],
            ["push", "origin", "main"],
        ):
            subprocess.run(["git"] + args, cwd=self.repo_dir, capture_output=True)  # noqa: PLW1510

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    # --- helpers ---

    @property
    def store(self):
        return os.path.join(self.repo_dir, ".tasks")

    def seed_tasks_branch(self):
        """Orphan 'tasks' branch carrying the store default config (see above)."""
        index = os.path.join(self.test_dir, "seed_index")
        config_path = os.path.join(self.test_dir, "seed_config.yaml")
        with open(config_path, "w") as handle:
            json.dump(STORE_CONFIG, handle)
        env = dict(os.environ, GIT_INDEX_FILE=index)

        def git(*args, **kwargs):
            return subprocess.run(  # noqa: PLW1510
                ["git"] + list(args),
                cwd=self.repo_dir,
                capture_output=True,
                text=True,
                env=env if kwargs.get("indexed") else None,
            ).stdout.strip()

        blob = git("hash-object", "-w", config_path, indexed=True)
        tree = git(
            "update-index",
            "--add",
            "--cacheinfo",
            f"100644,{blob},config.yaml",
            indexed=True,
        ) or git("write-tree", indexed=True)
        commit = subprocess.run(  # noqa: PLW1510
            ["git", "commit-tree", tree, "-m", "Store default config"],
            cwd=self.repo_dir,
            capture_output=True,
            text=True,
        ).stdout.strip()
        subprocess.run(
            ["git", "branch", "tasks", commit], cwd=self.repo_dir, capture_output=True
        )  # noqa: PLW1510

    def run_cmd(self, args):
        result = subprocess.run(  # noqa: PLW1510
            [self.script_path, "tasks", "-j"] + args,
            cwd=self.repo_dir,
            capture_output=True,
            text=True,
        )
        try:
            payload = json.loads(result.stdout)
        except json.JSONDecodeError:
            return {
                "success": False,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "returncode": result.returncode,
            }
        payload["returncode"] = result.returncode
        return payload

    def store_git(self, *args):
        return subprocess.run(  # noqa: PLW1510
            ["git"] + list(args), cwd=self.store, capture_output=True, text=True
        )

    def git(self, *args, cwd=None):
        return subprocess.run(  # noqa: PLW1510
            ["git"] + list(args),
            cwd=cwd or self.repo_dir,
            capture_output=True,
            text=True,
        )

    def make_task(self, title, state="backlog"):
        res = self.run_cmd(
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
        self.assertTrue(res["success"], res)
        return res["data"]["file"]

    def task_path(self, task_file, state="backlog"):
        return os.path.join(self.store, state, task_file)

    def write_part(self, task_file, part, text, state="backlog"):
        path = os.path.join(self.task_path(task_file, state), f"{part}.md")
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(text)
        return path

    def edit_part(self, task_file, part, text, state="backlog"):
        path = os.path.join(self.task_path(task_file, state), f"{part}.md")
        with open(path, "a", encoding="utf-8") as handle:
            handle.write(text)
        return path

    def commit_files(self, rev="HEAD"):
        out = self.store_git(
            "show", "--name-only", "--no-renames", "--format=", rev
        ).stdout
        return [line for line in out.splitlines() if line.strip()]

    def commit_subject(self, rev="HEAD"):
        return self.store_git("log", "-1", "--format=%s", rev).stdout.strip()

    def find_commit(self, prefix):
        """Newest store commit whose subject starts with prefix."""
        for line in self.store_git("log", "--format=%H%x09%s").stdout.splitlines():
            sha, _, subject = line.partition("\t")
            if subject.startswith(prefix):
                return sha
        return None

    def pending_lines(self):
        return self.store_git(
            "status", "--porcelain", "--untracked-files=all"
        ).stdout.splitlines()

    def assert_own_paths_only(self, rev, own_file, other_file):
        committed = self.commit_files(rev)
        self.assertTrue(
            [p for p in committed if own_file in p],
            f"the task's own paths must be committed: {committed}",
        )
        self.assertFalse(
            [p for p in committed if other_file in p],
            f"another task's paths leaked into this commit: {committed}",
        )

    # --- per-task sites ---

    def test_unlink_commits_only_its_own_task(self):
        file_a = self.make_task("Alpha task for unlink scoping")
        file_b = self.make_task("Beta task for unlink scoping")
        self.assertTrue(self.run_cmd(["link", file_a, file_b])["success"])
        b_edit = f"{STORY}\nagent B uncommitted edit"
        self.write_part(file_b, "story", b_edit)

        res = self.run_cmd(["unlink", file_a, file_b])
        self.assertTrue(res["success"], res)

        self.assertEqual(self.commit_subject(), f"Unlk {file_a}->{file_b}")
        self.assert_own_paths_only("HEAD", file_a, file_b)
        pending = self.pending_lines()
        self.assertTrue(
            any(f"{file_b}/story.md" in line for line in pending),
            f"task B must still be pending: {pending}",
        )
        with open(os.path.join(self.task_path(file_b), "story.md")) as handle:
            self.assertEqual(handle.read(), b_edit, "B must keep its uncommitted edit")

    def test_permanent_delete_commits_only_its_own_task(self):
        file_a = self.make_task("Alpha task for delete scoping")
        file_b = self.make_task("Beta task for delete scoping")
        b_edit = f"{STORY}\nagent B uncommitted edit"
        self.write_part(file_b, "story", b_edit)
        marked = self.run_cmd(["delete", file_a])
        self.assertTrue(marked["success"], marked)
        code = marked["data"]["delete_code"]

        res = self.run_cmd(["delete", file_a, "--confirm", code])
        self.assertTrue(res["success"], res)

        self.assertEqual(self.commit_subject(), f"Del {file_a}")
        self.assert_own_paths_only("HEAD", file_a, file_b)
        pending = self.pending_lines()
        self.assertTrue(
            any(f"{file_b}/story.md" in line for line in pending),
            f"task B must still be pending: {pending}",
        )
        with open(os.path.join(self.task_path(file_b), "story.md")) as handle:
            self.assertEqual(handle.read(), b_edit, "B must keep its uncommitted edit")

    def test_doctor_fix_commits_only_its_own_task(self):
        file_a = self.make_task("Alpha task for doctor scoping")
        file_b = self.make_task("Beta task for doctor scoping")
        b_edit = f"{STORY}\nagent B uncommitted edit"
        self.write_part(file_b, "story", b_edit)
        # Break A's branch metadata and give it an uncommitted edit of its own,
        # so the repair commit has this task's paths in it.
        self.edit_part(file_a, "story", "\nagent A own edit")
        with open(os.path.join(self.task_path(file_a), "meta.json")) as handle:
            meta = json.load(handle)
        meta["Br"] = "9999-task-alpha-task-for-doctor-scoping"
        with open(os.path.join(self.task_path(file_a), "meta.json"), "w") as handle:
            json.dump(meta, handle, indent=2)

        res = self.run_cmd(["doctor", "--fix"])
        self.assertTrue(res["success"], res)

        sha = self.find_commit("Doctor: fixed task inconsistencies")
        self.assertIsNotNone(sha, "the repair must commit under its own message")
        self.assertEqual(
            self.commit_subject(sha), f"Doctor: fixed task inconsistencies for {file_a}"
        )
        self.assert_own_paths_only(sha, file_a, file_b)
        pending = self.pending_lines()
        self.assertTrue(
            any(f"{file_b}/story.md" in line for line in pending),
            f"task B must still be pending: {pending}",
        )
        with open(os.path.join(self.task_path(file_b), "story.md")) as handle:
            self.assertEqual(handle.read(), b_edit, "B must keep its uncommitted edit")

    def test_archive_hook_pushes_only_the_archived_task(self):
        file_c = self.make_task("Gamma task for archive scoping")
        file_b = self.make_task("Beta task for archive scoping")
        for state in ("READY", "PROGRESSING"):
            moved = self.run_cmd(["move", file_c, state])
            self.assertTrue(moved["success"], moved)
        worktree = os.path.join(self.repo_dir, ".task-worktrees", file_c)
        self.assertTrue(os.path.isdir(worktree), worktree)
        with open(os.path.join(worktree, "feature.py"), "w") as handle:
            handle.write("def feature():\n    return True\n")
        self.git("add", "feature.py", cwd=worktree)
        self.git("commit", "-m", "Add feature", cwd=worktree)
        b_edit = f"{STORY}\nagent B uncommitted edit"
        self.write_part(file_b, "story", b_edit)

        # The branch must be merged (and pushed) before the archive proceeds
        # past the hook, so the whole archive flow runs.
        merged = self.git("merge", file_c)
        self.assertEqual(merged.returncode, 0, merged.stderr)
        self.assertEqual(self.git("push", "origin", "main").returncode, 0)

        res = self.run_cmd(["move", file_c, "ARCHIVED", "-f"])
        self.assertTrue(res["success"], res)

        archive_sha = self.find_commit("Archive [")
        self.assertIsNotNone(archive_sha, "the archive hook must commit the store")
        self.assertTrue(
            os.path.isdir(os.path.join(self.store, "archived", file_c)),
            "the task must be archived",
        )

        # The hook pushes before it removes the worktree, so the state it
        # pushed is exactly the archive commit.
        remote = self.store_git("remote", "get-url", "origin").stdout.strip()
        self.assertTrue(os.path.isabs(remote) and os.path.isdir(remote), remote)
        pushed = subprocess.run(  # noqa: PLW1510
            ["git", "rev-parse", "tasks"],
            cwd=remote,
            capture_output=True,
            text=True,
        ).stdout.strip()
        self.assertEqual(
            pushed, archive_sha, "the pushed store state must be the archive commit"
        )

        self.assert_own_paths_only(archive_sha, file_c, file_b)
        pending = self.pending_lines()
        self.assertTrue(
            any(f"{file_b}/story.md" in line for line in pending),
            f"task B must still be pending after the push: {pending}",
        )
        with open(os.path.join(self.store, "backlog", file_b, "story.md")) as handle:
            self.assertEqual(handle.read(), b_edit, "B must keep its uncommitted edit")

    def test_concurrent_unlink_and_checkpoint_stay_scoped(self):
        """Two agents writing at once: two commits, each its own task's."""
        file_a = self.make_task("Alpha task for concurrent scoping")
        file_b = self.make_task("Beta task for concurrent scoping")
        for state in ("READY", "PROGRESSING"):
            for task_file in (file_a, file_b):
                moved = self.run_cmd(["move", task_file, state])
                self.assertTrue(moved["success"], moved)
        self.assertTrue(self.run_cmd(["link", file_a, file_b])["success"])
        self.edit_part(
            file_b, "story", "\nagent B uncommitted edit", state="progressing"
        )
        before = self.store_git("rev-parse", "HEAD").stdout.strip()

        procs = [
            subprocess.Popen(
                [self.script_path, "tasks", "-j", "unlink", file_a, file_b],
                cwd=self.repo_dir,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            ),
            subprocess.Popen(
                [self.script_path, "tasks", "-j", "checkpoint", file_b],
                cwd=self.repo_dir,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            ),
        ]
        for proc in procs:
            out, _ = proc.communicate(timeout=120)
            payload = json.loads(out)
            self.assertTrue(payload["success"], payload)

        new_log = [
            line.split("\t", 1)[1]
            for line in self.store_git(
                "log", "--format=%H%x09%s", f"{before}..HEAD"
            ).stdout.splitlines()
            if line.strip()
        ]
        self.assertEqual(
            sorted(new_log),
            sorted([f"Unlk {file_a}->{file_b}", f"Cp: {file_b}"]),
            "the race must produce exactly one commit per command",
        )
        for line in self.store_git(
            "log", "--format=%H%x09%s", f"{before}..HEAD"
        ).stdout.splitlines():
            sha, _, subject = line.partition("\t")
            if subject.startswith("Unlk"):
                self.assert_own_paths_only(sha, file_a, file_b)
            else:
                self.assert_own_paths_only(sha, file_b, file_a)


class TestWholeStoreSweepsHoldTheStoreLock(unittest.TestCase):
    """The two documented whole-store sweeps must hold the store write lock.

    They legitimately touch every record in the store (a LIVE->DONE migration
    and the delete-mark sweep), so they cannot be scoped per task; the lock at
    least stops another agent's commit landing inside theirs.
    """

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.repo_dir = os.path.join(self.test_dir, "repo")
        os.makedirs(self.repo_dir)
        subprocess.run(
            ["git", "init", "-b", "main"], cwd=self.repo_dir, capture_output=True
        )  # noqa: PLW1510
        subprocess.run(
            ["git", "config", "user.email", "test@example.com"], cwd=self.repo_dir
        )  # noqa: PLW1510
        subprocess.run(["git", "config", "user.name", "Test User"], cwd=self.repo_dir)  # noqa: PLW1510
        with open(os.path.join(self.repo_dir, "README.md"), "w") as handle:
            handle.write("# Test Repo")
        subprocess.run(
            ["git", "add", "README.md"], cwd=self.repo_dir, capture_output=True
        )  # noqa: PLW1510
        subprocess.run(
            ["git", "commit", "-m", "Initial commit"],
            cwd=self.repo_dir,
            capture_output=True,
        )  # noqa: PLW1510
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.script_path = os.path.join(self.repo_dir, "hammer")
        os.symlink(os.path.join(project_root, "hammer"), self.script_path)
        subprocess.run(["git", "add", "hammer"], cwd=self.repo_dir, capture_output=True)  # noqa: PLW1510
        subprocess.run(
            ["git", "commit", "-m", "Add hammer"],
            cwd=self.repo_dir,
            capture_output=True,
        )  # noqa: PLW1510
        index = os.path.join(self.test_dir, "seed_index")
        config_path = os.path.join(self.test_dir, "seed_config.yaml")
        with open(config_path, "w") as handle:
            json.dump(STORE_CONFIG, handle)
        env = dict(os.environ, GIT_INDEX_FILE=index)

        def git(*args, **kwargs):
            return subprocess.run(  # noqa: PLW1510
                ["git"] + list(args),
                cwd=self.repo_dir,
                capture_output=True,
                text=True,
                env=env if kwargs.get("indexed") else None,
            ).stdout.strip()

        blob = git("hash-object", "-w", config_path, indexed=True)
        tree = git(
            "update-index",
            "--add",
            "--cacheinfo",
            f"100644,{blob},config.yaml",
            indexed=True,
        ) or git("write-tree", indexed=True)
        commit = subprocess.run(  # noqa: PLW1510
            ["git", "commit-tree", tree, "-m", "Store default config"],
            cwd=self.repo_dir,
            capture_output=True,
            text=True,
        ).stdout.strip()
        subprocess.run(
            ["git", "branch", "tasks", commit], cwd=self.repo_dir, capture_output=True
        )  # noqa: PLW1510
        res = self.run_cmd(["init"])
        self.assertTrue(res["success"], f"init must build a store repo: {res}")
        created = self.make_task("Alpha task for sweep locking")
        self.assertTrue(created["success"], created)
        self.addCleanup(shutil.rmtree, self.test_dir, ignore_errors=True)

    @property
    def store(self):
        return os.path.join(self.repo_dir, ".tasks")

    def run_cmd(self, args):
        result = subprocess.run(  # noqa: PLW1510
            [self.script_path, "tasks", "-j"] + args,
            cwd=self.repo_dir,
            capture_output=True,
            text=True,
        )
        try:
            return json.loads(result.stdout)
        except json.JSONDecodeError:
            return {
                "success": False,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "returncode": result.returncode,
            }

    def make_task(self, title):
        return self.run_cmd(
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

    def store_git(self, *args):
        return subprocess.run(  # noqa: PLW1510
            ["git"] + list(args), cwd=self.store, capture_output=True, text=True
        )

    def hold_lock(self):
        """Take the store lock here; a sweep that ignores it finishes anyway."""
        fd = os.open(
            os.path.join(self.store, ".hammer-lock"), os.O_CREAT | os.O_RDWR, 0o644
        )
        fcntl.flock(fd, fcntl.LOCK_EX)
        released = []

        def release():
            if not released:
                released.append(True)
                fcntl.flock(fd, fcntl.LOCK_UN)
                os.close(fd)

        self.addCleanup(release)
        return release

    def run_blocking_until_released(self, release, args):
        proc = subprocess.Popen(
            [self.script_path, "tasks", "-j"] + args,
            cwd=self.repo_dir,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        time.sleep(2.0)
        self.assertIsNone(proc.poll(), "the sweep must block while the lock is held")
        release()
        out, _ = proc.communicate(timeout=60)
        payload = json.loads(out)
        self.assertTrue(payload["success"], payload)
        return payload

    def test_clear_delete_marks_holds_the_store_lock(self):
        """A pending delete mark makes every command sweep the store."""
        created = self.make_task("Beta task for delete mark sweep")
        self.assertTrue(created["success"], created)
        marked = self.run_cmd(["delete", str(created["data"]["id"])])
        self.assertTrue(marked["success"], marked)

        release = self.hold_lock()
        self.run_blocking_until_released(release, ["list"])

        # The sweep that ran under the lock cleared the mark it found.
        meta_path = os.path.join(
            self.store, "rejected", created["data"]["file"], "meta.json"
        )
        with open(meta_path) as handle:
            self.assertNotIn(
                "DeleteCode", handle.read(), "the sweep must clear the delete mark"
            )

    def test_live_to_done_migration_holds_the_store_lock(self):
        """A stray live/ folder makes every command migrate it to done/."""
        live_task = os.path.join(self.store, "live", "0-task-legacy-live-record")
        os.makedirs(live_task)
        with open(os.path.join(live_task, "meta.json"), "w") as handle:
            json.dump({"Id": 0, "St": "DONE"}, handle)

        release = self.hold_lock()
        self.run_blocking_until_released(release, ["list"])

        self.assertTrue(
            os.path.isdir(
                os.path.join(self.store, "done", "0-task-legacy-live-record")
            ),
            "the migration must complete once the lock is free",
        )
