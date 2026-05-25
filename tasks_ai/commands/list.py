import os
import shutil
import textwrap
import json
from ..constants import STATE_FOLDERS
from ..file_manager import FM
from ..utils import parse_filename, has_path

def run(cli, show_all=False):
    """Execution logic for 'tasks list'."""
    if not os.path.exists(cli.tasks_path):
        cli.error("Init required.")
    
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
            
            # Robustness: handle corrupted/empty meta.json
            try:
                task = FM.load(path)
            except Exception:
                continue
                
            summary = (task.metadata.get("Ti") or "No Title")[:60]
            if task.corrupted:
                summary = "CORRUPTED TASK"

            tt, tb = parse_filename(item)
            task_id = task.metadata.get("Id")
            
            if not task_id and not task.corrupted:
                task_id = cli._get_next_id()
                task.metadata["Id"] = task_id
                cli._atomic_write(path, task)
                try:
                    cli._run_git(["add", "--all"], cwd=cli.tasks_path)
                    cli._run_git(
                        ["commit", "--allow-empty", "-m", f"Assign Id {task_id} to {item}"], 
                        cwd=cli.tasks_path
                    )
                except: pass

            if not task_id:
                task_id = item.split("-")[0] if "-" in item else "???"

            seen.add(item)
            tasks.append({
                "id": task_id,
                "p": task.metadata.get("Pr") or 9,
                "file": item,
                "type": tt,
                "branch": tb,
                "summary": summary,
                "blocked_by": task.metadata.get("Bl") or [],
                "state": state,
            })
        if tasks:
            tasks.sort(key=lambda x: (x["p"], x["file"]))
            all_data[state] = tasks

    if output_json:
        cli.finish(all_data)
        return

    # Print list table
    term_width = shutil.get_terminal_size(fallback=(180, 24)).columns
    fixed_cols = (3 + 1 + 2 + 1 + 7 + 1 + 6 + 1 + 30)
    summary_min = 30
    available = max(term_width - fixed_cols, 10)
    branch_width = 30
    summary_width = max(summary_min, available)

    print(f"{'#':>3} {'P':>2} {'Summary':<{summary_width}} {'Status':<7} {'Type':<6} {'Branch':<{branch_width}}")
    
    for state in STATE_FOLDERS.keys():
        if state in all_data:
            tasks = all_data[state]
            for t in tasks:
                summary_lines = textwrap.wrap(t["summary"], width=summary_width) or [""]
                
                def simple_wrap(text, width):
                    res = []
                    while len(text) > width:
                        res.append(text[:width])
                        text = text[width:]
                    res.append(text)
                    return res
                
                branch_lines = simple_wrap(t["branch"], branch_width) or [""]
                max_lines = max(len(summary_lines), len(branch_lines))
                
                for i in range(max_lines):
                    s_line = summary_lines[i] if i < len(summary_lines) else ""
                    b_line = branch_lines[i] if i < len(branch_lines) else ""
                    
                    id_str = str(t["id"]) if i == 0 else ""
                    p_str = str(t["p"]) if i == 0 else ""
                    status_str = t["state"] if i == 0 else ""
                    type_str = t["type"] if i == 0 else ""
                    
                    print(f"{id_str:>3} {p_str:>2} {s_line:<{summary_width}} {status_str:<7} {type_str:<6} {b_line:<{branch_width}}")
    
    cli.finish(all_data)
