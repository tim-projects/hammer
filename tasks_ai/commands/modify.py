import os
import re
from ..constants import CURRENT_TASK_FILENAME
from ..file_manager import FM
from ..utils import parse_filename

def run(cli, filename, title=None, story=None, tech=None, criteria=None, plan=None, repro=None, 
        notes=None, progress=None, findings=None, mitigations=None, tests_passed=None, 
        priority=None, regression_check=None):
    """Execution logic for 'tasks modify'."""
    filepath, _ = cli.find_task(filename)
    if not filepath:
        cli.error(f"Task '{filename}' not found.")
    
    task = FM.load(filepath)
    fname = os.path.basename(filepath)
    task_id = fname.rsplit(".", 1)[0]
    tt, _ = parse_filename(fname)
    updated = False
    
    if title:
        title = title.strip()
        if len(title) < 10:
            cli.error("Title too vague.")
        task.metadata["Ti"] = title
        updated = True
        
    if story:
        task.parts["story"] = story
        updated = True
    if tech:
        task.parts["tech"] = tech
        updated = True
    if criteria:
        if isinstance(criteria, list):
            task.parts["criteria"] = "\n".join(f"- [ ] {c}" for c in criteria)
        else:
            task.parts["criteria"] = criteria
        updated = True
    if plan:
        if isinstance(plan, list):
            task.parts["plan"] = "\n".join(f"{i}. {p}" for i, p in enumerate(plan, 1))
        else:
            task.parts["plan"] = plan
        updated = True
    if repro:
        if isinstance(repro, list):
            task.parts["repro"] = "\n".join(f"{i}. {r}" for i, r in enumerate(repro, 1))
        else:
            task.parts["repro"] = repro
        updated = True

    if notes or progress or findings or mitigations:
        n = task.parts.get("notes", "- Progress: \n- Findings: \n- Mitigations: \n")
        if notes: n = notes
        if progress: n = re.sub(r"- Progress:.*", f"- Progress: {progress}", n)
        if findings: n = re.sub(r"- Findings:.*", f"- Findings: {findings}", n)
        if mitigations: n = re.sub(r"- Mitigations:.*", f"- Mitigations: {mitigations}", n)
        task.parts["notes"] = n
        updated = True

    if tests_passed is not None:
        task.metadata["Tp"] = bool(tests_passed)
        updated = True

    if priority is not None:
        task.metadata["Pr"] = priority
        updated = True

    if regression_check is not None:
        task.metadata["Rc"] = True if regression_check else ""
        updated = True

    if updated:
        cli._atomic_write(filepath, task)
        dump_path = os.path.join(filepath, CURRENT_TASK_FILENAME)
        if os.path.exists(dump_path):
            dump = FM.load(dump_path)
            dump.parts["content"] = task.parts.get("notes", "")
            cli._atomic_write(dump_path, dump)
            
        cli._append_log(filepath, "Mod")
        cli._run_git(["add", "--all"], cwd=cli.tasks_path)
        cli._run_git(["commit", "--allow-empty", "-m", f"Mod {os.path.basename(filepath)}"], cwd=cli.tasks_path)
        
        cli.log(f"Modified: [{task.metadata.get('Id', '')}] {tt} | {task.metadata.get('Ti', '')}")
        
        _, branch = parse_filename(os.path.basename(filepath))
        # Ensure branch exists logic if needed
    else:
        cli.log("No changes.")
        
    cli.finish({
        "id": task.metadata.get("Id"),
        "task_id": task_id,
        "title": task.metadata.get("Ti", ""),
    })
