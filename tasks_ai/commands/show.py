import os

from ..constants import CURRENT_TASK_FILENAME, KEY_MAP, STATE_FOLDERS
from ..file_manager import FM
from ..utils import parse_filename


def _task_record(cli, path, state):
    """Metadata plus every .md file of one task directory."""
    task = FM.load(path)
    tn = os.path.basename(path)
    tt, br = parse_filename(tn)
    files = {
        name: content
        for name, content in task.parts.items()
        if os.path.exists(os.path.join(path, f"{name}.md"))
    }
    return {
        "state": state,
        "file": os.path.relpath(path, cli.root),
        "name": tn,
        "type": tt,
        "branch": br,
        "metadata": {str(KEY_MAP.get(str(k), k)): v for k, v in task.metadata.items()},
        "files": files,
    }


def _print_record(record):
    meta = record["metadata"]
    print(
        f"# TASK: {meta.get('Title', record['name'])}\n- **Id**: {meta.get('Id', '')} | **State**: {meta.get('State', record['state'])} | **Priority**: {meta.get('Priority', '')}\n- **File**: `{record['file']}`\n- **Type**: {record['type']} | **Branch**: `{record['branch']}`"
    )
    for name in sorted(record["files"]):
        print(f"\n## {name}\n{record['files'][name].strip()}")


def run_all(cli):
    """Execution logic for 'tasks show --all': every task's .md files and metadata."""
    if not os.path.exists(cli.tasks_path):
        cli.error("INIT_REQUIRED")

    records = []
    for state, folder in STATE_FOLDERS.items():
        fp = os.path.join(cli.tasks_path, folder)
        if not os.path.isdir(fp):
            continue
        for item in sorted(os.listdir(fp)):
            path = os.path.join(fp, item)
            if item == ".gitkeep" or not os.path.isdir(path):
                continue
            try:
                records.append(_task_record(cli, path, state))
            except Exception:  # noqa: BLE001, S112
                continue

    if not cli.as_json:
        for record in records:
            _print_record(record)
            print()
    cli.finish(records)


def run_task_all(cli, filename):
    """Execution logic for 'tasks show <id> --all': all .md files and metadata of one task."""
    filepath, _ = cli.find_task(filename)
    if not filepath:
        cli.error(
            f"Task '{filename}' not found.",
            hint="Use 'hammer tasks list' to see available task Ids.",
        )
    filepath_str = str(filepath)
    state = next(
        (
            s
            for s, folder in STATE_FOLDERS.items()
            if os.path.basename(os.path.dirname(filepath_str)) == folder
        ),
        None,
    )
    record = _task_record(cli, filepath_str, state)
    if not cli.as_json:
        _print_record(record)
    cli.finish(record)


def run(cli, filename, section=None, show_all=False):
    """Execution logic for 'tasks show'."""
    if show_all:
        return run_task_all(cli, filename) if filename else run_all(cli)
    filepath, _ = cli.find_task(filename)
    if not filepath:
        cli.error(
            f"Task '{filename}' not found.",
            hint="Use 'hammer tasks list' to see available task Ids.",
        )
    filepath_str = str(filepath)
    task = FM.load(filepath_str)
    tn = os.path.basename(filepath_str)
    tt, br = parse_filename(tn)
    data = {
        "file": os.path.relpath(filepath_str, cli.root),
        "name": tn,
        "type": tt,
        "branch": br,
        "metadata": {str(KEY_MAP.get(str(k), k)): v for k, v in task.metadata.items()},
        "log_file": os.path.relpath(
            os.path.join(filepath_str, "activity.log"), cli.root
        ),
    }
    dp = os.path.join(filepath_str, CURRENT_TASK_FILENAME)
    if os.path.exists(dp):
        d = FM.load(dp)
        data["dump"] = {
            "file": os.path.relpath(dp, cli.root),
            "content": d.parts.get("content", "").strip(),
        }
    section_map = {
        "story": ("Story", task.parts.get("story", "No story")),
        "tech": ("Technical", task.parts.get("tech", "No technical details")),
        "criteria": ("Criteria", task.parts.get("criteria", "No criteria")),
        "plan": ("Plan", task.parts.get("plan", "No plan")),
        "repro": ("Reproduction", task.parts.get("repro", "No reproduction steps")),
        "notes": ("Notes", task.parts.get("notes", "No notes")),
        "progress": (
            "Active Progress",
            data.get("dump", {}).get("content", "No active progress"),
        ),
    }
    if not cli.as_json:
        if section:
            if section in section_map:
                title, content = section_map[section]
                print(f"## {title}\n{content}")
            else:
                cli.error("UNKNOWN_SECTION", section=section)
        else:
            meta = data["metadata"]
            print(
                f"# TASK: {meta.get('Title', data['name'])}\n- **Id**: {meta.get('Id', '')} | **State**: {meta.get('State', '')} | **Priority**: {meta.get('Priority', '')}\n- **File**: `{data['file']}`\n- **Type**: {data['type']} | **Branch**: `{data['branch']}`"
            )
            print(f"\n## Story\n{task.parts.get('story', 'No story')}")
            print(f"\n## Technical\n{task.parts.get('tech', 'No technical details')}")
            print(f"\n## Criteria\n{task.parts.get('criteria', 'No criteria')}")
            print(f"\n## Plan\n{task.parts.get('plan', 'No plan')}")
            if task.parts.get("repro"):
                print(f"\n## Reproduction\n{task.parts.get('repro')}")
            if data.get("dump"):
                print(f"\n## Active Progress\n{data['dump']['content']}")
    cli.finish(data)
