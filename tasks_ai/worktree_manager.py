import json
import os

from tasks_ai.utils import store_lock



class WorktreeManager:
    """
    Manages git worktrees for task isolation, replacing the legacy
    branch-based workflow. Each task may have a dedicated worktree
    so development happens in an independent working directory.
    """

    MANIFEST_NAME = "worktrees.json"

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

    @property
    def manifest_path(self) -> str:
        return os.path.join(self.context.tasks_path, self.MANIFEST_NAME)

    def _load_manifest(self) -> dict:
        if not os.path.exists(self.manifest_path):
            return {"worktrees": {}}
        try:
            with open(self.manifest_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, dict):
                return {"worktrees": {}}
            data.setdefault("worktrees", {})
            return data
        except (json.JSONDecodeError, OSError):
            return {"worktrees": {}}

    def _save_manifest(self, manifest: dict):
        os.makedirs(os.path.dirname(self.manifest_path), exist_ok=True)
        tmp_path = self.manifest_path + ".tmp"
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2)
        os.replace(tmp_path, self.manifest_path)

    def get_worktree_path(self, task_id) -> str | None:
        manifest = self._load_manifest()
        entry = manifest.get("worktrees", {}).get(str(task_id))
        if entry:
            return entry.get("path")
        return None

    def get_worktree_branch(self, task_id) -> str | None:
        manifest = self._load_manifest()
        entry = manifest.get("worktrees", {}).get(str(task_id))
        if entry:
            return entry.get("branch")
        return None

    def has_worktree(self, task_id) -> bool:
        path = self.get_worktree_path(task_id)
        if not path:
            return False
        return os.path.exists(path)

    def detect_task_in_cwd(self, cwd=None) -> str | None:
        abs_cwd = os.path.abspath(cwd or os.getcwd())
        manifest = self._load_manifest()
        best_match = None
        best_len = 0
        for task_id, entry in manifest.get("worktrees", {}).items():
            wt_path = entry.get("path")
            if not wt_path:
                continue
            norm = os.path.normpath(wt_path)
            if (abs_cwd == norm or abs_cwd.startswith(norm + os.sep)) and len(
                norm
            ) > best_len:
                best_match = task_id
                best_len = len(norm)
        return best_match

    def is_in_task_worktree(self, cwd=None) -> bool:
        return self.detect_task_in_cwd(cwd) is not None

    def create_task_worktree(self, task_id, branch=None) -> str | None:
        if branch is None:
            branch = str(task_id)
        # Check-and-register must be one transaction: two agents mounting at
        # once both pass has_worktree and then rewrite the manifest from a
        # stale copy, dropping each other's entry.
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
                result = self.git.run(
                    ["worktree", "add", "-b", branch, worktree_path],
                    cwd=self.context.main_repo_root,
                )
            if result.returncode != 0:
                if self.logger:
                    self.logger.error(
                        f"Failed to create worktree for task {task_id}: {result.stderr}"
                    )
                return None
            manifest = self._load_manifest()
            manifest["worktrees"][str(task_id)] = {
                "branch": branch,
                "path": worktree_path,
                "task_file": branch,
            }
            self._save_manifest(manifest)
        self.log(f"Git: Created worktree for task {task_id} at '{worktree_path}'")
        return worktree_path

    def list_worktrees(self) -> list[dict]:
        manifest = self._load_manifest()
        worktrees = []
        for task_id, entry in manifest.get("worktrees", {}).items():
            path = entry.get("path")
            exists = bool(path and os.path.exists(path))
            worktrees.append(
                {
                    "task_id": task_id,
                    "branch": entry.get("branch"),
                    "path": path,
                    "exists": exists,
                }
            )
        return worktrees

    def remove_task_worktree(self, task_id, force: bool = False) -> bool:
        # Same transaction shape as create: prune can rewrite the manifest while
        # another agent is mid-mount, losing a freshly written entry.
        with store_lock(self.context):
            manifest = self._load_manifest()
            entry = manifest.get("worktrees", {}).get(str(task_id))
            if not entry:
                return False
            path = entry.get("path")
            branch = entry.get("branch")
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
            if branch:
                verify = self.git.run(
                    ["rev-parse", "--verify", branch], cwd=self.context.main_repo_root
                )
                if verify.returncode == 0:
                    if self.git.is_merged(branch, "main"):
                        self.git.run(
                            ["branch", "-d", branch], cwd=self.context.main_repo_root
                        )
                    elif force:
                        self.git.run(
                            ["branch", "-D", branch], cwd=self.context.main_repo_root
                        )
            del manifest["worktrees"][str(task_id)]
            self._save_manifest(manifest)
        self.log(f"Git: Removed worktree for task {task_id}")
        return True

    def prune_worktrees(self) -> list[str]:
        with store_lock(self.context):
            self.git.run(["worktree", "prune"], cwd=self.context.main_repo_root)
            manifest = self._load_manifest()
            stale = []
            for task_id, entry in list(manifest.get("worktrees", {}).items()):
                path = entry.get("path")
                if path and not os.path.exists(path):
                    stale.append(task_id)
            for task_id in stale:
                del manifest["worktrees"][str(task_id)]
            if stale:
                self._save_manifest(manifest)
        self.log(f"Pruned {len(stale)} stale worktree entries")
        return stale
