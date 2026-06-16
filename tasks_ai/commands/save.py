def run(cli, branch="tasks", fatal=True):
    """Internal: push current .tasks worktree branch to remote."""
    return cli.git.push_tasks_branch(branch=branch, fatal=fatal)
