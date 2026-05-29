def run(cli, dry_run=False, yes=False):
    """Execution logic for 'tasks cleanup'."""
    current_branch = cli._run_git(["rev-parse", "--abbrev-ref", "HEAD"]).stdout.strip()
    default_branch = cli._get_default_branch()

    if current_branch not in ("main", "master", "staging", "testing"):
        if cli.as_json:
            cli.finish(
                {
                    "error": f"Cleanup must be run from {default_branch}, staging, or testing branch. Currently on '{current_branch}'."
                }
            )
        else:
            print(
                f"Error: Cleanup must be run from {default_branch}, staging, or testing branch.\nCurrently on: {current_branch}"
            )
        return

    main_sha = cli._run_git(["rev-parse", default_branch]).stdout.strip()
    if not main_sha:
        cli.finish({"cleaned": [], "archived": [], "count": 0})
        return

    branches = (
        cli._run_git(["branch", "--format", "%(refname:short)"])
        .stdout.strip()
        .splitlines()
    )

    cleaned = []
    archived = []

    for branch in branches:
        if branch in (default_branch, "staging", "testing"):
            continue

        # Check if merged
        res = cli._run_git(["merge-base", "--is-ancestor", branch, default_branch])
        if res.returncode == 0:
            if dry_run:
                cleaned.append(branch)
            else:
                cli._run_git(["branch", "-d", branch])
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
