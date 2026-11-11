#!/usr/bin/env python3
"""
repo - Repository and pipeline branch management
Usage: repo <command> [args]

Commands:
  merge <src> <dest>        Merge <src> into <dest> (exit 0 = merged)
  promote <branch>          DEPRECATED: promote a branch (use 'tasks move')
  demote <task-id> <state>  Demote a task to an earlier state (exit 0 = demoted)
  sync                      Sync testing -> staging -> default branch (exit 0 = synced)
  commit <message>          Validate, commit, and optionally push (exit 0 = committed)
  git <args>                Forward <args> to git
  status                    Show git status (read-only)
  check-merged <branch>     Exit 0 if <branch> reached the default branch (read-only)
  check-merged-testing <b>  Exit 0 if <branch> reached testing (read-only)
  branch list               List local branches (read-only)
  branch create <name>      Create and switch to <name>
  branch delete <name>      Delete <name>
  branch exists <name>      Exit 0 if <name> exists (read-only)

Global flags:
  -y, --yes   Auto-confirm prompts
  -q, --quiet Suppress output (for scripting)
  -j, --json  JSON output
  --dev       Use /tmp/.tasks instead of the project store (isolated)

Examples:
  hammer repo status
  hammer repo merge 250 testing
  hammer repo check-merged current
  hammer repo branch create 400-task-new-thing
"""

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

sys.path.append(os.getcwd())
try:
    from tasks_ai.cli import TasksCLI
    from tasks_ai.constants import STATE_FOLDERS
    from tasks_ai.help_text import agent_epilog
except ImportError:
    TasksCLI = None
    STATE_FOLDERS = {}
    agent_epilog = None
SCRIPT_DIR = Path(__file__).parent.resolve()
RED = "\033[0;31m"
GREEN = "\033[0;32m"
YELLOW = "\033[1;33m"
CYAN = "\033[0;36m"
NC = "\033[0m"
FLAGS = {"yes": False, "quiet": False, "json": False, "dev": False}


def get_default_branch():
    """The repo's actual default branch: origin/HEAD, then the first existing
    of main/master - never assume 'main' exists."""
    result = run(
        ["git", "symbolic-ref", "--quiet", "--short", "refs/remotes/origin/HEAD"],
        check=False,
        capture=True,
    )
    if result.returncode == 0 and result.stdout.strip():
        return result.stdout.strip()
    for branch in ("main", "master"):
        if branch_exists(branch):
            return branch
    return "main"


def pipeline():
    """Pipeline stages in promotion order, ending at the default branch."""
    return ["testing", "staging", get_default_branch()]


def get_primary_remote():
    try:
        result = subprocess.run(
            ["git", "remote"], capture_output=True, text=True, check=True
        )
        remotes = result.stdout.split()
        if not remotes:
            return "origin"
        return "origin" if "origin" in remotes else remotes[0]
    except Exception:  # noqa: BLE001
        return "origin"


PRIMARY_REMOTE = get_primary_remote()


def log(msg):
    if not FLAGS["quiet"] and not FLAGS["json"]:
        print(f"{GREEN}[repo]{NC} {msg}")


def warn(msg):
    if not FLAGS["quiet"] and not FLAGS["json"]:
        print(f"{YELLOW}[repo] WARN:{NC} {msg}")


def error(msg, hint=None):
    if hint:
        msg = f"{msg} | HINT: {hint}"
    if FLAGS["json"]:
        print(json.dumps({"success": False, "error": msg}))
    else:
        print(f"{RED}[repo] ERROR:{NC} {msg}")
    sys.exit(1)


def info(msg):
    if not FLAGS["quiet"] and not FLAGS["json"]:
        print(f"{CYAN}[repo]{NC} {msg}")


def find_project_root(start_path=None):
    if start_path is None:
        start_path = os.getcwd()
    current = os.path.abspath(start_path)
    while True:
        if os.path.isdir(os.path.join(current, ".git")):
            return current
        if os.path.isdir(os.path.join(current, ".tasks")):
            return current
        parent = os.path.dirname(current)
        if parent == current:
            break
        current = parent
    return Path(__file__).parent.resolve()


def repo_root():
    """Repo every git operation of this tool acts on.

    Dev mode uses the throwaway repo the tasks CLI binds to: falling back to the
    repo the command was invoked from is what leaked dev branches and merges.
    """
    if FLAGS["dev"]:
        from tasks_ai.context import DevRepoUnavailable, ProjectContext

        try:
            return ProjectContext(dev=True).repo_root
        except DevRepoUnavailable as exc:
            error(f"{exc}. Run without --dev to act on the real repository.")
    return find_project_root()


def run(cmd, check=True, capture=False, env=None, cwd=None, quiet=False):
    project_root = repo_root()
    capture = capture or quiet or FLAGS["json"]
    if FLAGS["dev"] and cmd[:1] == ["git"] and cmd[1:2] == ["push"]:
        # The dev repo's remote is the repo it was cloned from: a push from here
        # would move real refs, which is exactly what dev mode must not do.
        warn("Dev mode: push to remote skipped (throwaway repo).")
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")
    try:
        # Mark hammer's own git calls: the pre-merge-commit hook must not block
        # 'repo merge'/'repo sync', only a user's raw 'git merge'.
        call_env = os.environ.copy()
        call_env["HAMMER_INTERNAL_CALL"] = "1"
        if env:
            call_env.update(env)
        return subprocess.run(
            cmd,
            check=check,
            capture_output=capture,
            text=True,
            env=call_env,
            cwd=cwd or project_root,
        )
    except subprocess.CalledProcessError as e:
        err_msg = e.stderr if capture else ""
        error(f"Command failed: {' '.join(cmd)}\n{err_msg}")
        raise


def get_current_branch():
    return run(
        ["git", "rev-parse", "--abbrev-ref", "HEAD"], capture=True
    ).stdout.strip()


def prompt_yes_no(prompt):
    if FLAGS["yes"]:
        return True
    try:
        while True:
            res = input(f"{prompt} [y/n] ").strip().lower()
            if res in ["y", "yes"]:
                return True
            if res in ["n", "no"]:
                return False
    except EOFError:
        error("EOFError: stdin closed. Use -y flag to auto-confirm.")


class ToolRunner:
    def run_validation(self, fix=False, dev=False, cwd=None):
        git_root = cwd or repo_root()
        local_check = os.path.join(git_root, "check.py")
        cmd = [sys.executable, local_check, "all"]
        if fix:
            cmd.append("--fix")
        if dev:
            cmd.append("--dev")
        result = subprocess.run(cmd, capture_output=True, text=True, cwd=git_root)  # noqa: PLW1510
        if result.returncode != 0:
            warn("Validation failed")
            if result.stdout:
                print(result.stdout)
            if result.stderr:
                print(result.stderr, file=sys.stderr)
            return False
        log("✅ Validation passed")
        return True


def branch_exists(name):
    return (
        run(
            ["git", "rev-parse", "--verify", name], check=False, capture=True
        ).returncode
        == 0
    )


def check_remote_exists():
    result = run(
        ["git", "remote", "get-url", PRIMARY_REMOTE], check=False, capture=True
    )
    if result.returncode != 0:
        if FLAGS["yes"]:
            warn(f"No '{PRIMARY_REMOTE}' remote - continuing in local-only mode")
            return False
        warn(f"No '{PRIMARY_REMOTE}' remote - continuing in local-only mode")
        return False
    return True


def check_merged_to_main(branch):
    if not branch_exists(branch):
        error(f"Branch {branch} does not exist.")
    result = run(
        ["git", "merge-base", "--is-ancestor", branch, get_default_branch()],
        check=False,
        capture=True,
    )
    return result.returncode == 0


def check_merged_to_testing(branch):
    if not branch_exists(branch):
        error(f"Branch {branch} does not exist.")
    result = run(
        ["git", "merge-base", "--is-ancestor", branch, "testing"],
        check=False,
        capture=True,
    )
    return result.returncode == 0


def cmd_merge(src_input, target_input):
    src = resolve_branch(src_input)
    target = resolve_branch(target_input)

    # Identify if src is a task branch
    task_id = src.split("-")[0] if src.split("-")[0].isdigit() else None
    cli = (
        TasksCLI(quiet=FLAGS["quiet"], dev=FLAGS["dev"], yes=FLAGS["yes"])
        if TasksCLI
        else None
    )

    if task_id and cli:
        path, _ = cli.find_task(task_id)
        if path:
            # Map git branch target to pipeline status
            pipeline_to_status = {
                "testing": "TESTING",
                "staging": "STAGING",
                get_default_branch(): "DONE",
            }
            new_status = pipeline_to_status.get(target)
            if new_status:
                info(
                    f"Task branch detected: {src}. Routing merge through 'tasks move {task_id} {new_status}'..."
                )
                cli.move(task_id, new_status, yes=FLAGS["yes"])
                return

    if target not in pipeline():  # noqa: SIM102
        if not FLAGS["yes"]:
            msg = f"Merging between task branches (outside pipeline: {src} -> {target}). Continue?"
            if not prompt_yes_no(msg):
                log("Merge cancelled.")
                return
    ensure_pipeline_branch(target)
    info(f"Merging {src.upper()} → {target.upper()}")
    current = get_current_branch()
    if current != src:
        st = run(["git", "status", "--porcelain"], capture=True).stdout.strip()
        if st:
            warn(f"Uncommitted changes on {current.upper()}. Auto-committing...")
            run(["git", "add", "."])
            run(["git", "commit", "-m", f"WIP: Auto-commit {current}"])
        run(["git", "checkout", src])
    log(f"Merging {src} into {target}...")
    run(["git", "checkout", target])
    if check_remote_exists():
        run(["git", "pull", PRIMARY_REMOTE, target], check=False)
    else:
        warn("No remote - skipping pull")
    run(["git", "merge", src, "-m", f"merge: {src} into {target}"])
    if check_remote_exists():
        if FLAGS["yes"] or prompt_yes_no(f"Push {target}?"):
            run(["git", "push", PRIMARY_REMOTE, target])
    else:
        warn("No remote - skipping push")
    log(f"✅ Successfully merged {src.upper()} → {target.upper()}")


def cmd_commit(message):
    if not message:
        error("commit: message required")
    current = get_current_branch()
    st = run(["git", "status", "--porcelain"], capture=True).stdout.strip()
    if st:
        run(["git", "add", "."])
        if not ToolRunner().run_validation(fix=True, dev=FLAGS["dev"]):
            error("Compliance failed.")
        run(["git", "commit", "-m", message])
        info(f"Committed on {current.upper()}")
        if FLAGS["yes"] or prompt_yes_no(f"Push {current}?"):
            if not check_remote_exists():
                pass
            else:
                run(["git", "push", PRIMARY_REMOTE, current])
        log("✅ Commit successful")
    else:
        warn("No changes to commit")


def cmd_promote(src_input, original_task_id=None):
    """
    DEPRECATED: Promote a branch through the pipeline.
    This command is legacy. Use 'hammer tasks move' instead.
    """
    warn(
        "'repo promote' is DEPRECATED. Please use 'hammer tasks move' for unified task promotion."
    )

    src = resolve_branch(src_input)
    task_id = original_task_id or (
        src.split("-")[0] if src.split("-")[0].isdigit() else None
    )

    if task_id and TasksCLI:
        # Redirect to hammer tasks move
        log(f"Redirecting promotion of task {task_id} to 'tasks move'...")
        cmd = ["./hammer", "tasks", "move", task_id]
        if FLAGS["yes"]:
            cmd.append("-y")
        subprocess.run(cmd)  # noqa: PLW1510
        return

    error(
        "Promotion of non-task branches is not supported via this legacy command. Use 'git merge' manually."
    )


def cmd_demote(task_id_input, target_state):
    from tasks_ai.file_manager import FM

    task_id = task_id_input.split("-")[0]
    cli = (
        TasksCLI(quiet=FLAGS["quiet"], dev=FLAGS["dev"], yes=FLAGS["yes"])
        if TasksCLI
        else None
    )
    if cli:
        path, _ = cli.find_task(task_id)
    else:
        error("TasksCLI not initialized")
    task = FM.load(path)
    branch = task.metadata.get("Br")
    info(f"Demoting {task_id} to {target_state}...")
    branches_to_sync = (
        ["staging", "testing"] if target_state == "PROGRESSING" else ["staging"]
    )
    # Sync through the task worktree if one exists, otherwise fall back to main repo
    wt_path = cli.git.worktrees.get_worktree_path(task_id) if cli else None
    cwd = wt_path if wt_path and os.path.exists(wt_path) else repo_root()
    for b in branches_to_sync:
        if branch_exists(b):
            run(["git", "checkout", branch], cwd=cwd)
            run(
                ["git", "merge", b, "-m", f"Sync: {b} -> {branch} (demotion)"],
                check=False,
                cwd=cwd,
            )
    cli.move(task_id, target_state)
    task.metadata["Rc"] = ""
    FM.dump(task, path)
    log("✅ Successfully demoted.")


def resolve_branch(name):
    if name == "current":
        return get_current_branch()
    numeric_id = name.split("-")[0] if name else None
    if numeric_id and numeric_id.isdigit() and TasksCLI:
        cli = (
            TasksCLI(quiet=True, dev=FLAGS["dev"], yes=FLAGS["yes"])
            if TasksCLI
            else None
        )
        path, _ = cli.find_task(numeric_id)
        if path:
            return os.path.basename(path).rsplit(".", 1)[0]
    if branch_exists(name):
        return name
    error(f"COULD NOT RESOLVE BRANCH: {name}!")


def ensure_pipeline_branch(name):
    if branch_exists(name):
        return
    stages = pipeline()
    if name not in stages:
        error(f"Branch {name} not in pipeline.")
    idx = stages.index(name)
    base = stages[idx + 1] if idx + 1 < len(stages) else get_default_branch()
    if not branch_exists(base):
        base = get_current_branch()
    run(["git", "checkout", "-b", name, base], quiet=True)
    run(["git", "checkout", "-"], quiet=True)


def global_flags():
    """Global flags, identical across every tool and accepted on either side of
    the command. SUPPRESS defaults keep a subparser from overwriting a flag the
    main parser already consumed."""
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument(
        "-y",
        "--yes",
        action="store_true",
        default=argparse.SUPPRESS,
        help="Auto-confirm prompts.",
    )
    parser.add_argument(
        "-q",
        "--quiet",
        action="store_true",
        default=argparse.SUPPRESS,
        help="Suppress output (for scripting).",
    )
    parser.add_argument(
        "-j",
        "--json",
        action="store_true",
        default=argparse.SUPPRESS,
        help="JSON output.",
    )
    parser.add_argument(
        "--dev",
        action="store_true",
        default=argparse.SUPPRESS,
        help="Use /tmp/.tasks instead of the project store (isolated).",
    )
    return parser


def build_parser():
    parser = argparse.ArgumentParser(
        prog="repo",
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        parents=[global_flags()],
        epilog=agent_epilog("repo") if agent_epilog else None,
    )
    sub = parser.add_subparsers(dest="command", metavar="command")

    merge = sub.add_parser(
        "merge", parents=[global_flags()], help="Merge <src> into <dest>."
    )
    merge.add_argument("src", help="Source branch, task id, or 'current'.")
    merge.add_argument(
        "dest", help="Target branch or pipeline stage (testing, staging, default)."
    )

    promote = sub.add_parser(
        "promote",
        parents=[global_flags()],
        help="DEPRECATED: promote a branch. Use 'hammer tasks move' instead.",
    )
    promote.add_argument("branch", help="Branch name or task id.")

    demote = sub.add_parser(
        "demote", parents=[global_flags()], help="Demote a task to an earlier state."
    )
    demote.add_argument("task_id", help="Task id or task filename.")
    demote.add_argument("state", help="Target state (e.g. PROGRESSING).")

    sub.add_parser(
        "sync",
        parents=[global_flags()],
        help="Sync testing -> staging -> default branch (exit 0 = synced).",
    )

    commit = sub.add_parser(
        "commit",
        parents=[global_flags()],
        help="Validate, commit, and optionally push (exit 0 = committed).",
    )
    commit.add_argument("message", nargs="+", help="Commit message.")

    git = sub.add_parser(
        "git", parents=[global_flags()], help="Forward remaining args to git."
    )
    git.add_argument("git_args", nargs=argparse.REMAINDER, help="Args for git.")

    sub.add_parser(
        "status", parents=[global_flags()], help="Show git status (read-only)."
    )

    check_merged = sub.add_parser(
        "check-merged",
        parents=[global_flags()],
        help="Exit 0 if <branch> is merged to the default branch (read-only).",
    )
    check_merged.add_argument("branch", help="Branch name, task id, or 'current'.")

    check_merged_testing = sub.add_parser(
        "check-merged-testing",
        parents=[global_flags()],
        help="Exit 0 if <branch> is merged to testing (read-only).",
    )
    check_merged_testing.add_argument(
        "branch", help="Branch name, task id, or 'current'."
    )

    branch = sub.add_parser(
        "branch", parents=[global_flags()], help="Branch helpers (see actions below)."
    )
    branch_sub = branch.add_subparsers(dest="action", required=True, metavar="action")
    branch_sub.add_parser(
        "list", parents=[global_flags()], help="List local branches (read-only)."
    )
    branch_create = branch_sub.add_parser(
        "create", parents=[global_flags()], help="Create and switch to <name>."
    )
    branch_create.add_argument("name", help="New branch name.")
    branch_delete = branch_sub.add_parser(
        "delete", parents=[global_flags()], help="Delete <name> (safe delete)."
    )
    branch_delete.add_argument("name", help="Branch to delete.")
    branch_exists_p = branch_sub.add_parser(
        "exists", parents=[global_flags()], help="Exit 0 if <name> exists (read-only)."
    )
    branch_exists_p.add_argument("name", help="Branch to test.")
    return parser


def main():
    global FLAGS  # noqa: PLW0602
    parser = build_parser()
    args = parser.parse_args()
    FLAGS.update(
        yes=getattr(args, "yes", False),
        quiet=getattr(args, "quiet", False),
        json=getattr(args, "json", False),
        dev=getattr(args, "dev", False),
    )

    if not args.command:
        parser.print_help()
        sys.exit(1)

    if args.command == "merge":
        cmd_merge(args.src, args.dest)
    elif args.command == "promote":
        cmd_promote(args.branch)
    elif args.command == "demote":
        cmd_demote(args.task_id, args.state)
    elif args.command == "sync":
        cmd_merge("testing", "staging")
        cmd_merge("staging", get_default_branch())
    elif args.command == "commit":
        cmd_commit(" ".join(args.message))
    elif args.command == "git":
        run(["git"] + args.git_args)
    elif args.command == "status":
        run(["git", "status"])
    elif args.command == "check-merged":
        sys.exit(0 if check_merged_to_main(args.branch) else 1)
    elif args.command == "check-merged-testing":
        sys.exit(0 if check_merged_to_testing(args.branch) else 1)
    elif args.command == "branch":
        if args.action == "list":
            run(["git", "branch"])
        elif args.action == "create":
            run(["git", "checkout", "-b", args.name])
        elif args.action == "delete":
            run(["git", "branch", "-d", args.name])
        else:
            sys.exit(0 if branch_exists(args.name) else 1)


if __name__ == "__main__":
    sys.exit(main() or 0)
