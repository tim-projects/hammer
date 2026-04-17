#!/usr/bin/env python3
"""
repo - Repository management wrapper script
Usage: repo <command> [args]

Commands:
  merge <src> to <target>    - Merge src branch into target with compliance checks.
                               <src> can be 'current', a task ID (e.g. '23'), or branch name.
  promote <src>              - Promote src through the pipeline: Task -> testing -> staging -> main.
                               <src> can be 'current', a task ID, or a pipeline branch.
  sync                       - Sync branches in order: testing → staging → main
  status                     - Show current branch and pending changes
  git <args>                 - Run git command
  branch list                - List all branches
  branch create <name>       - Create and switch to new branch
  branch delete <name>       - Delete local branch
  push                       - Push current branch to origin
  commit <message>           - Add all changes and commit with message (runs compliance)
  cleanup                    - Run tasks cleanup

Options:
  -y, --yes                  Auto-answer yes to prompts
  -q, --quiet                Minimal output
  -j, --json                 JSON output
  -h, --help                 Show this help
"""

import subprocess
import sys
import os
import json
import shutil
from pathlib import Path

# Add current dir to path to import tasks_ai
sys.path.append(os.getcwd())
try:
    from tasks_ai.cli import TasksCLI
    from tasks_ai.constants import STATE_FOLDERS
except ImportError:
    TasksCLI = None
    STATE_FOLDERS = {}

SCRIPT_DIR = Path(__file__).parent.resolve()

RED = "\033[0;31m"
GREEN = "\033[0;32m"
YELLOW = "\033[1;33m"
CYAN = "\033[0;36m"
NC = "\033[0m"

FLAGS = {"yes": False, "quiet": False, "json": False, "dev": False}

PIPELINE = ["testing", "staging", "main"]


def log(msg):
    if not FLAGS["quiet"]:
        print(f"{GREEN}[repo]{NC} {msg}")


def warn(msg):
    if not FLAGS["quiet"]:
        print(f"{YELLOW}[repo] WARN:{NC} {msg}")


def error(msg):
    if FLAGS["json"]:
        print(json.dumps({"success": False, "error": msg}))
    else:
        print(f"{RED}[repo] ERROR:{NC} {msg}")
    sys.exit(1)


def info(msg):
    if not FLAGS["quiet"]:
        print(f"{CYAN}[repo]{NC} {msg}")


def find_project_root(start_path=None):
    """Search upward for .tasks directory or .git directory."""
    if start_path is None:
        # Start from cwd first, not script dir, to respect test isolation
        start_path = os.getcwd()

    current = os.path.abspath(start_path)
    while True:
        if os.path.isdir(os.path.join(current, ".tasks")) or os.path.isdir(
            os.path.join(current, ".git")
        ):
            return current
        parent = os.path.dirname(current)
        if parent == current:
            break
        current = parent

    # Fallback to script location
    return Path(__file__).parent.resolve()


def run(cmd, check=True, capture=False, env=None, cwd=None):
    project_root = find_project_root()
    try:
        return subprocess.run(
            cmd,
            check=check,
            capture_output=capture,
            text=True,
            env=env,
            cwd=cwd or project_root,
        )
    except subprocess.CalledProcessError as e:
        if check:
            # For capture=True, the error message is in e.stderr
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
    if not sys.stdin.isatty():
        warn(
            "Non-interactive mode detected. Use -y flag to auto-confirm: 'python repo.py -y ...'"
        )
    try:
        while True:
            res = input(f"{prompt} [y/n] ").strip().lower()
            if res in ["y", "yes"]:
                return True
            if res in ["n", "no"]:
                return False
    except EOFError:
        error(
            "EOFError: stdin closed. Use -y flag to auto-confirm: 'python repo.py -y ...'"
        )


class ToolRunner:
    def __init__(self):
        pass

    def run_validation(self, fix=False, dev=False):
        git_root = find_project_root()
        check_py = os.path.join(git_root, "check.py")
        check_cmd = shutil.which("check")
        if not os.path.exists(check_py) and not check_cmd:
            warn("check.py not found, skipping tool validation")
            return True

        tools = ["format", "lint", "typecheck", "test"]
        all_passed = True
        for t in tools:
            # We still need to know if it's configured.
            # check.py handles the config check itself and returns 1 if not configured.
            # But we only want to fail if it IS configured and FAILS.
            # Wait, if it's NOT configured, check.py prints an error and returns 1.
            # We should probably only run 'all' if we want to check everything.
            pass

        # Simpler: just run 'check all'
        log("Running codebase validation (check all)...")
        # Prefer local check.py over system check
        local_check = os.path.join(git_root, "check.py")
        if os.path.exists(local_check):
            cmd = [sys.executable, local_check, "all"]
        elif check_cmd:
            cmd = ["check", "all"]
        else:
            cmd = [sys.executable, check_py, "all"]
        if fix:
            cmd.append("--fix")
        if dev:
            cmd.append("--dev")

        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=600, cwd=git_root
            )
        except subprocess.TimeoutExpired:
            error(
                "Validation timed out after 10 minutes.\n"
                "The validation process is taking too long. Possible causes:\n"
                "  - Too many files to process\n"
                "  - Infinite loop in validation\n"
                "  - System is under heavy load\n"
                "Try running 'check all' manually to see what's happening."
            )

        if result.returncode != 0:
            print(result.stdout)
            print(result.stderr, file=sys.stderr)
            warn(f"Validation failed with exit code {result.returncode}")
            all_passed = False
        else:
            log("✅ Validation passed")

        return all_passed


def branch_exists(name):
    res = run(["git", "rev-parse", "--verify", name], check=False, capture=True)
    return res.returncode == 0


def resolve_branch(name):
    """Resolve 'current', task ID, or name to a full branch name."""
    if name == "current":
        return get_current_branch()

    # Check if task ID
    if name.isdigit() and TasksCLI:
        cli = TasksCLI(quiet=True, dev=FLAGS["dev"])
        path, _ = cli.find_task(name)
        if path:
            branch_name = os.path.basename(path)
            # If local branch doesn't exist but remote does, restore it
            if not branch_exists(branch_name):
                remote_check = run(
                    ["git", "ls-remote", "--heads", "origin", branch_name],
                    check=False,
                    capture=True,
                )
                if remote_check.stdout.strip():
                    run(
                        ["git", "checkout", "-b", branch_name, f"origin/{branch_name}"],
                        check=False,
                    )
                    log(f"Restored branch '{branch_name}' from remote for promotion")
            return branch_name

    # Check if exists as is
    if branch_exists(name):
        return name

    # Check if exists on remote
    remote_check = run(
        ["git", "ls-remote", "--heads", "origin", name], check=False, capture=True
    )
    if remote_check.stdout.strip():
        run(["git", "checkout", "-b", name, f"origin/{name}"], check=False)
        log(f"Restored branch '{name}' from remote")
        return name

    error(f"Could not resolve branch: {name}")


def ensure_pipeline_branch(name):
    if branch_exists(name):
        return

    if name not in PIPELINE:
        error(f"Branch {name} does not exist and is not a pipeline branch.")

    # Create from next in pipeline or main
    idx = PIPELINE.index(name)
    base = "main"
    if idx + 1 < len(PIPELINE):
        base = PIPELINE[idx + 1]

    if not branch_exists(base):
        if base == "main" and branch_exists("master"):
            base = "master"
        else:
            error(f"Cannot create {name}: base branch {base} not found.")

    log(f"Creating pipeline branch {name} from {base}...")
    run(["git", "checkout", "-b", name, base])
    run(["git", "checkout", "-"])  # Return


def cmd_merge(src_input, target):
    src = resolve_branch(src_input)
    # target is passed as argument, ensure it's used correctly
    ensure_pipeline_branch(target)

    info(f"Merging {src} → {target}")

    current = get_current_branch()

    if src == target:
        error(f"Source and target are the same: {src}")

    # 1. Pre-merge checks on src
    if current != src:
        # Check for uncommitted changes and auto-commit if needed
        st = run(["git", "status", "--porcelain"], capture=True).stdout.strip()
        if st:
            warn(f"Uncommitted changes on {current}. Auto-committing...")
            run(["git", "add", "."])
            run(["git", "commit", "-m", f"WIP: Auto-commit before promote to {src}"])

        checkout_res = run(["git", "checkout", src], check=False, capture=True)
        if checkout_res.returncode != 0:
            error(
                f"Failed to checkout {src}: {checkout_res.stderr}\n"
                "Cannot promote with uncommitted changes."
            )
        current = src

    # Check clean
    st = run(["git", "status", "--porcelain"], capture=True).stdout.strip()
    if st:
        warn(f"Uncommitted changes on {src}. Auto-committing...")
        run(["git", "add", "."])
        run(["git", "commit", "-m", f"WIP: {src}"])

    # Run compliance
    log("Running compliance checks...")
    if not ToolRunner().run_validation(fix=True, dev=FLAGS["dev"]):
        error(
            "Compliance failed. Cannot merge to main.\n\n"
            "IMPORTANT: You must fix ALL validation errors (both related AND unrelated to your task) before merging.\n"
            "If the errors are pre-existing/unrelated to your changes, you must:\n"
            "  1. Create a new task to fix the pre-existing errors\n"
            "  2. Move that task to PROGRESSING and fix the errors\n"
            "  3. Move that task through the workflow to LIVE\n"
            "  4. Then retry merging your original task\n\n"
            "Do NOT attempt to bypass this by using direct git merge - "
            "the workflow requires all validation to pass."
        )

    # 2. Perform Merge
    log(f"Merging {src} into {target}...")
    run(["git", "checkout", target])
    # Pull both to be safe
    run(["git", "pull", "origin", target], check=False)

    merge_res = run(
        ["git", "merge", src, "-m", f"merge: {src} into {target} (automated)"],
        check=False,
        capture=True,
    )
    if merge_res.returncode != 0:
        warn("Merge conflict detected!")
        print(merge_res.stdout)
        print(merge_res.stderr)
        error("Please resolve conflicts manually, then finish the merge and push.")

    # 4. Push
    if prompt_yes_no(f"Push {target} to origin?"):
        run(["git", "push", "origin", target])

    # 6. Return
    if src and (FLAGS["yes"] or prompt_yes_no(f"Switch back to {src}?")):
        run(["git", "checkout", src])

    log(f"✅ Successfully merged {src} → {target}")


def cmd_promote(src_input):
    src = resolve_branch(src_input)

    # Determine target
    target = "testing"  # default
    if src == "testing":
        target = "staging"
    elif src == "staging":
        target = "main"
    elif src == "main" or src == "master":
        error("Cannot promote main/master branch further.")
        return  # Ensure target is always bound for pyright
    else:
        # It's a feature branch, promote to testing
        target = "testing"

    cmd_merge(src, target)

    # If it was a feature branch promoted to testing, ask to promote testing to staging etc.
    if target != "main":
        if prompt_yes_no(f"Continue promotion from {target} to next stage?"):
            cmd_promote(target)


def cmd_status():
    branch = get_current_branch()
    info(f"Current branch: {branch}")
    run(["git", "status"], capture=False)


def main():
    global FLAGS
    args = []
    for arg in sys.argv[1:]:
        if arg in ["-y", "--yes"]:
            FLAGS["yes"] = True
        elif arg in ["-q", "--quiet"]:
            FLAGS["quiet"] = True
        elif arg in ["-j", "--json"]:
            FLAGS["json"] = True
        elif arg == "--dev":
            FLAGS["dev"] = True
        elif arg in ["-h", "--help"]:
            print(__doc__)
            return
        else:
            args.append(arg)

    if not args:
        print(__doc__)
        return
    cmd = args[0]

    if cmd == "merge":
        if len(args) < 4 or args[2] != "to":
            error("Usage: repo merge <src> to <target>")
        cmd_merge(args[1], args[3])
    elif cmd == "promote":
        if len(args) < 2:
            error("Usage: repo promote <src>")
        cmd_promote(args[1])
    elif cmd == "sync":
        cmd_merge("testing", "staging")
        cmd_merge("staging", "main")
    elif cmd == "status":
        cmd_status()
    elif cmd == "commit":
        msg = " ".join(args[1:]) if len(args) > 1 else None
        if not msg:
            error("Message required")
        if not ToolRunner().run_validation(fix=True, dev=FLAGS["dev"]):
            error("Compliance failed. Changes not committed.")
        run(["git", "add", "."])
        run(["git", "commit", "-m", msg])
    elif cmd == "push":
        b = get_current_branch()
        run(["git", "push", "origin", b])
    elif cmd == "git":
        run(["git"] + args[1:], capture=False)
    elif cmd == "branch":
        sub = args[1] if len(args) > 1 else "list"
        if sub == "list":
            run(["git", "branch", "-a"], capture=False)
        elif sub == "create":
            run(["git", "checkout", "-b", args[2]])
        elif sub == "delete":
            run(["git", "branch", "-d", args[2]])
    elif cmd == "cleanup":
        cleanup_args = ["python3", "tasks.py", "cleanup"]
        if FLAGS["dev"]:
            cleanup_args.append("--dev")
        run(cleanup_args + args[1:])
    else:
        error(f"Unknown command: {cmd}")


if __name__ == "__main__":
    main()
