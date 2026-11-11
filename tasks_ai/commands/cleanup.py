def run(cli, dry_run=False, yes=False):
    """Execution logic for 'tasks cleanup' - removes stale worktrees and merged branches."""
    current_branch = cli.git.get_current_branch()
    default_branch = cli.git.get_default_branch()
    if not default_branch:
        cli.error("NO_DEFAULT_BRANCH", current_branch=current_branch)
        return
    if current_branch not in (default_branch, "staging", "testing"):
        if cli.as_json:
            cli.finish(
                {
                    "error": f"Cleanup must be run from {default_branch}, staging, or testing branch. Currently on '{current_branch}'."
                }
            )
        else:
            cli.error(
                "CLEANUP_BRANCH_INVALID",
                default_branch=default_branch,
                current_branch=current_branch,
            )
        return

    main_sha = cli.git.run(["rev-parse", default_branch]).stdout.strip()
    if not main_sha:
        cli.finish({"cleaned": [], "archived": [], "count": 0})
        return

    cleaned = []
    archived = []

    # 1. Prune stale worktree entries from the manifest
    pruned = cli.git.worktrees.prune_worktrees()
    for task_id in pruned:
        if dry_run:
            cli.console("worktree", "would_prune", f"task {task_id}")
        else:
            cli.console("worktree", "pruned", f"task {task_id}")
        cleaned.append(f"worktree:{task_id}")

    # 2. Clean up merged branches (backed by worktrees)
    branches = (
        cli.git.run(
            ["branch", "--format", "%(refname:short)"], cwd=cli.context.main_repo_root
        )
        .stdout.strip()
        .splitlines()
    )

    for branch in branches:
        if branch in (default_branch, "staging", "testing"):
            continue
        res = cli.git.run(
            ["merge-base", "--is-ancestor", branch, default_branch],
            cwd=cli.context.main_repo_root,
        )
        if res.returncode == 0:
            status_res = cli.git.run(
                ["status", "--porcelain", branch], cwd=cli.context.main_repo_root
            )
            if status_res.stdout.strip():
                if dry_run:
                    cleaned.append(branch)
                else:
                    print(
                        f"⚠️ Skipping {branch}: Uncommitted/untracked changes detected. Clean up work first."
                    )
                continue
            if dry_run:
                cleaned.append(branch)
            else:
                cli.git.run(["branch", "-d", branch], cwd=cli.context.main_repo_root)
                cleaned.append(branch)

    # 3. Remove worktrees for merged task branches
    for wt in cli.git.worktrees.list_worktrees():
        branch = wt.get("branch")
        if not branch:
            continue
        if branch in (default_branch, "staging", "testing"):
            continue
        if cli.git.is_merged(branch, default_branch, cwd=cli.context.main_repo_root):
            if dry_run:
                cli.console("worktree", "would_remove", branch)
            else:
                cli.git.worktrees.remove_task_worktree(wt["task_id"], force=False)
                cli.console("worktree", "removed", branch)

    if not dry_run:
        cli.log(f"Cleaned: {', '.join(cleaned) if cleaned else 'nothing'}")
    cli.finish(
        {
            "cleaned": cleaned,
            "archived": archived,
            "count": len(cleaned) + len(archived),
        }
    )
