def run(cli, dry_run=False, yes=False):
    """Execution logic for 'tasks cleanup'."""
    current_branch = cli.git.get_current_branch()
    default_branch = cli.git.get_default_branch()

    if current_branch not in ("main", "master", "staging", "testing"):
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

    branches = (
        cli.git.run(["branch", "--format", "%(refname:short)"])
        .stdout.strip()
        .splitlines()
    )

    cleaned = []
    archived = []

    for branch in branches:
        if branch in (default_branch, "staging", "testing"):
            continue

        # Check if merged
        res = cli.git.run(["merge-base", "--is-ancestor", branch, default_branch])
        if res.returncode == 0:
            # SAFETY CHECK: Verify branch is clean
            status_res = cli.git.run(["status", "--porcelain", branch])
            if status_res.stdout.strip():
                print(
                    f"⚠️ Skipping {branch}: Uncommitted/untracked changes detected. Clean up work first."
                )
                continue

            if dry_run:
                cleaned.append(branch)
            else:
                cli.git.run(["branch", "-d", branch])
                cleaned.append(branch)

    if not dry_run:
        cli.log(f"Cleaned branches: {', '.join(cleaned)}")

    cli.finish(
        {
            "cleaned": cleaned,
            "archived": archived,
            "count": len(cleaned) + len(archived),
        }
    )
