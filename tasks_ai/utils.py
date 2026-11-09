import fcntl
import os
import re
import shutil
import tempfile
import threading
from contextlib import contextmanager
from typing import Any

from tasks_ai.file_manager import FM

"""Store-wide write lock for the shared .tasks repo.

The store is one git repo written by every worktree and every agent session.
Git protects only its own index, so two read-modify-write transactions racing
each other (id allocation, manifest rewrite, undo) lose data with no error.
flock is per-open-file and is released by the kernel when a holder dies, so a
crashed agent never leaves a stale lock behind.

Reentrancy: a transaction may call another store operation (commit_task_paths
is the choke point for most mutations). Nested acquisitions of the same lock
in one thread would deadlock, so a second request in the same thread passes
straight through.
"""

_local = threading.local()

LOCK_NAME = ".hammer-lock"


@contextmanager
def store_lock(cli):
    """Hold the store-wide write lock for the duration of the block."""
    if getattr(_local, "depth", 0):
        _local.depth += 1
        try:
            yield
        finally:
            _local.depth -= 1
        return
    path = os.path.join(cli.tasks_path, LOCK_NAME)
    # No truncate and never unlink: another agent may be blocked on this
    # same inode right now.
    fd = os.open(path, os.O_CREAT | os.O_RDWR, 0o644)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        _local.depth = 1
        try:
            yield
        finally:
            _local.depth = 0
    finally:
        fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)


def derive_task_id(numeric_id, task_type: str, title: str) -> str:
    """The single naming rule for task id, branch, worktree dir and task folder.

    The slug is capped at 30 characters; create and doctor both derive from here
    so doctor never repairs a name it disagrees with.
    """
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", str(title).lower()).strip("-") or "task"
    return f"{numeric_id}-{task_type}-{slug[:30]}".strip("-")


def audit_worktree_manifest(manifest_worktrees, worktrees_base, live_paths):
    """Where the worktree manifest, git and the directory tree disagree.

    Hammer owns these paths: a task's worktree lives at exactly
    <worktrees_base>/<branch> and is registered in the manifest. Any other
    arrangement is drift a consumer would have to guess about, which is how
    stray directories and phantom paths get created.
    """
    findings = []
    live = {os.path.abspath(p) for p in live_paths}
    registered = set()
    for task_id, entry in sorted(manifest_worktrees.items()):
        path = entry.get("path") or ""
        branch = entry.get("branch") or ""
        if not path:
            findings.append(
                (
                    "GUARD_WORKTREE_PATH_DRIFT",
                    task_id,
                    f"manifest entry for task {task_id} has no worktree path",
                )
            )
            continue
        abs_path = os.path.abspath(path)
        registered.add(abs_path)
        expected = os.path.join(worktrees_base, branch)
        if abs_path != expected:
            findings.append(
                (
                    "GUARD_WORKTREE_PATH_DRIFT",
                    task_id,
                    f"worktree for task {task_id} is at '{abs_path}', expected '{expected}'",
                )
            )
        elif abs_path not in live:
            findings.append(
                (
                    "GUARD_WORKTREE_MISSING_WORKTREE",
                    task_id,
                    f"manifest path '{abs_path}' is not a git worktree",
                )
            )
    base = os.path.abspath(worktrees_base)
    if os.path.isdir(base):
        for name in sorted(os.listdir(base)):
            abs_path = os.path.join(base, name)
            if abs_path in registered:
                continue
            if os.path.isdir(abs_path) and os.path.exists(
                os.path.join(abs_path, ".git")
            ):
                continue
            findings.append(
                (
                    "GUARD_WORKTREE_UNREGISTERED",
                    None,
                    f"directory under {base} is not in the manifest: {abs_path}",
                )
            )
    return findings


def worktree_path_matches(wt_path: str, worktrees_base: str, branch: str) -> bool:
    """A task's worktree lives at exactly <worktrees_base>/<branch>.

    Anything else means the manifest, the branch and the directory on disk
    disagree, so no consumer can resolve the task by name.
    """
    return os.path.abspath(wt_path) == os.path.join(worktrees_base, branch)


def parse_filename(name: str) -> tuple[str, str]:
    """Parse task filename to extract type and slug."""
    if not name:
        return ("task", "")
    name_part = str(name).rsplit(".", 1)[0]
    if "-" in name_part:
        parts = name_part.split("-", 2)
        if len(parts) >= 3:
            return (parts[1], name_part)
    if "_" in name_part:
        parts = name_part.split("_", 1)
        return (parts[0], parts[1])
    return ("task", name_part)


def resolve_content(cli, value, lines=False):
    """Long-form flags accept a file path for bulk submission.

    A value naming an existing file is replaced by that file's contents, so a
    page-sized story or criteria list can come from a temp file instead of a
    shell arg (one item per line when lines=True, matching the list flags'
    own normalization). A path-shaped value that names nothing is an error:
    storing the path itself as prose would corrupt the task silently. Only a
    single token counts as path-shaped, because criteria routinely name
    ./hammer ... and a sentence is never a path; the cost of that rule is that
    an intended path containing spaces which does not exist is kept as prose.
    """
    def _read(v):
        if os.path.isfile(v):
            with open(v, "r", encoding="utf-8") as fh:
                content = fh.read()
            return content.splitlines() if lines else content
        # Whitespace means prose, not a path: criteria routinely name ./hammer ...
        # shortcut: an intended path containing spaces that is missing is stored as
        # prose instead of erroring.
        path_shaped = v.startswith(("/", "./", "../", "~")) or v.endswith(
            (".md", ".txt")
        )
        if path_shaped and not any(c.isspace() for c in v):
            cli.error("CONTENT_FILE_NOT_FOUND", path=v)
        return v

    if isinstance(value, list):
        resolved = [
            _read(v) if isinstance(v, str) and v.strip() else v for v in value
        ]
        if not lines:
            return resolved
        flat = []
        for item in resolved:
            flat.extend(item) if isinstance(item, list) else flat.append(item)
        return flat
    return _read(value) if isinstance(value, str) and value.strip() else value


def atomic_write(path: str, task_or_content: Any, fm=None):
    """
    Write task or raw content to path atomically.
    Supports both single-file tasks (.md) and multi-file task directories.
    """
    if hasattr(task_or_content, "metadata"):
        if path.endswith(".md"):
            if fm:
                fm.dump(task_or_content, path)
            else:
                from .file_manager import FM

                FM.dump(task_or_content, path)
        else:
            parent_dir = os.path.dirname(path.rstrip("/"))
            if parent_dir:
                os.makedirs(parent_dir, exist_ok=True)
            temp_dir = tempfile.mkdtemp(dir=parent_dir or ".")
            try:
                if os.path.isdir(path):
                    for item in os.listdir(path):
                        src_item = os.path.join(path, item)
                        dst_item = os.path.join(temp_dir, item)
                        if os.path.isdir(src_item):
                            shutil.copytree(src_item, dst_item)
                        else:
                            shutil.copy2(src_item, dst_item)
                if fm:
                    fm.dump(task_or_content, temp_dir)
                else:
                    from .file_manager import FM

                    FM.dump(task_or_content, temp_dir)
                if os.path.exists(path):
                    if os.path.isdir(path):
                        shutil.rmtree(path)
                    else:
                        os.remove(path)
                os.rename(temp_dir, path)
            except Exception:
                if os.path.exists(temp_dir):
                    shutil.rmtree(temp_dir)
                raise


def store_is_git(cli):
    """True when the store lives inside a git work tree.

    'tasks init' clones the store's own repo, but a store can also be a plain
    directory that was never initialised; those have no history to write to, so
    store writes are skipped there instead of failing the command.
    """
    res = cli._run_git(["rev-parse", "--is-inside-work-tree"], cwd=cli.tasks_path)
    return res.returncode == 0 and res.stdout.strip() == "true"


def _stageable(cli, path):
    """Relative path if git will accept it as an add pathspec, else None.

    A path that is neither on disk nor in the index is rejected by git, which
    would abort the whole store write.
    """
    rel = os.path.relpath(path, cli.tasks_path)
    if os.path.exists(path):
        return rel
    tracked = cli._run_git(["ls-files", "--error-unmatch", rel], cwd=cli.tasks_path)
    return rel if tracked.returncode == 0 else None


def commit_task_paths(cli, task_filepath, message, *extra_paths):
    """Stage and commit only these task paths in the shared store.

    The store is one git repo shared by every agent, so 'add --all' would commit
    other tasks' uncommitted records under our message. A failing add or commit
    must be fatal: a silent failure writes to disk but never to the record.
    extra_paths covers the rest of a move: the old state folder, recorded as a
    deletion, and any sibling artifact of the task record.
    """
    if not store_is_git(cli):
        return
    # Every store mutation funnels here, so this is the single place the
    # store-wide lock is taken; inner mutations pass through re-entrantly.
    with store_lock(cli):
        specs = [
            s for s in (_stageable(cli, p) for p in (task_filepath, *extra_paths)) if s
        ]
        if not specs:
            return
        add = cli._run_git(["add", "--", *specs], cwd=cli.tasks_path)
        if add.returncode != 0:
            cli.error(
                "STORE_WRITE_FAIL",
                message=message,
                detail=(add.stderr or "").strip() or "git add failed",
            )
        commit = cli._run_git(
            ["commit", "--allow-empty", "-m", message], cwd=cli.tasks_path
        )
        if commit.returncode != 0:
            cli.error(
                "STORE_WRITE_FAIL",
                message=message,
                detail=(commit.stderr or "").strip() or "git commit failed",
            )


def sync_task_content(cli, filepath, task, is_final=False) -> bool:
    """Sync task metadata with current branch commits, notes and store changes."""
    from .constants import CURRENT_TASK_FILENAME

    if not filepath:
        return False
    filepath_str = str(filepath)
    tn = os.path.basename(filepath_str)
    _, branch = parse_filename(tn)
    updated = False
    main_root = cli.context.main_repo_root
    default_branch = cli.git.get_default_branch()
    if default_branch:
        res = cli._run_git(
            ["log", branch, f"^{default_branch}", "--oneline"], cwd=main_root
        )
        commits = res.stdout.strip() if res.returncode == 0 else ""
        if commits:
            task.parts["commits"] = commits
            updated = True
    dump_path = os.path.join(filepath_str, CURRENT_TASK_FILENAME)
    if os.path.exists(dump_path):
        dump = FM.load(dump_path)
        if dump.parts.get("content"):
            task.parts["notes"] = dump.parts["content"]
            updated = True
    # The task record lives in the shared store, which the main repo ignores, so
    # pending changes are detected in the store repo and part files are read
    # straight off disk instead of diffed against the main repo.
    rel_task_dir = os.path.relpath(filepath_str, cli.tasks_path)
    if store_is_git(cli):
        res_status = cli._run_git(
            ["status", "--porcelain", "--", rel_task_dir], cwd=cli.tasks_path
        )
        if res_status.returncode != 0:
            cli.error(
                "STORE_WRITE_FAIL",
                message="inspect task record",
                detail=(res_status.stderr or "").strip() or "git status failed",
            )
        if res_status.stdout.strip():
            updated = True
    if os.path.isdir(filepath_str):
        for entry in sorted(os.listdir(filepath_str)):
            if not entry.endswith(".md") or entry == CURRENT_TASK_FILENAME:
                continue
            try:
                with open(
                    os.path.join(filepath_str, entry), "r", encoding="utf-8"
                ) as f:
                    content = f.read()
            except OSError:
                continue
            part_name = entry[:-3]
            if task.parts.get(part_name) != content:
                task.parts[part_name] = content
                updated = True
    return updated


def perform_move(cli, task, current_state, new_status, filepath):
    """Execute the physical move of task files on disk, including auxiliary artifacts."""
    from .constants import STATE_FOLDERS
    from .file_manager import FM

    if not filepath:
        cli.error("Invalid task path.")
    filepath_str = str(filepath)
    sync_task_content(cli, filepath_str, task, is_final=new_status == "ARCHIVED")
    task.metadata.pop("St", None)
    fname = task.metadata.get("Br") or str(task.metadata.get("Id", "unknown-task"))
    new_filepath = os.path.join(cli.tasks_path, STATE_FOLDERS[new_status], fname)
    if filepath_str != new_filepath:
        atomic_write(new_filepath, task, fm=FM)
        task_folder_name = os.path.basename(filepath_str)
        patches_src = os.path.join(
            cli.tasks_path, "review", task_folder_name, "patches"
        )
        patches_dst = os.path.join(
            cli.tasks_path, STATE_FOLDERS[new_status], fname, "patches"
        )
        if os.path.exists(patches_src):
            os.makedirs(os.path.dirname(patches_dst), exist_ok=True)
            shutil.move(patches_src, patches_dst)
            cli.log(f"Migrated patches directory to {new_status}")
        audit_src = os.path.join(cli.tasks_path, "review", f"{task_folder_name}.audit")
        audit_dst = os.path.join(
            cli.tasks_path, STATE_FOLDERS[new_status], f"{fname}.audit"
        )
        if os.path.exists(audit_src):
            shutil.move(audit_src, audit_dst)
            cli.log(f"Migrated audit file to {new_status}")
        if os.path.exists(filepath_str):
            if os.path.isdir(filepath_str):
                shutil.rmtree(filepath_str)
            else:
                os.remove(filepath_str)
    else:
        atomic_write(new_filepath, task, fm=FM)
    cli._append_log(new_filepath, f"{current_state}->{new_status}")
    return task


def has_path(start_id: str, target_id: str, tasks_path: str, fm, visited=None) -> bool:
    """Check if there's a path from start_id to target_id via BlockedBy links."""
    import json

    from .constants import STATE_FOLDERS

    if visited is None:
        visited = set()
    if start_id in visited:
        return False
    visited.add(start_id)
    task_file = None
    for state_folder in STATE_FOLDERS.values():
        state_path = os.path.join(tasks_path, state_folder)
        if not os.path.exists(state_path):
            continue
        for task_dir in os.listdir(state_path):
            task_dir_path = os.path.join(state_path, task_dir)
            if not os.path.isdir(task_dir_path):
                continue
            meta_file = os.path.join(task_dir_path, "meta.json")
            if os.path.exists(meta_file):
                try:
                    with open(meta_file, "r") as f:
                        meta = json.load(f)
                    if str(meta.get("Id")) == str(start_id):
                        task_file = task_dir_path
                        break
                except (OSError, json.JSONDecodeError):
                    pass
        if task_file:
            break
    if not task_file:
        return False
    try:
        task = fm.load(task_file)
        bl = task.metadata.get("Bl", [])
        if not isinstance(bl, list):
            bl = []
        for blocker_dir in bl:
            blocker_id = (
                blocker_dir.split("-")[0] if "-" in blocker_dir else blocker_dir
            )
            if str(blocker_id) == str(target_id):
                return True
            if has_path(blocker_id, target_id, tasks_path, fm, visited):
                return True
    except Exception:  # noqa: BLE001, S110
        pass
    return False
