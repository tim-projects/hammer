import os

from ..cli_errors import PipelineMergeConflict
from ..file_manager import FM


def _sync_or_warn(cli, wt_path, branch):
    """Bring the mounted worktree up to date with the default branch.

    A worktree with no work of its own is merged (a fast-forward, so it cannot
    conflict). A worktree with local work is never merged here -- that would
    write conflict markers into the user's files -- so the conflicts that a
    later promotion would hit are reported instead.
    """
    default_branch = cli.git.get_default_branch()
    if not default_branch:
        cli.console("worktree", "sync", "skipped (no default branch)")
        return

    merge_source = cli.git.resolve_merge_source(default_branch)
    if not merge_source:
        cli.console("worktree", "sync", "skipped (no main/master ref)")
        return

    if not cli.git.has_local_work(wt_path, merge_source):
        try:
            cli.git.sync_worktree(wt_path, default_branch, branch)
        except PipelineMergeConflict:
            cli.error("WORKTREE_MERGE_CONFLICT", branch=branch, default=default_branch)
        cli.console("worktree", "sync", f"{merge_source} -> complete")
        return

    conflicts = cli.git.conflicting_files(wt_path, merge_source)
    if conflicts is None:
        cli.console("worktree", "conflicts", "could not check (old git)")
    elif conflicts:
        cli.console(
            "worktree",
            "conflicts",
            f"{len(conflicts)} file(s) conflict with {merge_source}:",
        )
        for path in conflicts:
            cli.console("conflict", "file", path)
        cli.log(f"Resolve in the worktree, then re-run: git merge {merge_source}")
    else:
        cli.console("worktree", "sync", f"up to date with {merge_source}")


def run(cli, task_id):
    """Execution logic for 'tasks mount <id>'."""
    filepath, _ = cli.find_task(task_id)
    if not filepath:
        cli.error("TASK_NOT_FOUND", filename=str(task_id))

    task = FM.load(str(filepath))
    branch = task.metadata.get("Br", "")
    if not branch:
        branch = str(task_id)

    wt_path = cli.git.worktrees.create_task_worktree(
        str(task.metadata.get("Id", task_id)), branch
    )
    if not wt_path:
        cli.error("Failed to create worktree for task.")

    _sync_or_warn(cli, wt_path, branch)

    cli.log(f"Worktree mounted at: {wt_path}")
    cli.log(f"Run: cd {wt_path}")

    cli.finish(
        {
            "id": task.metadata.get("Id"),
            "task_id": branch,
            "branch": branch,
            "worktree_path": wt_path,
            "cwd": os.getcwd(),
        }
    )
