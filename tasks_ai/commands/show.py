import os
from ..constants import KEY_MAP, CURRENT_TASK_FILENAME
from ..file_manager import FM
from ..utils import parse_filename


def run(cli, filename, section=None):
    """Execution logic for 'tasks show'."""
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
                f"# TASK: {meta.get('Title', data['name'])}\n"
                f"- **Id**: {meta.get('Id', '')} | **State**: {meta.get('State', '')} | **Priority**: {meta.get('Priority', '')}\n"
                f"- **File**: `{data['file']}`\n"
                f"- **Type**: {data['type']} | **Branch**: `{data['branch']}`"
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
