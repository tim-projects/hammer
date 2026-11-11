import os
import subprocess


class DevRepoUnavailable(Exception):
    """Dev mode cannot be isolated: no repo to act on, and the real one is off limits."""


class ProjectContext:
    """
    Central authority for path resolution and environment detection.
    Supports standard git repositories and git worktrees.
    """

    def __init__(self, dev: bool = False, tasks_dir_override: str | None = None):
        self.dev = dev
        self.repo_root = self._get_git_root()
        self.main_repo_root = self._get_main_repo_root()
        self.is_worktree = os.path.normpath(self.repo_root) != os.path.normpath(
            self.main_repo_root
        )
        # The repo the command was invoked from, before dev swaps it out. The
        # store must be cloned from HERE: a clone has no local 'tasks' branch
        # (only origin/tasks), so cloning the store from the dev repo itself
        # fails 'clone --branch tasks'.
        self.invoked_repo_root = self.main_repo_root
        if self.dev:
            dev_store = os.environ.get("HAMMER_DEV_TASKS_DIR", "/tmp/.tasks")
            # A dev store must never be the real one: 'init --force' backs up and
            # rmtree's whatever tasks_path resolves to, so a variable aimed at the
            # production store (inherited env, a leaked gate export, a scratch
            # script running at import) re-clones the real store from a throwaway
            # repo and loses every commit that was not pushed.
            production_store = os.path.join(self.main_repo_root, ".tasks")
            if os.path.realpath(dev_store) == os.path.realpath(production_store):
                raise DevRepoUnavailable(
                    f"HAMMER_DEV_TASKS_DIR points at the real store "
                    f"({production_store}); dev mode needs an isolated store, "
                    "for example /tmp/.tasks"
                )
            self.tasks_path = dev_store
            # Dev mode swaps the store AND the repo it acts on. Binding only the
            # store leaves every git write on the real repo: dev-created branches
            # and worktrees collide with real task ids and the guard then rejects
            # the real promotion.
            self.repo_root = self._ensure_dev_repo(self.main_repo_root, self.tasks_path)
            self.main_repo_root = self.repo_root
            self.is_worktree = False
        elif tasks_dir_override:
            if os.path.isabs(tasks_dir_override):
                self.tasks_path = tasks_dir_override
            else:
                self.tasks_path = os.path.join(self.main_repo_root, tasks_dir_override)
        else:
            self.tasks_path = os.path.join(self.main_repo_root, ".tasks")

    def _get_git_root(self) -> str:
        """Get the top-level directory of the current git repository/worktree."""
        try:
            return (
                subprocess.check_output(
                    ["git", "rev-parse", "--show-toplevel"], stderr=subprocess.DEVNULL
                )
                .decode()
                .strip()
            )
        except subprocess.CalledProcessError:
            return os.getcwd()

    def _get_main_repo_root(self) -> str:
        """Get the root directory of the main repository, even if in a worktree."""
        try:
            common_dir = (
                subprocess.check_output(
                    ["git", "rev-parse", "--git-common-dir"], stderr=subprocess.DEVNULL
                )
                .decode()
                .strip()
            )
            if not os.path.isabs(common_dir):
                abs_common = os.path.abspath(common_dir)
                return os.path.dirname(abs_common)
            return os.path.dirname(common_dir)
        except subprocess.CalledProcessError:
            return self._get_git_root()

    @staticmethod
    def dev_repo_path(tasks_path: str) -> str:
        """Throwaway repo of a dev store, keyed on the store so it is reused."""
        return os.path.abspath(tasks_path) + "-repo"

    def _ensure_dev_repo(self, source: str, tasks_path: str) -> str:
        """Clone `source` into the dev repo, once per HAMMER_DEV_TASKS_DIR.

        A dev invocation cannot be isolated in place: worktrees and branches
        must live somewhere the real repo cannot see. When the clone cannot be
        made (not a git repository, empty history, unwritable path) dev mode
        refuses rather than silently falling back to the real repo.
        """
        path = self.dev_repo_path(tasks_path)
        if os.path.isdir(os.path.join(path, ".git")):
            return path
        os.makedirs(os.path.dirname(path), exist_ok=True)
        result = subprocess.run(
            ["git", "clone", "--quiet", source, path],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            raise DevRepoUnavailable(
                f"detached dev repo could not be cloned from {source} "
                f"({result.stderr.strip() or 'unknown error'})"
            )
        # An empty source has no HEAD at all: give the dev repo a root commit so
        # worktrees and branches can be created from it.
        seeded = subprocess.run(
            ["git", "-C", path, "rev-parse", "--verify", "HEAD"],
            capture_output=True,
            text=True,
            check=False,
        )
        if seeded.returncode != 0:
            root = subprocess.run(
                [
                    "git",
                    "-C",
                    path,
                    "commit",
                    "--allow-empty",
                    "--quiet",
                    "-m",
                    "dev repo root",
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            if root.returncode != 0:
                raise DevRepoUnavailable(
                    f"detached dev repo at {path} could not be seeded "
                    f"({root.stderr.strip() or 'unknown error'})"
                )
        # Mirror the source's local branches, otherwise a dev run can only see
        # the checked-out branch: worktree, branch and guard checks read local
        # refs, and a dev store is seeded from the 'tasks' branch.
        default = subprocess.run(
            ["git", "-C", path, "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True,
            text=True,
            check=False,
        ).stdout.strip()
        steps = [
            # Detach first: git refuses to fetch into the checked-out branch.
            ["checkout", "--quiet", "--detach"],
            ["fetch", "--quiet", "origin", "+refs/heads/*:refs/heads/*"],
        ]
        if default:
            steps.append(["checkout", "--quiet", default])
        for step in steps:
            mirror = subprocess.run(
                ["git", "-C", path] + step,
                capture_output=True,
                text=True,
                check=False,
            )
            if mirror.returncode != 0:
                raise DevRepoUnavailable(
                    f"detached dev repo at {path} could not mirror branches from "
                    f"{source} ({mirror.stderr.strip() or 'unknown error'})"
                )
        return path

    def resolve_path(self, *paths: str) -> str:
        """Resolve a path relative to the main repo root."""
        return os.path.join(self.main_repo_root, *paths)

    def resolve_worktree_path(self, *paths: str) -> str:
        """Resolve a path relative to the current worktree/repo root."""
        return os.path.join(self.repo_root, *paths)

    def __repr__(self):
        return f"ProjectContext(repo_root={self.repo_root}, main_repo_root={self.main_repo_root}, is_worktree={self.is_worktree}, tasks_path={self.tasks_path})"
