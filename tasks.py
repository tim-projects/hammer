#!/usr/bin/env python3
import argparse
from tasks_ai.cli import TasksCLI

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        prog="tasks-ai",
        description="Tasks AI: Agent-optimized, Git-backed task lifecycle manager.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        add_help=True,
    )
    parser.add_argument("-j", "--json", action="store_true", help="JSON output.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("init", help="Init tasks.")

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

    mv_p = subparsers.add_parser("move", help="Move task.")
    mv_p.add_argument(
        "filename", help="Task Id (or filename). Use numeric Id from 'list' output."
    )
    mv_p.add_argument(
        "status",
        help="Target state. Use comma-separated for multi-step (e.g., 'READY,PROGRESSING,TESTING').",
    )

    del_p = subparsers.add_parser(
        "delete", help="Permanently remove a task and its logs."
    )
    del_p.add_argument("filename")
    del_p.add_argument("--confirm", help="Confirmation code.")

    rec_p = subparsers.add_parser("reconcile", help="Archive orphans.")
    rec_p.add_argument("target", nargs="?")

    args = parser.parse_args()
    cli = TasksCLI(as_json=args.json, command=args.command)

    if args.command == "init":
        cli.init()
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
        )
    elif args.command == "move":
        cli.move(args.filename, args.status)
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
        cli.reconcile(args.target)
