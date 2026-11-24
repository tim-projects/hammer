import os
import re
import shutil

from tasks_ai.utils import audit_worktrees, store_lock

_TASK_ID = re.compile(r"^(\d+)-")


class WorktreeManager:
    """
    Manages git worktrees for task isolation, replacing the legacy
    branch-based workflow. Each task may have a dedicated worktree
    so development happens in an independent working directory.
    """

    def __init__(self, context, git_service, logger=None):
        self.context = context
        self.git = git_service
        self.logger = logger

    def log(self, message: str):
        if self.logger:
            self.logger.log(message)

    @property
    def worktrees_base(self) -> str:
        return os.path.join(self.context.main_repo_root, ".task-worktrees")

    def _worktree_entries(self) -> list[dict]:
        result = self.git.run(
            ["worktree", "list", "--porcelain"], cwd=self.context.main_repo_root
        )
        if result.returncode != 0:
            return []
        entries = []
        current = {}
        for line in result.stdout.splitlines():
            if not line.strip():
                if current:
                    entries.append(current)
                    current = {}
                continue
            key, _, value = line.partition(" ")
            if key == "worktree":
                current = {"path": value}
            elif key == "branch":
                current["branch"] = value.removeprefix("refs/heads/")
        if current:
            entries.append(current)
        return entries

    @staticmethod
    def _task_id(entry: dict) -> str | None:
        match = _TASK_ID.match(entry.get("branch", ""))
        return match.group(1) if match else None

    def _task_worktrees(self) -> list[dict]:
        entries = []
        for entry in self._worktree_entries():
            task_id = self._task_id(entry)
            if task_id is None:
                continue
            path = entry.get("path")
            base = os.path.abspath(self.worktrees_base)
            managed_path = bool(
                path and os.path.abspath(path).startswith(base + os.sep)
            )
            entries.append(
                {
                    "task_id": task_id,
                    # Stage transitions switch the checked-out branch in place;
                    # a managed worktree directory keeps the original task branch.
                    "branch": (
                        os.path.basename(path) if managed_path else entry.get("branch")
                    ),
                    "path": path,
                    "exists": os.path.exists(path or ""),
                }
            )
        return entries

    def get_worktree_path(self, task_id) -> str | None:
        task_id = str(task_id)
        for entry in self._task_worktrees():
            if entry["task_id"] == task_id:
                return entry["path"]
        return None

    def get_worktree_branch(self, task_id) -> str | None:
        task_id = str(task_id)
        for entry in self._task_worktrees():
            if entry["task_id"] == task_id:
                return entry["branch"]
        return None

    def has_worktree(self, task_id) -> bool:
        path = self.get_worktree_path(task_id)
        return bool(path and os.path.exists(path))

    def detect_task_in_cwd(self, cwd=None) -> str | None:
        abs_cwd = os.path.abspath(cwd or os.getcwd())
        best_match = None
        best_len = 0
        for entry in self._task_worktrees():
            path = entry.get("path")
            if not path:
                continue
            norm = os.path.normpath(path)
            if (abs_cwd == norm or abs_cwd.startswith(norm + os.sep)) and len(
                norm
            ) > best_len:
                best_match = entry["task_id"]
                best_len = len(norm)
        return best_match

    def is_in_task_worktree(self, cwd=None) -> bool:
        return self.detect_task_in_cwd(cwd) is not None

    def create_task_worktree(
        self, task_id, branch=None, base_ref: str | None = None
    ) -> str | None:
        if branch is None:
            branch = str(task_id)
        # A task branch must never materialize the central store in its
        # worktree. Check the branch tree before git checks it out.
        ref = branch
        verify = self.git.run(
            ["rev-parse", "--verify", ref], cwd=self.context.main_repo_root
        )
        if verify.returncode != 0:
            ref = "HEAD"
        tracked = self.git.run(
            ["ls-tree", "-r", "--name-only", ref, "--", ".tasks"],
            cwd=self.context.main_repo_root,
        )
        if tracked.returncode == 0 and tracked.stdout.strip():
            if self.logger:
                self.logger.error(
                    "STORE_BRANCH_TRACKS_TASKS",
                    branch=branch,
                    store_path=os.path.join(self.worktrees_base, branch, ".tasks"),
                )
            return None
        # Check-and-create must be one transaction: two agents mounting at once
        # must not create the same branch concurrently.
        with store_lock(self.context):
            if self.has_worktree(task_id):
                return self.get_worktree_path(task_id)
            os.makedirs(self.worktrees_base, exist_ok=True)
            worktree_path = os.path.join(self.worktrees_base, branch)
            result = self.git.run(
                ["worktree", "add", worktree_path, branch],
                cwd=self.context.main_repo_root,
            )
            if result.returncode != 0:
                create_branch = ["worktree", "add", "-b", branch, worktree_path]
                if base_ref:
                    create_branch.append(base_ref)
                result = self.git.run(
                    create_branch,
                    cwd=self.context.main_repo_root,
                )
            if result.returncode != 0:
                if self.logger:
                    self.logger.error(
                        f"Failed to create worktree for task {task_id}: {result.stderr}"
                    )
                return None
        self.log(f"Git: Created worktree for task {task_id} at '{worktree_path}'")
        return worktree_path

    def live_worktree_paths(self) -> list[str]:
        """Paths git reports as worktrees (the main checkout included)."""
        return [entry["path"] for entry in self._worktree_entries()]

    def audit_worktrees(self) -> list[tuple[str, str | None, str]]:
        """Findings for every worktree path that disagrees with Git."""
        return audit_worktrees(self._worktree_entries(), self.worktrees_base)

    def remove_unregistered_dir(self, path: str) -> bool:
        """Delete a directory under .task-worktrees/ Git does not own.

        Refuses anything that is a real git worktree or outside the base: this is
        a repair, not a cleanup of other agents' working directories.
        """
        base = os.path.abspath(self.worktrees_base)
        target = os.path.abspath(path)
        if not target.startswith(base + os.sep) or not os.path.isdir(target):
            return False
        if target in {os.path.abspath(p) for p in self.live_worktree_paths()}:
            return False
        shutil.rmtree(target)
        return True

    def list_worktrees(self) -> list[dict]:
        return self._task_worktrees()

    def remove_task_worktree(self, task_id, force: bool = False) -> bool:
        with store_lock(self.context):
            entry = next(
                (
                    item
                    for item in self._task_worktrees()
                    if item["task_id"] == str(task_id)
                ),
                None,
            )
            if not entry:
                return False
            path = entry.get("path")
            branch = entry.get("branch")
            branch_exists = False
            merged = False
            if branch:
                verify = self.git.run(
                    ["rev-parse", "--verify", branch], cwd=self.context.main_repo_root
                )
                branch_exists = verify.returncode == 0
                if branch_exists:
                    merged = self.git.is_merged(branch, cwd=self.context.main_repo_root)
            if path and os.path.exists(path):
                cmd = ["worktree", "remove"]
                if force:
                    cmd.append("--force")
                cmd.append(path)
                result = self.git.run(cmd, cwd=self.context.main_repo_root)
                if result.returncode != 0:
                    self.log(
                        f"Warning: Failed to remove worktree at '{path}': {result.stderr}"
                    )
            if branch_exists:
                if merged:
                    self.git.run(
                        ["branch", "-d", branch], cwd=self.context.main_repo_root
                    )
                elif force:
                    self.git.run(
                        ["branch", "-D", branch], cwd=self.context.main_repo_root
                    )
        self.log(f"Git: Removed worktree for task {task_id}")
        return True

    def prune_worktrees(self) -> list[str]:
        with store_lock(self.context):
            stale = [
                entry["task_id"]
                for entry in self._task_worktrees()
                if not entry["exists"]
            ]
            self.git.run(["worktree", "prune"], cwd=self.context.main_repo_root)
        self.log(f"Pruned {len(stale)} stale worktree entries")
        return stale
