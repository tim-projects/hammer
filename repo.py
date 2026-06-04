#!/usr/bin/env python3
"""
repo - Repository management wrapper script
Usage: repo <command> [args]
"""

import subprocess
import sys
import os
import json
from pathlib import Path

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


def get_primary_remote():
    try:
        result = subprocess.run(
            ["git", "remote"], capture_output=True, text=True, check=True
        )
        remotes = result.stdout.split()
        if not remotes:
            return "origin"
        return "origin" if "origin" in remotes else remotes[0]
    except Exception:
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


def run(cmd, check=True, capture=False, env=None, cwd=None, quiet=False):
    project_root = find_project_root()
    capture = capture or quiet or FLAGS["json"]
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
        git_root = cwd or find_project_root()
        local_check = os.path.join(git_root, "check.py")
        cmd = [sys.executable, local_check, "all"]
        if fix:
            cmd.append("--fix")
        if dev:
            cmd.append("--dev")
        result = subprocess.run(cmd, capture_output=True, text=True, cwd=git_root)
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
        ["git", "merge-base", "--is-ancestor", branch, "main"],
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
    error(
        "Command 'repo merge' is deprecated and disabled. Use 'hammer tasks move' for all pipeline transitions to ensure state synchronization."
    )


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


def check_main_divergence():
    run(["git", "fetch", "origin"])
    local = run(["git", "rev-parse", "main"], capture=True).stdout.strip()
    remote = run(["git", "rev-parse", "origin/main"], capture=True).stdout.strip()
    if local != remote:
        error(
            "Local main is out of sync with origin/main. Run git pull or resolve divergence manually.",
            hint="Run git fetch origin && git log main..origin/main to see missing commits.",
        )


def cmd_promote(src_input, original_task_id=None):
    """
    Promote a branch through the pipeline.
    This is now an alias for 'hammer tasks move' with appropriate state mapping.
    """
    src = resolve_branch(src_input)
    task_id = original_task_id or (
        src.split("-")[0] if src.split("-")[0].isdigit() else None
    )

    if task_id and TasksCLI:
        cli = TasksCLI(
            quiet=FLAGS.get("quiet", False), dev=FLAGS["dev"], yes=FLAGS["yes"]
        )
        path, current_status = cli.find_task(task_id)
        if path and current_status:
            status_to_next_state = {
                "PROGRESSING": "TESTING",
                "TESTING": "REVIEW",
                "REVIEW": "STAGING",
                "STAGING": "DONE",
            }
            next_state = status_to_next_state.get(current_status)
            if next_state:
                cli.move(task_id, next_state)
                log(
                    f"✅ Successfully promoted {src.upper()} → {next_state.upper()} via tasks move"
                )
                if next_state == "DONE":
                    cli.move(task_id, "ARCHIVED")
                    run(["git", "branch", "-d", src], check=False)
                return

    # Fallback for non-task branches (very basic)
    error(f"Cannot promote non-task branch '{src}' automatically. Use git merge.")


def cmd_demote(task_id_input, target_state):
    task_id = task_id_input.split("-")[0]
    cli = TasksCLI(quiet=True, dev=FLAGS["dev"], yes=FLAGS["yes"]) if TasksCLI else None
    if not cli:
        error("TasksCLI not initialized")

    path, current_status = cli.find_task(task_id)
    if not path:
        error(f"Task {task_id} not found.")

    info(f"Demoting {task_id} to {target_state} via tasks move...")
    cli.move(task_id, target_state)
    log(f"✅ Successfully demoted {task_id} to {target_state}")


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
    if name not in PIPELINE:
        error(f"Branch {name} not in pipeline.")
    idx = PIPELINE.index(name)
    base = PIPELINE[idx + 1] if idx + 1 < len(PIPELINE) else "main"
    if not branch_exists(base):
        base = get_current_branch()
    run(["git", "checkout", "-b", name, base], quiet=True)
    run(["git", "checkout", "-"], quiet=True)


def main():
    global FLAGS
    args = []
    for arg in sys.argv[1:]:
        if arg in ["-y", "--yes"]:
            FLAGS["yes"] = True
        elif arg == "--dev":
            FLAGS["dev"] = True
        elif arg in ["-j", "--json"]:
            FLAGS["json"] = True
        elif arg in ["-q", "--quiet"]:
            FLAGS["quiet"] = True
        else:
            args.append(arg)
    if not args:
        print(__doc__)
        return
    cmd = args[0]
    if cmd == "merge":
        if len(args) < 3:
            print("Usage: repo.py merge <src> <dest>")
            return
        cmd_merge(args[1], args[2])
    elif cmd == "promote":
        cmd_promote(args[1])
    elif cmd == "demote":
        cmd_demote(args[1], args[2])
    elif cmd == "sync":
        cmd_merge("testing", "staging")
        cmd_merge("staging", "main")
    elif cmd == "commit":
        cmd_commit(" ".join(args[1:]))
    elif cmd == "git":
        run(["git"] + args[1:])
    elif cmd == "status":
        run(["git", "status"])
    elif cmd == "check-merged":
        if len(args) < 2:
            error("check-merged: specify branch")
        sys.exit(0 if check_merged_to_main(args[1]) else 1)
    elif cmd == "check-merged-testing":
        if len(args) < 2:
            error("check-merged-testing: specify branch")
        sys.exit(0 if check_merged_to_testing(args[1]) else 1)
    elif cmd == "branch":
        if len(args) < 2:
            error("branch: specify list, create, or delete")
        elif args[1] == "list":
            run(["git", "branch"])
        elif args[1] == "create" and len(args) > 2:
            run(["git", "checkout", "-b", args[2]])
        elif args[1] == "delete" and len(args) > 2:
            run(["git", "branch", "-d", args[2]])
        elif args[1] == "exists" and len(args) > 2:
            sys.exit(0 if branch_exists(args[2]) else 1)
        else:
            error("branch: unknown subcommand")
    else:
        error(f"Unknown: {cmd}")


if __name__ == "__main__":
    main()
