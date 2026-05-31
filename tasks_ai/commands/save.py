import os


def run(cli, branch="tasks", fatal=True):
    """Internal: push current .tasks worktree branch to remote."""
    if not os.path.exists(cli.tasks_path):
        if fatal:
            cli.error("INIT_REQUIRED")
        return None

    remotes = cli._run_git(["remote", "-v"], cwd=cli.tasks_path)
    if not remotes.stdout.strip():
        if cli.dev or cli.yes:
            current = cli._run_git(
                ["rev-parse", "--abbrev-ref", "HEAD"], cwd=cli.tasks_path
            ).stdout.strip()
            cli.log("No remote configured - skipping push (local-only mode)")
            return {"branch": branch, "remote": None, "from_branch": current}
        else:
            if fatal:
                cli.error("NO_REMOTE_CONFIGURED")
            return None

    current = cli._run_git(
        ["rev-parse", "--abbrev-ref", "HEAD"], cwd=cli.tasks_path
    ).stdout.strip()
    push_result = cli._run_git(
        ["push", "-u", "origin", f"{current}:refs/heads/{branch}"], cwd=cli.tasks_path
    )

    if push_result.returncode != 0:
        if fatal:
            cli.error("PUSH_FAIL", stderr=push_result.stderr)
        else:
            cli.log(f"Warning: {push_result.stderr}")
            return None

    cli.log(f"Pushed .tasks ({current}) to origin/{branch}")
    return {"branch": branch, "remote": "origin", "from_branch": current}
