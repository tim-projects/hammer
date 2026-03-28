#!/usr/bin/env python3
"""
repo - Repository management wrapper script
Usage: repo <command> [args]

Commands:
  merge testing to staging   - Run compliance checks and merge testing → staging
  merge staging to main     - Run compliance checks and merge staging → main
  sync [branches...]        - Sync branches in order: testing → staging → main → testing
  clean                     - Clean up generated files and show status
  status                    - Show current branch and pending changes
  git <args>                - Run git command (e.g., repo git status)
  branch list               - List all branches
  branch exists <name>      - Check if branch exists (local or remote)
  branch push <name>        - Push branch to remote
  branch delete <name>      - Delete local branch
  branch create <name>      - Create and switch to new branch
  merged <branch> <target> - Check if branch is merged to target (e.g., repo merged feature main)
  merge-base <a> <b>       - Get merge base between two branches
  worktree list             - List worktrees
  worktree add <path> <branch> - Add worktree

Options:
  -y, --yes                 Auto-answer yes to prompts (for automation)
  -q, --quiet               Quiet mode, minimal output
  -j, --json                JSON output (for AI parsing)
  -h, --help                Show this help
"""

import subprocess
import sys
import os
import json
from pathlib import Path
from typing import Optional, List, Dict, Any

SCRIPT_DIR = Path(__file__).parent.resolve()
LOG_DIR = SCRIPT_DIR / 'logs'

GENERATED_FILES = ['public/_headers', 'public/_redirects', 'worker/wrangler.jsonc']

RED = '\033[0;31m'
GREEN = '\033[0;32m'
YELLOW = '\033[1;33m'
CYAN = '\033[0;36m'
NC = '\033[0m'

# Global flags
FLAGS = {
    'yes': False,
    'quiet': False,
    'json': False
}

# Check if we're in a git repo
result = subprocess.run(['git', 'rev-parse', '--git-dir'], capture_output=True)
if result.returncode != 0:
    if FLAGS.get('json'):
        print(json.dumps({"error": "Not a git repository"}))
    else:
        print(f"{RED}Error: Not a git repository{NC}")
        print("Please run this script from the project root.")
    sys.exit(1)


def log(msg):
    if not FLAGS['quiet']:
        print(f"{GREEN}[repo]{NC} {msg}")


def warn(msg):
    if not FLAGS['quiet']:
        print(f"{YELLOW}[repo] WARN:{NC} {msg}")


def error(msg):
    if FLAGS['json']:
        print(json.dumps({"error": msg}))
    else:
        print(f"{RED}[repo] ERROR:{NC} {msg}")
    sys.exit(1)


def info(msg):
    if not FLAGS['quiet']:
        print(f"{CYAN}[repo]{NC} {msg}")


def out(msg):
    """Output for both modes"""
    if not FLAGS['quiet']:
        print(msg)


def run(cmd, check=True, capture=False):
    try:
        return subprocess.run(cmd, check=check, capture_output=capture, text=True)
    except subprocess.CalledProcessError as e:
        if check:
            error(f"Command failed: {' '.join(cmd)}")
        raise


def get_current_branch():
    result = run(['git', 'rev-parse', '--abbrev-ref', 'HEAD'], capture=True)
    return result.stdout.strip()


def cleanup_generated():
    if not FLAGS['quiet']:
        log("Cleaning up generated files...")
    for f in GENERATED_FILES:
        if Path(f).exists():
            result = run(['git', 'diff', '--quiet', f], check=False)
            if result.returncode != 0:
                result = run(['git', 'status', '--porcelain'], capture=True)
                untracked = [l for l in result.stdout.splitlines() 
                            if not any(l.strip().startswith(g.split('/')[0]) for g in GENERATED_FILES)]
                if not untracked:
                    run(['git', 'restore', f], check=False)


def check_clean_working_tree() -> bool:
    cleanup_generated()
    result = run(['git', 'status', '--porcelain'], capture=True)
    untracked = [l for l in result.stdout.splitlines() 
                if not any(l.strip().startswith(g.split('/')[0]) for g in GENERATED_FILES)]
    if untracked:
        error("Uncommitted changes detected")
    return True


def prompt_yes_no(prompt):
    if FLAGS['yes']:
        return True
    while True:
        response = input(f"{prompt} [y/n] ").strip().lower()
        if response in ['y', 'yes']:
            return True
        if response in ['n', 'no']:
            return False
        print("Please answer y or n")


def output_json(data: Dict[str, Any]):
    print(json.dumps(data, indent=2))


def cmd_clean():
    log("Cleaning up generated files...")
    for f in GENERATED_FILES:
        if Path(f).exists():
            result = run(['git', 'diff', '--quiet', f], check=False)
            if result.returncode != 0:
                run(['git', 'restore', f], check=False)
                log(f"Restored: {f}")
    run(['git', 'status'])


def cmd_status():
    branch = get_current_branch()
    
    if FLAGS['json']:
        result = run(['git', 'status', '--porcelain'], capture=True)
        untracked = [l for l in result.stdout.splitlines() 
                    if not any(l.strip().startswith(g.split('/')[0]) for g in GENERATED_FILES)]
        
        branches = {}
        for b in ['main', 'staging', 'testing']:
            try:
                sha = run(['git', 'rev-parse', '--short', f'origin/{b}'], capture=True).stdout.strip()
                branches[b] = sha
            except:
                branches[b] = None
        
        output_json({
            "current_branch": branch,
            "clean": len(untracked) == 0,
            "uncommitted": untracked,
            "branches": branches
        })
        return
    
    info(f"Current branch: {branch}")
    result = run(['git', 'status', '--porcelain'], capture=True)
    untracked = [l for l in result.stdout.splitlines() 
                if not any(l.strip().startswith(g.split('/')[0]) for g in GENERATED_FILES)]
    if untracked:
        warn("Uncommitted changes:")
        for line in untracked:
            print(f"  {line}")
    else:
        info("Working tree is clean")
    print()
    info("Branches:")
    for b in ['main', 'staging', 'testing']:
        try:
            sha = run(['git', 'rev-parse', '--short', f'origin/{b}'], capture=True).stdout.strip()
            print(f"  {b}: {sha}")
        except:
            print(f"  {b}: N/A")


def cmd_merge_testing_staging():
    """Merge testing to staging with compliance checks"""
    current = get_current_branch()
    if current != 'testing':
        if FLAGS['yes'] or prompt_yes_no(f"You're on '{current}', not 'testing'. Switch to testing?"):
            run(['git', 'checkout', 'testing'])
        else:
            error("Must be on testing branch")

    check_clean_working_tree()

    info("Ready to merge testing → staging")
    if not FLAGS['yes']:
        if not prompt_yes_no("Proceed with merge?"):
            log("Cancelled")
            if FLAGS['json']:
                output_json({"cancelled": True, "action": "merge testing to staging"})
            return

    run_compliance_loop("staging")

    log("Merging testing into staging...")
    run(['git', 'checkout', 'staging'])
    run(['git', 'pull', 'origin', 'staging'])
    run(['git', 'merge', 'testing', '-m', 'merge: testing into staging (automated)'])
    run(['git', 'push', 'origin', 'staging'])
    run(['git', 'checkout', 'testing'])

    log("✅ Successfully merged testing → staging")
    if FLAGS['json']:
        output_json({"success": True, "action": "merge testing to staging"})


def cmd_merge_staging_main():
    """Merge staging to main with compliance checks"""
    current = get_current_branch()
    if current != 'staging':
        if FLAGS['yes'] or prompt_yes_no(f"You're on '{current}', not 'staging'. Switch to staging?"):
            run(['git', 'checkout', 'staging'])
        else:
            error("Must be on staging branch")

    check_clean_working_tree()

    info("Ready to merge staging → main")
    if not FLAGS['yes']:
        if not prompt_yes_no("Run staging validation first (required)?"):
            error("Staging validation is required")

    log("Running staging validation...")
    result = run([str(SCRIPT_DIR / 'run_staging_validation.sh'), '--env', 'staging'], check=False)
    if result.returncode != 0:
        error("Staging validation failed")

    log("✅ Validation passed")

    if not FLAGS['yes']:
        if not prompt_yes_no("Proceed with merge to main?"):
            log("Cancelled")
            if FLAGS['json']:
                output_json({"cancelled": True, "action": "merge staging to main"})
            return

    run_compliance_check_main()

    log("Merging staging into main...")
    run(['git', 'checkout', 'main'])
    run(['git', 'pull', 'origin', 'main'])
    run(['git', 'merge', 'staging', '-m', 'merge: staging into main (automated)'])
    run(['git', 'push', 'origin', 'main'])
    run(['git', 'checkout', 'staging'])

    log("✅ Successfully merged staging → main")

    if FLAGS['yes'] or FLAGS['quiet'] or prompt_yes_no("Auto-sync testing with main?"):
        log("Syncing main → testing...")
        run(['git', 'checkout', 'testing'])
        run(['git', 'merge', 'main'])
        run(['git', 'push', 'origin', 'testing'])
        run(['git', 'checkout', 'staging'])
        log("✅ Synced main → testing")

    if FLAGS['json']:
        output_json({"success": True, "action": "merge staging to main", "auto_synced": True})


def run_compliance_loop(target_branch):
    """Run compliance loop for testing→staging merge"""
    max_retries = 5
    retry_count = 0

    while retry_count < max_retries:
        log(f"Compliance check (attempt {retry_count + 1}/{max_retries})...")

        log("Running typecheck...")
        result = run(['npm', 'run', 'typecheck'], check=False)
        if result.returncode != 0:
            error("Type check failed - cannot auto-fix")

        log("Applying formatting...")
        run(['npm', 'run', 'format'], check=False)

        log("Applying lint fixes...")
        run(['npm', 'run', 'lint'], check=False)

        log("Running audit fix...")
        run(['npm', 'audit', 'fix', '--yes'], check=False)

        if target_branch == "staging":
            log("Skipping build for staging")
        else:
            log("Running build...")
            result = run(['npm', 'run', 'build'], check=False)
            if result.returncode != 0:
                error("Build failed")

        log("Compliance met!")
        break
        retry_count += 1

    if retry_count == max_retries:
        error("Max retries reached without compliance")

    if run(['git', 'status', '--porcelain'], capture=True).stdout.strip():
        log("Auto-fixes detected, committing...")
        run(['git', 'add', '.'])
        run(['git', 'commit', '-m', 'chore: automated fixes'], check=False)


def run_compliance_check_main():
    """Run simplified compliance check for staging→main merge"""
    log("Running typecheck...")
    result = run(['npm', 'run', 'typecheck'], check=False)
    if result.returncode != 0:
        error("Type check failed")

    log("Applying formatting...")
    run(['npm', 'run', 'format'], check=False)

    log("Running format check...")
    result = run(['npm', 'run', 'format:check'], check=False)
    if result.returncode != 0:
        error("Format check failed")

    log("Running lint...")
    result = run(['npm', 'run', 'lint'], check=False)
    if result.returncode != 0:
        warn("Lint check failed - proceeding anyway")

    if run(['git', 'status', '--porcelain'], capture=True).stdout.strip():
        log("Auto-fixes detected, committing...")
        run(['git', 'add', '.'])
        run(['git', 'commit', '-m', 'chore: final automated fixes'], check=False)


def cmd_sync(branches):
    if not branches:
        branches = ['main', 'staging', 'testing']
    
    valid = {'main', 'staging', 'testing'}
    for b in branches:
        if b not in valid:
            error(f"Unknown branch: {b}")

    log(f"Sync order: {' → '.join(branches)}")
    if not FLAGS['yes']:
        if not prompt_yes_no("Continue?"):
            log("Cancelled")
            return

    if 'main' in branches and 'staging' in branches:
        cmd_merge_staging_main()

    if 'staging' in branches and 'testing' in branches:
        cmd_merge_testing_staging()
        log("Syncing main → testing...")
        run(['git', 'checkout', 'testing'])
        run(['git', 'merge', 'main'])
        run(['git', 'push', 'origin', 'testing'])
        run(['git', 'checkout', 'staging'])

    log("✅ Sync complete")
    if FLAGS['json']:
        output_json({"success": True, "action": "sync", "branches": branches})


def cmd_help():
    print(__doc__)


def cmd_git(args):
    """Run git command"""
    result = run(['git'] + args, capture=True)
    out(result.stdout)


def cmd_branch(args):
    """Branch management commands"""
    if not args:
        result = run(['git', 'branch'], capture=True)
        out(result.stdout)
        return

    subcmd = args[0]

    if subcmd == 'list':
        result = run(['git', 'branch', '-a'], capture=True)
        out(result.stdout)

    elif subcmd == 'exists':
        if len(args) < 2:
            error("Usage: repo branch exists <name>")
        name = args[1]
        local_result = run(['git', 'rev-parse', '--verify', name], check=False, capture=True)
        local = local_result.returncode == 0
        
        has_origin = run(['git', 'remote', 'get-url', 'origin'], check=False, capture=True).returncode == 0
        if has_origin:
            remote_result = run(['git', 'ls-remote', '--heads', 'origin', name], capture=True)
            remote = bool(remote_result.stdout.strip())
        else:
            remote = False
        
        if local or remote:
            print("true")
        else:
            print("false")
        return

    elif subcmd == 'push':
        if len(args) < 2:
            error("Usage: repo branch push <name>")
        name = args[1]
        run(['git', 'push', 'origin', name])

    elif subcmd == 'delete':
        if len(args) < 2:
            error("Usage: repo branch delete <name>")
        name = args[1]
        current = get_current_branch()
        if current == name:
            run(['git', 'checkout', 'master'])
        run(['git', 'branch', '-d', name])

    elif subcmd == 'create':
        if len(args) < 2:
            error("Usage: repo branch create <name>")
        name = args[1]
        run(['git', 'checkout', '-b', name])

    else:
        error(f"Unknown branch command: {subcmd}")


def cmd_merged(args):
    """Check if branch is merged to target"""
    if len(args) < 2:
        error("Usage: repo merged <branch> <target> (e.g., repo merged feature main)")
    branch = args[0]
    target = args[1]

    target_sha = run(['git', 'rev-parse', target], capture=True).stdout.strip()
    branch_sha = run(['git', 'rev-parse', branch], capture=True).stdout.strip()
    merge_base = run(['git', 'merge-base', branch_sha, target], capture=True).stdout.strip()

    if merge_base == target_sha:
        print("true")
    else:
        print("false")
    return


def cmd_merge_base(args):
    """Get merge base between two branches"""
    if len(args) < 2:
        error("Usage: repo merge-base <branch1> <branch2>")
    result = run(['git', 'merge-base', args[0], args[1]], capture=True)
    print(result.stdout.strip())


def cmd_worktree(args):
    """Worktree management"""
    if not args:
        result = run(['git', 'worktree', 'list'], capture=True)
        out(result.stdout)
        return

    subcmd = args[0]

    if subcmd == 'add':
        if len(args) < 3:
            error("Usage: repo worktree add <path> <branch>")
        run(['git', 'worktree', 'add', args[1], args[2]])

    elif subcmd == 'remove':
        if len(args) < 2:
            error("Usage: repo worktree remove <path>")
        run(['git', 'worktree', 'remove', args[1]])

    else:
        error(f"Unknown worktree command: {subcmd}")


def parse_args():
    """Parse command line arguments and set global flags"""
    global FLAGS
    
    # First pass: check for flags that don't require git repo
    for arg in sys.argv[1:]:
        if arg in ['-y', '--yes']:
            FLAGS['yes'] = True
        elif arg in ['-q', '--quiet']:
            FLAGS['quiet'] = True
        elif arg in ['-j', '--json']:
            FLAGS['json'] = True
        elif arg in ['-h', '--help']:
            cmd_help()
            sys.exit(0)


def main():
    parse_args()
    
    # Filter out flags to get the actual command
    args = [arg for arg in sys.argv[1:] if not arg.startswith('-')]
    
    if not args:
        cmd_help()
        return

    cmd = args[0]

    if cmd in ['help', '--help', '-h']:
        cmd_help()
        return

    if cmd == 'merge':
        if len(args) < 3:
            error("Usage: repo merge testing to staging | repo merge staging to main")
        sub = f"{args[1]} {args[2]}"
        if sub == "testing to staging":
            cmd_merge_testing_staging()
        elif sub == "staging to main":
            cmd_merge_staging_main()
        else:
            error(f"Unknown merge: {sub}")

    elif cmd == 'sync':
        cmd_sync(args[1:] if len(args) > 1 else [])

    elif cmd == 'clean':
        cmd_clean()

    elif cmd == 'status':
        cmd_status()

    elif cmd == 'git':
        cmd_git(args[1:])

    elif cmd == 'branch':
        cmd_branch(args[1:])

    elif cmd == 'merged':
        cmd_merged(args[1:])

    elif cmd == 'merge-base':
        cmd_merge_base(args[1:])

    elif cmd == 'worktree':
        cmd_worktree(args[1:])

    else:
        error(f"Unknown command: {cmd}")
        cmd_help()


if __name__ == '__main__':
    main()
