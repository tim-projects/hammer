#!/usr/bin/env python3
"""
guard - Git-as-database integrity enforcement
Usage: guard <command> [args]

Commands:
  check <task-id>   Gate verdict for one task (exit 0 = pass, 1 = reject)
  scan              Full anomaly report (read-only)
  refresh           Rebuild the cache from git now
  rebuild           Delete the cache, rebuild from scratch, report
  hooks             Install/emit git-hook wrappers into the common hooks dir
"""

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
# The package lives next to this script; cwd may be a task worktree without it.
sys.path.insert(0, str(SCRIPT_DIR))

from tasks_ai.constants import STATE_FOLDERS, load_config
from tasks_ai.guard_engine import (
    GuardEngine,
    GuardUnavailable,
    task_id_of,
)
from tasks_ai.help_text import agent_epilog

RED = "\033[0;31m"
GREEN = "\033[0;32m"
YELLOW = "\033[1;33m"
CYAN = "\033[0;36m"
NC = "\033[0m"

PRE_COMMIT_HOOK = """#!/bin/bash
# hammer guard: reject duplicate task IDs at commit time
branch=$(git rev-parse --abbrev-ref HEAD 2>/dev/null) || exit 0
[ -z "$branch" ] && exit 0
hammer guard check --branch "$branch" || exit 1
"""

PRE_PUSH_HOOK = """#!/bin/bash
# hammer guard: reject duplicate task IDs at push time
while read -r local_ref local_sha remote_ref remote_sha; do
    branch="${local_ref#refs/heads/}"
    [ -z "$branch" ] && continue
    hammer guard check --branch "$branch" || exit 1
done
"""

FIX_PLAN = {
    "GUARD_DUPLICATE_ID": "hammer tasks doctor --fix to reconcile; the guard "
    "never deletes branches itself.",
    "GUARD_STATE_DUPLICATE": "hammer tasks doctor --fix to move the duplicate "
    "folder back to its metadata state.",
    "GUARD_BRANCH_NONCONFORMANT": "hammer tasks doctor --fix to correct "
    "metadata.Br to the folder name.",
    "GUARD_BRANCH_MISSING": "hammer tasks mount <id> to restore the branch, "
    "or move the task back to PROGRESSING.",
    "GUARD_DUPLICATE_REMOTE_ID": "hammer guard refresh --fetch, then "
    "hammer tasks doctor --fix to reconcile.",
    "GUARD_REMOTE_DIVERGENCE": "hammer tasks mount <id> to restore the branch "
    "from origin, then hammer tasks doctor --fix.",
    "GUARD_WORKTREE_ORPHAN": "hammer tasks mount <id> or "
    "hammer tasks doctor --fix to reconcile worktrees.",
    "GUARD_WORKTREE_MISSING": "hammer tasks mount <id>.",
    "GUARD_UNAVAILABLE": "hammer guard rebuild; --force overrides and logs.",
}


def log(msg):
    print(f"{GREEN}[guard]{NC} {msg}")


def warn(msg):
    print(f"{YELLOW}[guard] WARN:{NC} {msg}")


def fail(msg):
    print(f"{RED}[guard] REJECT:{NC} {msg}", file=sys.stderr)
    sys.exit(1)


def main_repo_root():
    result = subprocess.run(  # noqa: PLW1510
        ["git", "rev-parse", "--git-common-dir"], capture_output=True, text=True
    )
    if result.returncode != 0:
        return Path(os.getcwd())
    common = result.stdout.strip()
    if not os.path.isabs(common):
        common = os.path.join(os.getcwd(), common)
    return Path(os.path.normpath(common)).parent


def get_engine(dev=False, cwd=None):
    if dev:
        # Dev reads the same throwaway repo the tasks CLI acts on: assessing the
        # real repo's refs against a dev store is what produced false rejections
        # of real promotions.
        from tasks_ai.context import ProjectContext

        context = ProjectContext(dev=True)
        root = Path(context.repo_root)
        tasks_path = context.tasks_path
        cwd = root  # every git read comes from the dev repo, never the invoked one
    else:
        root = main_repo_root()
        tasks_path = str(root / ".tasks")
    return GuardEngine(
        repo_root=str(root),
        tasks_path=tasks_path,
        dev=dev,
        config=load_config(tasks_path),
        cwd=cwd or os.getcwd(),
    )


def branch_for_task(engine, task_id):
    """Derive the task's branch from its folder name (single source on disk)."""
    if not engine.tasks_path:
        return None
    for folder in STATE_FOLDERS.values():
        state_dir = os.path.join(engine.tasks_path, folder)
        if not os.path.isdir(state_dir):
            continue
        for name in sorted(os.listdir(state_dir)):
            if task_id_of(name) == task_id and os.path.isdir(
                os.path.join(state_dir, name)
            ):
                return name
    return None


def emit_findings(findings, as_json):
    """Every finding blocks: there is no warning tier to fall back to."""
    if as_json:
        print(
            json.dumps(
                {
                    "success": not findings,
                    "verdict": "REJECT" if findings else "PASS",
                    "findings": findings,
                },
                indent=2,
            )
        )
    else:
        for finding in findings:
            print(f"{RED}{finding['code']}{NC}: {finding['detail']}")
    return 1 if findings else 0


def cmd_check(args):
    engine = get_engine(dev=args.dev, cwd=os.getcwd())
    try:
        findings = engine.verdict(
            args.task_id,
            from_state=args.from_state,
            to_state=args.to_state,
            branch=args.branch or branch_for_task(engine, args.task_id),
        )
    except GuardUnavailable as exc:
        # Cannot verify -> cannot approve. Fail closed, no escape hatch.
        fail(f"GUARD_UNAVAILABLE: {exc}")
    return emit_findings(findings, args.json)


def cmd_scan(args):
    engine = get_engine(dev=args.dev, cwd=os.getcwd())
    try:
        findings = engine.scan()
    except GuardUnavailable as exc:
        fail(f"GUARD_UNAVAILABLE: {exc}")
    rows = [
        {"code": f["code"], "task_id": f["task_id"], "detail": f["detail"]}
        for f in findings
        if args.all or f["code"] != "GUARD_REMOTE_DIVERGENCE"
    ]
    if args.json:
        print(
            json.dumps(
                {
                    "success": True,
                    "anomalies": rows,
                    "events": engine.events(),
                },
                indent=2,
            )
        )
        return 0
    events = engine.events()
    if not rows and not events:
        log("no anomalies found")
        return 0
    if rows:
        log(f"{len(rows)} anomaly(ies)")
    for row in rows:
        print(f"  {YELLOW}{row['code']}{NC} [{row['task_id']}] {row['detail']}")
        if args.fix_plan and row["code"] in FIX_PLAN:
            print(f"      {CYAN}fix:{NC} {FIX_PLAN[row['code']]}")
    for event in events:
        print(f"  {RED}{event['code']}{NC} [{event['task_id']}] {event['detail']}")
    return 0


def cmd_refresh(args):
    engine = get_engine(dev=args.dev, cwd=os.getcwd())
    if args.fetch:
        subprocess.run(["git", "fetch", "--all"], cwd=engine.cwd, check=False)
    conn = engine.connect()
    try:
        engine._ensure_schema(conn)
        summary = engine.refresh(conn)
    except GuardUnavailable as exc:
        fail(f"GUARD_UNAVAILABLE: {exc}")
    finally:
        conn.close()
    if args.json:
        print(json.dumps({"success": True, "summary": summary}, indent=2))
    else:
        log(f"cache refreshed: {summary}")
    return 0


def cmd_rebuild(args):
    engine = get_engine(dev=args.dev, cwd=os.getcwd())
    try:
        rows = engine.rebuild()
    except GuardUnavailable as exc:
        fail(f"GUARD_UNAVAILABLE: {exc}")
    if args.json:
        print(json.dumps({"success": True, "anomalies": rows}, indent=2))
    else:
        log(f"cache rebuilt from git: {len(rows)} anomaly(ies)")
        for row in rows:
            print(f"  {YELLOW}{row['code']}{NC} [{row['task_id']}] {row['detail']}")
    return 0


def hooks_dir():
    result = subprocess.run(  # noqa: PLW1510
        ["git", "rev-parse", "--git-path", "hooks"], capture_output=True, text=True
    )
    if result.returncode != 0:
        return None
    path = result.stdout.strip()
    if not os.path.isabs(path):
        path = os.path.join(os.getcwd(), path)
    return path


def cmd_hooks(args):
    if not (args.install or args.emit):
        print(__doc__)
        return 1
    if args.emit:
        print(PRE_COMMIT_HOOK)
        print(PRE_PUSH_HOOK)
        return 0
    target = hooks_dir()
    if not target:
        fail("GUARD_UNAVAILABLE: not a git repository; cannot install hooks")
    os.makedirs(target, exist_ok=True)
    for name, body in (("pre-commit", PRE_COMMIT_HOOK), ("pre-push", PRE_PUSH_HOOK)):
        path = os.path.join(target, name)
        with open(path, "w") as handle:
            handle.write(body)
        os.chmod(path, 0o755)
        if args.json:
            print(json.dumps({"success": True, "installed": path}))
        else:
            log(f"installed {path}")
    return 0


def build_parser():
    parser = argparse.ArgumentParser(
        prog="guard",
        description=__doc__,
        epilog=agent_epilog("guard"),
    )
    sub = parser.add_subparsers(dest="command")

    check = sub.add_parser("check", help="gate verdict for one task")
    check.add_argument("task_id", nargs="?", type=int)
    check.add_argument("--from", dest="from_state")
    check.add_argument("--to", dest="to_state")
    check.add_argument("--branch")
    check.add_argument("--json", action="store_true")
    check.add_argument("--dev", action="store_true")
    check.set_defaults(func=cmd_check)

    scan = sub.add_parser("scan", help="full anomaly report")
    scan.add_argument("--all", action="store_true", help="include archived/divergence")
    scan.add_argument("--json", action="store_true")
    scan.add_argument("--fix-plan", action="store_true")
    scan.add_argument("--dev", action="store_true")
    scan.set_defaults(func=cmd_scan)

    refresh = sub.add_parser("refresh", help="rebuild the cache from git now")
    refresh.add_argument("--fetch", action="store_true")
    refresh.add_argument("--json", action="store_true")
    refresh.add_argument("--dev", action="store_true")
    refresh.set_defaults(func=cmd_refresh)

    rebuild = sub.add_parser("rebuild", help="delete and rebuild the cache")
    rebuild.add_argument("--json", action="store_true")
    rebuild.add_argument("--dev", action="store_true")
    rebuild.set_defaults(func=cmd_rebuild)

    hooks = sub.add_parser("hooks", help="install/emit git-hook wrappers")
    hooks.add_argument("--install", action="store_true")
    hooks.add_argument("--emit", action="store_true")
    hooks.add_argument("--json", action="store_true")
    hooks.set_defaults(func=cmd_hooks)
    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()
    if not getattr(args, "command", None):
        parser.print_help()
        sys.exit(1)
    if args.command == "check" and args.task_id is None and not args.branch:
        parser.error("check requires a task id or --branch")
    sys.exit(args.func(args) or 0)


if __name__ == "__main__":
    main()
