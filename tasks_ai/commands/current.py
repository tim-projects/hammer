import os
from ..constants import KEY_MAP, CURRENT_TASK_FILENAME
from ..file_manager import FM
from ..utils import parse_filename

def run(cli, filename=None):
    """Execution logic for 'tasks current'."""
    filepath, task = cli.get_active_task(filename)
    if not filepath or not task:
        cli.error("No active task.")

    filepath_str = str(filepath)
    tn = os.path.basename(filepath_str)
    tt, br = parse_filename(tn)
    
    data = {
        "file": os.path.relpath(filepath_str, cli.root),
        "name": tn,
        "type": tt,
        "branch": br,
        "metadata": {
            str(KEY_MAP.get(str(k), k)): v for k, v in task.metadata.items()
        },
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

    if not cli.as_json:
        meta = data['metadata']
        print(f"# TASK: {meta.get('Title', data['name'])}\n"
              f"- **File**: `{data['file']}`\n"
              f"- **Type**: {data['type']} | **Branch**: `{data['branch']}`")
        for k, v in data["metadata"].items():
            if k != "Title":
                print(f"- **{k}**: {v}")
        if "dump" in data:
            print(f"\n## Active Progress\n{data['dump']['content']}")
        else:
            print(f"\n## Content\n{task.content}")

    cli.finish(data)
