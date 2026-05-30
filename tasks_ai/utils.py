from tasks_ai.file_manager import FM
import os
import shutil
import tempfile
from typing import Tuple, Any


def parse_filename(name: str) -> Tuple[str, str]:
    """Parse task filename to extract type and slug."""
    if not name:
        return "task", ""
    name_part = str(name).rsplit(".", 1)[0]
    if "-" in name_part:
        parts = name_part.split("-", 2)
        if len(parts) >= 3:
            return parts[1], name_part
    if "_" in name_part:
        parts = name_part.split("_", 1)
        return parts[0], parts[1]
    return "task", name_part


def atomic_write(path: str, task_or_content: Any, fm=None):
    """
    Write task or raw content to path atomically.
    Supports both single-file tasks (.md) and multi-file task directories.
    """
    if hasattr(task_or_content, "metadata"):
        # It's a Task object
        if path.endswith(".md"):
            if fm:
                fm.dump(task_or_content, path)
            else:
                from .file_manager import FM

                FM.dump(task_or_content, path)
        else:
            # Directory-based task
            parent_dir = os.path.dirname(path.rstrip("/"))
            if parent_dir:
                os.makedirs(parent_dir, exist_ok=True)
            temp_dir = tempfile.mkdtemp(dir=parent_dir or ".")
            try:
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
            except Exception as e:
                if os.path.exists(temp_dir):
                    shutil.rmtree(temp_dir)
                raise e
    else:
        # It's raw content (string or bytes)
        content = task_or_content
        if not isinstance(content, str):
            try:
                content = content.decode("utf-8")
            except (AttributeError, UnicodeDecodeError):
                content = str(content)

        dir_name = os.path.dirname(path)
        if dir_name:
            os.makedirs(dir_name, exist_ok=True)

        fd, temp_path = tempfile.mkstemp(dir=dir_name or ".", text=True)
        try:
            with os.fdopen(fd, "w") as f:
                f.write(content)
            os.replace(temp_path, path)
        except Exception as e:
            if os.path.exists(temp_path):
                os.remove(temp_path)
            raise e


def sync_task_content(cli, filepath, task, is_final=False) -> bool:
    """Sync task metadata with current branch commits and notes."""
    from .constants import CURRENT_TASK_FILENAME

    if not filepath:
        return False
    filepath_str = str(filepath)
    tn = os.path.basename(filepath_str)
    _, branch = parse_filename(tn)
    updated = False

    default_branch = "main"
    for b in ["main", "master"]:
        if cli._run_git(["rev-parse", "--verify", b]).returncode == 0:
            default_branch = b
            break

    res = cli._run_git(["log", branch, f"^{default_branch}", "--oneline"])
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

    # Detect manual edits
    rel_task_dir = os.path.relpath(filepath_str, cli.root)
    res_unstaged = cli._run_git(
        ["diff", "--name-only", "--", rel_task_dir], cwd=cli.root
    )
    res_staged = cli._run_git(
        ["diff", "--cached", "--name-only", "--", rel_task_dir], cwd=cli.root
    )

    changed_files = set()
    if res_unstaged.returncode == 0 and res_unstaged.stdout.strip():
        changed_files.update(res_unstaged.stdout.strip().splitlines())
    if res_staged.returncode == 0 and res_staged.stdout.strip():
        changed_files.update(res_staged.stdout.strip().splitlines())

    for rel_path in changed_files:
        if not rel_path.endswith(".md"):
            continue
        fname = os.path.basename(rel_path)
        if fname == CURRENT_TASK_FILENAME:
            continue
        part_name = fname[:-3]
        abs_path = os.path.join(cli.root, rel_path)
        try:
            with open(abs_path, "r", encoding="utf-8") as f:
                content = f.read()
            if task.parts.get(part_name) != content:
                task.parts[part_name] = content
                updated = True
        except Exception:
            pass

    return updated


def perform_move(cli, task, current_state, new_status, filepath):
    """Execute the physical move of task files on disk."""
    from .file_manager import FM
    from .constants import STATE_FOLDERS

    if not filepath:
        cli.error("Invalid task path.")
    filepath_str = str(filepath)
    sync_task_content(cli, filepath_str, task, is_final=(new_status == "ARCHIVED"))
    task.metadata.pop("St", None)
    fname = os.path.basename(filepath_str)
    new_filepath = os.path.join(cli.tasks_path, STATE_FOLDERS[new_status], fname)

    # Move and cleanup
    atomic_write(new_filepath, task, fm=FM)
    if os.path.exists(filepath_str):
        if os.path.isdir(filepath_str):
            shutil.rmtree(filepath_str)
        else:
            os.remove(filepath_str)
    cli._append_log(new_filepath, f"{current_state}->{new_status}")
    return task
    return task


def has_path(start_id: str, target_id: str, tasks_path: str, fm, visited=None) -> bool:
    """Check if there's a path from start_id to target_id via BlockedBy links."""
    from .constants import STATE_FOLDERS
    import json

    if visited is None:
        visited = set()

    if start_id in visited:
        return False
    visited.add(start_id)

    # Find the task file for start_id
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
                except (json.JSONDecodeError, IOError):
                    pass
        if task_file:
            break

    if not task_file:
        return False

    # Load the task and check its BlockedBy
    try:
        task = fm.load(task_file)
        bl = task.metadata.get("Bl", [])
        if not isinstance(bl, list):
            bl = []

        # Check direct links
        for blocker_dir in bl:
            # Extract task ID from directory name (format: {id}-{type}-{title})
            blocker_id = (
                blocker_dir.split("-")[0] if "-" in blocker_dir else blocker_dir
            )
            if str(blocker_id) == str(target_id):
                return True
            # Recursively check indirect paths
            if has_path(blocker_id, target_id, tasks_path, fm, visited):
                return True
    except Exception:
        pass

    return False
