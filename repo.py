#!/usr/bin/env python3
"""
repo - Repository management wrapper script
Usage: repo <command> [args]

Commands:
  merge <src> to <target>    - Merge src branch into target with compliance checks.
  promote <src>              - Promote src through the pipeline: Task -> testing -> staging -> main.
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
        remotes = run(["git", "remote"], capture=True).stdout.split()
        if "origin" in remotes:
            return "origin"
        return remotes[0] if remotes else "origin"
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


def check_origin_exists():
    result = run(["git", "remote", "get-url", PRIMARY_REMOTE], check=False, capture=True)
    if result.returncode != 0:
        if FLAGS["yes"]:
            warn(f"No '{PRIMARY_REMOTE}' remote - continuing in local-only mode")
            return False
        warn(f"No '{PRIMARY_REMOTE}' remote - continuing in local-only mode")
        return False
    return True


def resolve_branch(name):
    if name == "current":
        return get_current_branch()

    # Extract numeric ID if present (e.g., "89", "89-task-xxx", or just digits)
    numeric_id = name.split("-")[0] if name else None
    if numeric_id and numeric_id.isdigit() and TasksCLI:
        cli = TasksCLI(quiet=True, dev=FLAGS["dev"], yes=FLAGS["yes"])  # type: ignore[reportOptionalCall]
        path, _ = cli.find_task(numeric_id)
        if path:
            branch_name = os.path.basename(path)
            return branch_name

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


def cmd_merge(src_input, target_input):
    src = resolve_branch(src_input)
    target = resolve_branch(target_input)

    # Cross-branch merge confirmation (outside pipeline)
    if target not in PIPELINE:
        if not FLAGS["yes"]:
            msg = f"Merging between task branches (outside pipeline: {src} -> {target}). Continue?"
            if not prompt_yes_no(msg):
                log("Merge cancelled.")
                return

    ensure_pipeline_branch(target)
    info(f"Merging {src.upper()} \u2192 {target.upper()}")
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
    if check_origin_exists():
        run(["git", "pull", PRIMARY_REMOTE, target], check=False)
    else:
        warn("No remote - skipping pull")
    run(["git", "merge", src, "-m", f"merge: {src} into {target}"])
    if check_origin_exists():
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
            if not check_origin_exists():
                pass  # continue locally
            else:
                run(["git", "push", PRIMARY_REMOTE, current])
        log("✅ Commit successful")
    else:
        warn("No changes to commit")


def cmd_promote(src_input, original_task_id=None):
    src = resolve_branch(src_input)
    task_id = original_task_id or (
        src.split("-")[0] if src.split("-")[0].isdigit() else None
    )
    target = (
        "testing"
        if src not in PIPELINE
        else ("staging" if src == "testing" else "main")
    )

    if src == target:
        info(f"Branch '{src}' is already the terminal point. Nothing to promote.")
        return

    current_status = None
    if task_id and TasksCLI:
        cli = TasksCLI(quiet=True, dev=FLAGS["dev"], yes=FLAGS["yes"])  # type: ignore[reportOptionalCall]
        path, current_status = cli.find_task(task_id)
        if path:
            if target in ("staging", "main"):
                if current_status == "TESTING":
                    info(f"Task {task_id} in TESTING. Moving to REVIEW for audit.")
                    cli.move(task_id, "REVIEW")
                    error(
                        f"Task {task_id} moved to REVIEW for audit.",
                        hint=f"Run 'tasks modify {task_id} --regression-check' before promoting.",
                    )
                if current_status == "REVIEW":
                    from tasks_ai.file_manager import FM

                    task = FM.load(path)
                    if not task.metadata.get("Rc"):
                        error(
                            "Regression check not passed.",
                            hint=f"Run 'tasks modify {task_id} --regression-check'.",
                        )

    needs_move = False
    if task_id and TasksCLI and current_status:
        if target == "testing" and current_status == "PROGRESSING":
            needs_move = True
        elif target == "staging" and current_status == "REVIEW":
            needs_move = True
        elif target == "main":
            needs_move = True

    if src not in PIPELINE or needs_move:
        cmd_merge(src, target)

    if task_id and TasksCLI and needs_move:
        cli = TasksCLI(quiet=True, dev=FLAGS["dev"], yes=FLAGS["yes"])  # type: ignore[reportOptionalCall]
        new_status = None
        if target == "testing":
            new_status = "TESTING"
        elif target == "staging":
            new_status = "STAGING"
        elif target == "main":
            new_status = "DONE"
        if new_status:
            status = cli.find_task(task_id)[1]
            if status != new_status:
                cli.move(task_id, new_status)

    log(f"✅ Successfully promoted {src.upper()} → {target.upper()}")
    if target == "main":
        log(
            f"Merged to main complete. Current branch: {subprocess.check_output(['git', 'branch', '--show-current']).decode().strip()}"
        )

    if target == "main" and task_id and TasksCLI:
        log(
            f"Task {task_id} successfully promoted to MAIN. Auto-archiving branch and task."
        )
        cli = TasksCLI(quiet=True, dev=FLAGS["dev"], yes=True)
        cli.move(task_id, "ARCHIVED")
        subprocess.run(["git", "branch", "-d", src], capture_output=True)

    if target != "main" and original_task_id is not None:
        log(
            f"Task {task_id} moved to {target.upper()}. Run 'repo promote {src}' to continue to next stage."
        )


def cmd_demote(task_id_input, target_state):
    from tasks_ai.file_manager import FM

    task_id = task_id_input.split("-")[0]
    cli = TasksCLI(quiet=True, dev=FLAGS["dev"], yes=FLAGS["yes"])  # type: ignore[reportOptionalCall]
    path, _ = cli.find_task(task_id)
    task = FM.load(path)
    branch = task.metadata.get("Br")
    info(f"Demoting {task_id} to {target_state}...")

    branches_to_sync = (
        ["staging", "testing"] if target_state == "PROGRESSING" else ["staging"]
    )
    for b in branches_to_sync:
        if branch_exists(b):
            run(["git", "checkout", branch])
            run(
                ["git", "merge", b, "-m", f"Sync: {b} -> {branch} (demotion)"],
                check=False,
            )

    cli.move(task_id, target_state)
    task.metadata["Rc"] = ""
    FM.dump(task, path)
    log("✅ Successfully demoted.")


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
        cmd_merge(args[1], args[3])
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
        result = run(["git"] + args[1:], capture=True)
        if result.stdout:
            print(result.stdout)
    elif cmd == "status":
        result = run(["git", "status"], capture=True)
        print(result.stdout)
    elif cmd == "branch":
        if len(args) < 2:
            error("branch: specify list, create, or delete")
        elif args[1] == "list":
            result = run(["git", "branch"], capture=True)
            print(result.stdout)
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
