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

            tt, _ = parse_filename(item)  # We need tt for type
            
            # Determine the canonical task ID using multiple sources with validation
            canonical_id = None
            id_source = None
            
            # Source 1: metadata.Id (highest priority if valid)
            metadata_id = task.metadata.get("Id")
            if metadata_id and str(metadata_id).isdigit():
                canonical_id = int(metadata_id)
                id_source = "metadata.Id"
            
            # Source 2: metadata.Br (extract ID from branch if it follows expected format)
            if not canonical_id:
                branch_from_metadata = task.metadata.get("Br")
                if branch_from_metadata and isinstance(branch_from_metadata, str) and "-" in branch_from_metadata:
                    branch_parts = branch_from_metadata.split("-", 2)
                    if len(branch_parts) >= 3 and branch_parts[0].isdigit():
                        branch_id = int(branch_parts[0])
                        canonical_id = branch_id
                        id_source = "metadata.Br"
            
            # Source 3: directory name (extract ID if it follows expected format)
            if not canonical_id and not task.corrupted:
                dir_id = None
                if "-" in item:
                    parts = item.split("-", 1)
                    if parts[0].isdigit():
                        dir_id = int(parts[0])
                
                if dir_id is not None:
                    canonical_id = dir_id
                    id_source = "directory name"
            
            # If we still don't have an ID, try to fix metadata
            if not canonical_id and not task.corrupted:
                # Try to recover from directory name as last resort
                dir_id = None
                if "-" in item:
                    parts = item.split("-", 1)
                    if parts[0].isdigit():
                        dir_id = int(parts[0])
                
                if dir_id is not None:
                    canonical_id = dir_id
                    id_source = "directory name (recovery)"
                    # Fix the metadata
                    task.metadata["Id"] = canonical_id
                    cli._atomic_write(path, task)
                    try:
                        cli._run_git(["add", "--all"], cwd=cli.tasks_path)
                        cli._run_git(
                            ["commit", "--allow-empty", "-m", f"Recovered Id {canonical_id} for {item} from directory name"], 
                            cwd=cli.tasks_path
                        )
                    except: pass
                    cli.log(f"Recovered missing ID {canonical_id} for task {item} from directory name")
                else:
                    # Last resort: assign new ID (should extremely rarely happen)
                    canonical_id = cli._get_next_id()
                    id_source = "new ID assignment"
                    task.metadata["Id"] = canonical_id
                    cli._atomic_write(path, task)
                    try:
                        cli._run_git(["add", "--all"], cwd=cli.tasks_path)
                        cli._run_git(
                            ["commit", "--allow-empty", "-m", f"Assigned new Id {canonical_id} to {item}"], 
                            cwd=cli.tasks_path
                        )
                    except: pass
                    cli.log(f"Assigned new ID {canonical_id} to task {item} (no ID in metadata, dirname, or branch)")
            
            # Final fallback (should almost never happen)
            if not canonical_id:
                canonical_id = item.split("-")[0] if "-" in item else "???"
                id_source = "directory fallback"
            
            # Determine branch name - prefer consistency with canonical ID
            # First, check if metadata.Br exists and is valid
            branch_from_metadata = task.metadata.get("Br")
            if branch_from_metadata and isinstance(branch_from_metadata, str) and "-" in branch_from_metadata:
                branch_parts = branch_from_metadata.split("-", 2)
                if len(branch_parts) >= 3 and branch_parts[0].isdigit():
                    branch_id = int(branch_parts[0])
                    # If branch ID matches our canonical ID, use it
                    if branch_id == canonical_id:
                        tb = branch_from_metadata
                    else:
                        # Branch ID doesn't match - log warning and construct expected branch
                        cli.log(f"Warning: Branch ID mismatch for task {item}: metadata.Br='{branch_from_metadata}' (ID={branch_id}) vs canonical ID={canonical_id}")
                        # Construct expected branch from canonical ID
                        tb = f"{canonical_id}-{tt}-{(task.metadata.get('Ti') or 'unknown')[:30]}".strip("-")
                else:
                    # metadata.Br doesn't follow expected format
                    tb = f"{canonical_id}-{tt}-{(task.metadata.get('Ti') or 'unknown')[:30]}".strip("-")
            else:
                # No valid metadata.Br, construct expected branch
                tb = f"{canonical_id}-{tt}-{(task.metadata.get('Ti') or 'unknown')[:30]}".strip("-")
            
            seen.add(item)
            tasks.append({
                "id": canonical_id,
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
