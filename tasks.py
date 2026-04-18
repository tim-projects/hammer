#!/usr/bin/env python3
__version__ = "0.1.0"

import argparse
import sys
from tasks_ai.cli import TasksCLI
from tasks_ai.help_text import get_help_text

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        prog="tasks",
        description="Tasks AI: Agent-optimized, Git-backed task lifecycle manager.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        add_help=True,
        epilog=get_help_text(),
    )
    parser.add_argument("--version", action="store_true", help="Show version.")
    parser.add_argument("-j", "--json", action="store_true", help="JSON output.")
    parser.add_argument(
        "-q",
        "--quiet",
        action="store_true",
        help="Suppress output (for scripting).",
        default=False,
    )
    parser.add_argument(
        "--dev",
        action="store_true",
        help="Use /tmp/.tasks instead of project tasks (for development).",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("init", help="Init tasks.")

    save_p = subparsers.add_parser(
        "save", help="Save and push .tasks worktree to remote."
    )
    save_p.add_argument(
        "--branch",
        "-b",
        default="tasks",
        help="Remote branch name (default: 'tasks').",
    )
    save_p.add_argument(
        "-y",
        "--yes",
        action="store_true",
        help="Continue without remote (local-only mode).",
    )

    list_p = subparsers.add_parser("list", help="List tasks.")
    list_p.add_argument("--all", action="store_true")

    cur_p = subparsers.add_parser("current", help="Show active task.")
    cur_p.add_argument("filename", nargs="?")

    show_p = subparsers.add_parser("show", help="Show task details.")
    show_p.add_argument("filename", help="Task Id or filename to show.")
    show_p.add_argument(
        "section",
        nargs="?",
        choices=["story", "tech", "criteria", "plan", "repro", "notes", "progress"],
        help="Specific section to show: story, tech, criteria, plan, repro, notes, progress",
    )

    cp_p = subparsers.add_parser("checkpoint", help="Sync commits/notes.")
    cp_p.add_argument("filename", nargs="?")

    lk_p = subparsers.add_parser("link", help="Link tasks (blocker relationship).")
    lk_p.add_argument("filename", help="Task Id (or filename) to block.")
    lk_p.add_argument("blocked_by", help="Task Id (or filename) that is blocking.")

    cr_p = subparsers.add_parser("create", help="Create task.")
    cr_p.add_argument("title", help="Task title (min 10 chars).")
    cr_p.add_argument(
        "--type",
        "-t",
        default="task",
        choices=["task", "issue"],
        help="Task type: task or issue.",
    )
    cr_p.add_argument("--priority", "-p", type=int, help="Priority (1=highest).")
    cr_p.add_argument("--story", help="User story description.")
    cr_p.add_argument("--tech", help="Technical background.")
    cr_p.add_argument("--criteria", nargs="+", help="Acceptance criteria (list).")
    cr_p.add_argument("--plan", nargs="+", help="Implementation plan (list).")
    cr_p.add_argument(
        "--repro", nargs="+", help="Reproduction steps for issues (list)."
    )

    mod_p = subparsers.add_parser("modify", help="Update task.")
    mod_p.add_argument("filename", help="Task Id (or filename).")
    mod_p.add_argument("--title", help="New title.")
    mod_p.add_argument("--story", help="User story.")
    mod_p.add_argument("--tech", help="Technical background.")
    mod_p.add_argument("--criteria", nargs="+", help="Acceptance criteria.")
    mod_p.add_argument("--plan", nargs="+", help="Implementation plan.")
    mod_p.add_argument("--repro", nargs="+", help="Reproduction steps.")
    mod_p.add_argument("--notes", help="Notes content.")
    mod_p.add_argument("--progress", help="Progress update.")
    mod_p.add_argument("--findings", help="Findings.")
    mod_p.add_argument("--mitigations", help="Mitigations.")
    mod_p.add_argument(
        "--tests-passed", action="store_true", help="Mark tests as passed."
    )
    mod_p.add_argument(
        "--regression-check",
        action="store_true",
        help="Mark regression check as passed (enables STAGING from REVIEW).",
    )
    mod_p.add_argument("-p", "--priority", type=int, help="Update priority.")

    mv_p = subparsers.add_parser("move", help="Move task.")
    mv_p.add_argument(
        "filename", help="Task Id (or filename). Use numeric Id from 'list' output."
    )
    mv_p.add_argument(
        "status",
        help="Target state. Use comma-separated for multi-step (e.g., 'READY,PROGRESSING,TESTING').",
    )
    mv_p.add_argument(
        "-y",
        "--yes",
        action="store_true",
        help="Auto-confirm archive (push and delete branch).",
    )

    del_p = subparsers.add_parser(
        "delete", help="Permanently remove a task and its logs."
    )
    del_p.add_argument("filename")
    del_p.add_argument("--confirm", help="Confirmation code.")

    rec_p = subparsers.add_parser(
        "reconcile", help="Scan/clean merged branches (see cleanup)."
    )
    rec_p.add_argument("target", nargs="?")
    rec_p.add_argument("--all", action="store_true", help="Clean up all candidates.")

    clean_p = subparsers.add_parser(
        "cleanup",
        help="Clean up merged branches, push to remote, delete local, archive tasks.",
    )
    clean_p.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be cleaned up without making changes.",
    )
    clean_p.add_argument(
        "-y", "--yes", action="store_true", help="Auto-push and delete branches."
    )

    cfg_p = subparsers.add_parser("config", help="Manage configuration.")
    cfg_p.add_argument(
        "action",
        nargs="?",
        choices=["get", "set", "list", "detect"],
        help="Config action.",
    )
    cfg_p.add_argument("key", nargs="?", help="Config key.")
    cfg_p.add_argument("value", nargs="?", help="Config value.")
    cfg_p.add_argument(
        "--save", action="store_true", help="Save detected config (for detect action)."
    )

    subparsers.add_parser(
        "upgrade", help="Upgrade tasks to latest version (runs install.sh)."
    )

    run_p = subparsers.add_parser("run", help="Run a configured tool.")
    run_p.add_argument(
        "tool",
        nargs="?",
        choices=["lint", "test", "typecheck", "format", "all"],
        help="Tool to run.",
    )
    run_p.add_argument("--fix", action="store_true", help="Apply fixes if supported.")

    undo_p = subparsers.add_parser("undo", help="Undo last operation on a task.")
    undo_p.add_argument("filename", help="Task Id (or filename) to undo.")

    doc_p = subparsers.add_parser("doctor", help="Diagnose task data and git state.")
    doc_p.add_argument(
        "--fix",
        action="store_true",
        help="Attempt to fix issues automatically.",
    )

    args = parser.parse_args()

    if args.version:
        print(f"tasks version {__version__}")
        sys.exit(0)

    cli = TasksCLI(
        as_json=args.json,
        command=args.command,
        quiet=args.quiet,
        dev=args.dev,
        yes=getattr(args, "yes", False),
    )

    if args.command == "init":
        cli.init()
    elif args.command == "save":
        cli.save(branch=args.branch)
    elif args.command == "create":
        cli.create(
            args.title,
            args.type,
            args.priority,
            story=args.story,
            tech=args.tech,
            criteria=args.criteria,
            plan=args.plan,
            repro=args.repro,
        )
    elif args.command == "modify":
        cli.modify(
            args.filename,
            title=args.title,
            story=args.story,
            tech=args.tech,
            criteria=args.criteria,
            plan=args.plan,
            repro=args.repro,
            notes=args.notes,
            progress=args.progress,
            findings=args.findings,
            mitigations=args.mitigations,
            tests_passed=args.tests_passed,
            priority=args.priority,
            regression_check=args.regression_check,
        )
    elif args.command == "move":
        cli.move(args.filename, args.status, yes=args.yes)
    elif args.command == "delete":
        cli.delete(args.filename, confirm=args.confirm)
    elif args.command == "list":
        cli.list(show_all=args.all)
    elif args.command == "current":
        cli.current(args.filename)
    elif args.command == "show":
        cli.show(args.filename, args.section)
    elif args.command == "checkpoint":
        cli.checkpoint(args.filename)
    elif args.command == "link":
        cli.link(args.filename, args.blocked_by)
    elif args.command == "reconcile":
        cli.reconcile(args.target, all=args.all)
    elif args.command == "cleanup":
        cli.cleanup(dry_run=args.dry_run, yes=args.yes)
    elif args.command == "config":
        cli.config(args.action, args.key, args.value, save=args.save)
    elif args.command == "upgrade":
        cli.upgrade()
    elif args.command == "run":
        cli.run_tool(args.tool, fix=args.fix)
    elif args.command == "undo":
        cli.undo(args.filename)
    elif args.command == "doctor":
        cli.doctor(fix=args.fix)
