import os
import re
from datetime import datetime
from ..constants import STATE_FOLDERS
from ..models import Task
from ..file_manager import FM


def run(
    cli,
    title,
    task_type="task",
    priority=None,
    story=None,
    tech=None,
    criteria=None,
    plan=None,
    repro=None,
    branch=False,
):
    """Execution logic for 'tasks create'."""
    title = title.strip()
    if len(title) < 10:
        cli.error("Task title is too vague. Min 10 chars.")

    if task_type not in ["task", "issue", "docs", "test"]:
        cli.error(f"Invalid task type: {task_type}. Allowed: task, issue, docs, test.")

    if branch:
        cli.log(
            "Note: --branch flag is ignored; branch names are auto-generated from title."
        )

    missing = []
    if not story:
        missing.append("--story")
    if not tech:
        missing.append("--tech")
    if not criteria:
        missing.append("--criteria")
    if not plan:
        missing.append("--plan")
    if task_type == "issue" and not repro:
        missing.append("--repro")

    if missing:
        cli.error(
            f"MISSING PARTS: {', '.join(missing)}! HAMMER SAY NO! FIX! 🔨\n"
            f"Usage: tasks create '<title>' --story '<story>' --tech '<tech>' --criteria '<criteria>' --plan '<plan>'"
            f"{' --repro <repro>' if task_type == 'issue' else ''}"
        )

    MIN_LEN = 15
    too_short = []
    story_str = story if isinstance(story, str) else " ".join(story) if story else ""
    tech_str = tech if isinstance(tech, str) else " ".join(tech) if tech else ""

    if story and len(story_str.strip()) < MIN_LEN:
        too_short.append(f"--story (min {MIN_LEN} chars)")
    if tech and len(tech_str.strip()) < MIN_LEN:
        too_short.append(f"--tech (min {MIN_LEN} chars)")
    if criteria:
        crit_str = " ".join(criteria) if isinstance(criteria, list) else criteria
        if len(crit_str.strip()) < MIN_LEN:
            too_short.append(f"--criteria (min {MIN_LEN} chars)")
    if plan:
        plan_str = " ".join(plan) if isinstance(plan, list) else plan
        if len(plan_str.strip()) < MIN_LEN:
            too_short.append(f"--plan (min {MIN_LEN} chars)")
    if task_type == "issue" and repro:
        repro_str = " ".join(repro) if isinstance(repro, list) else repro
        if len(repro_str.strip()) < MIN_LEN:
            too_short.append(f"--repro (min {MIN_LEN} chars)")

    if too_short:
        cli.error(f"TOO SHORT: {', '.join(too_short)}! HAMMER SAY NO! FIX! 🔨")

    if priority is not None:
        try:
            p = int(priority)
            if not (1 <= p <= 9):
                raise ValueError()
        except (ValueError, TypeError):
            cli.error("Priority must be a number between 1 and 9.")

    clean_title = re.sub(r"[^a-zA-Z0-9]+", "-", title.lower()).strip("-")
    numeric_id = cli._get_next_id()
    task_id = f"{numeric_id}-{task_type}-{clean_title[:30]}".strip("-")
    task_dir = os.path.join(cli.tasks_path, STATE_FOLDERS["BACKLOG"], task_id)

    if cli.find_task(task_id)[0]:
        cli.error(f"Task {task_id} exists.")

    for state, folder in STATE_FOLDERS.items():
        fp = os.path.join(cli.tasks_path, folder)
        if not os.path.exists(fp):
            continue
        for item in os.listdir(fp):
            if item == ".gitkeep":
                continue
            path = os.path.join(fp, item)
            task = FM.load(path)
            if task.metadata.get("Id") == numeric_id:
                cli.error(f"Task with Id {numeric_id} already exists (in {state}).")

    task = Task(
        metadata={
            "Id": numeric_id,
            "Ti": title,
            "Cr": datetime.now().strftime("%y%m%d %H:%M"),
            "Bl": [],
            "Pr": priority or (1 if task_type == "issue" else 2),
            "Br": task_id,
        },
        parts={
            "story": story or "",
            "tech": tech or "",
            "criteria": (
                "\n".join(f"- [ ] {c}" for c in criteria)
                if isinstance(criteria, list)
                else f"- [ ] {criteria}"
            )
            if criteria
            else "",
            "plan": (
                "\n".join(f"{i}. {p}" for i, p in enumerate(plan, 1))
                if isinstance(plan, list)
                else f"1. {plan}"
            )
            if plan
            else "",
            "repro": (
                "\n".join(f"{i}. {r}" for i, r in enumerate(repro, 1))
                if isinstance(repro, list)
                else f"1. {repro}"
            )
            if repro
            else None,
        },
    )

    try:
        cli._atomic_write(task_dir, task)
        cli._append_log(task_dir, "Cr")
        cli._run_git(
            ["add", os.path.relpath(task_dir, cli.tasks_path)], cwd=cli.tasks_path
        )
        cli._run_git(
            ["commit", "--allow-empty", "-m", f"Add {task_type}: {title}"],
            cwd=cli.tasks_path,
        )

        original_branch = cli._run_git(
            ["rev-parse", "--abbrev-ref", "HEAD"]
        ).stdout.strip()
        cli._run_git(["checkout", cli._get_default_branch()], cwd=cli.root)
        cli._run_git(["checkout", "-b", task_id], cwd=cli.root)
        cli._run_git(["merge", original_branch], cwd=cli.root)

        current_branch = cli._run_git(
            ["rev-parse", "--abbrev-ref", "HEAD"]
        ).stdout.strip()
        cli.log(f"Created: [{numeric_id}] {task_type} | {title}")
        cli.log(f"Branch: {task_id} | Now on: {current_branch}")

        cli.finish(
            {
                "id": numeric_id,
                "task_id": task_id,
                "title": title,
                "file": task_id,
                "path": os.path.relpath(task_dir, cli.root),
                "branch": task_id,
                "current_branch": current_branch,
            }
        )
    except Exception as e:
        cli.error(str(e))
