import os
from ..constants import STATE_FOLDERS
from ..file_manager import FM
from ..utils import parse_filename
from ..libs.list_layout import render_table


def run(cli, show_all=False):
    """Execution logic for 'tasks list'."""
    if not os.path.exists(cli.tasks_path):
        cli.error("INIT_REQUIRED")

    # Check if we should output JSON
    output_json = cli.as_json

    all_data = {}
    seen = set()
    for state, folder in STATE_FOLDERS.items():
        if state == "ARCHIVED" and not show_all:
            continue
        fp = os.path.join(cli.tasks_path, folder)
        if not os.path.exists(fp):
            continue
        items = os.listdir(fp)
        tasks = []
        for item in sorted(items):
            if item == ".gitkeep" or item in seen:
                continue
            path = os.path.join(fp, item)
            if not os.path.isdir(path):
                continue

            try:
                task = FM.load(path)
            except Exception:
                continue

            summary = (task.metadata.get("Ti") or "No Title")[:60]
            if task.corrupted:
                summary = "CORRUPTED TASK"

            tt, tb = parse_filename(item)
            task_id = task.metadata.get("Id")

            # Fallback for ID
            if not task_id:
                task_id = item.split("-")[0] if "-" in item else "???"

            seen.add(item)
            tasks.append(
                {
                    "id": task_id,
                    "p": task.metadata.get("Pr") or 9,
                    "file": item,
                    "type": tt,
                    "branch": tb,
                    "summary": summary,
                    "state": state,
                }
            )
        if tasks:
            tasks.sort(key=lambda x: (x["p"], x["file"]))
            all_data[state] = tasks

    if output_json:
        cli.finish(all_data)
        return

    render_table(all_data)
    
    # Problem Tasks Scan
    cli.log("--- SCANNING FOR PROBLEM TASKS ---")
    candidates = []
    for state, folder in STATE_FOLDERS.items():
        fp = os.path.join(cli.tasks_path, folder)
        if not os.path.exists(fp): continue
        for item in os.listdir(fp):
            if item == ".gitkeep": continue
            path = os.path.join(fp, item)
            if not os.path.isdir(path): continue
            try:
                task = FM.load(path)
                if os.path.basename(os.path.dirname(path)) != STATE_FOLDERS.get(task.metadata.get("St", state)):
                     candidates.append({"task": item, "issue": "tampered location"})
            except:
                candidates.append({"task": item, "issue": "corrupted metadata"})

    if candidates:
        print("\n## Problem Tasks")
        print(f"{'Task':<40} {'Issue'}")
        print("-" * 60)
        for c in candidates:
            print(f"{c['task']:<40} {c['issue']}")
        print("\nRun './hammer tasks reconcile' to fix.")

    cli.finish(all_data)
