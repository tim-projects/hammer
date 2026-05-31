import os
from ..constants import STATE_FOLDERS
from ..file_manager import FM
from ..utils import parse_filename, perform_move


def run(cli, filename, new_status, yes=False):
    """Execution logic for 'tasks move'."""
    filepath, current_state_from_folder = cli.find_task(filename)
    if not filepath:
        cli.error(
            f"Task '{filename}' not found.",
            hint="Use 'hammer tasks list' to see all available task filenames/IDs.",
        )
    task_type, _ = parse_filename(os.path.basename(filepath))
    allowed_transitions = cli.pipeline.get_allowed_transitions(task_type)
    
    # Handle multi-step transitions
    if "," in new_status:
        steps = [s.strip() for s in new_status.split(",")]
        
        # Perform each step individually, letting move_logic enforce gates
        for step in steps:
            # Re-fetch state for each step to validate current transition
            _, current_state = cli.find_task(filename)
            if current_state == step:
                continue
            
            # Perform individual move; move_logic now enforces ALL gates
            move_logic(cli, filename, step, force=False, yes=yes, sync=True)
            
        cli.log(f"Moved: [{cli.find_task(filename)[0].split('/')[-1]}] -> {new_status}")
        cli.finish({"status": new_status})
        return

    # Single-step transition
    cli.pipeline.check_transition(cli, filename, new_status)

    task = FM.load(filepath)
    fname = os.path.basename(filepath)
    task_id = fname.rsplit(".", 1)[0]
    title = task.metadata.get("Ti", "")
    task_id_num = task.metadata.get("Id", "")
    tt, _ = parse_filename(fname)

    # Chained auto-promotion
    max_steps = 10
    while (
        new_status not in allowed_transitions.get(current_state_from_folder, [])
        and current_state_from_folder != new_status
        and max_steps > 0
    ):
        allowed = allowed_transitions.get(current_state_from_folder, [])
        if not allowed:
            break

        next_step = allowed[0]
        cli.log(f"Auto-promoting: {current_state_from_folder} -> {next_step}")
        try:
            move_logic(cli, filename, next_step, force=False, yes=yes, sync=True)
            filepath, current_state_from_folder = cli.find_task(filename)
            max_steps -= 1
        except Exception as e:
            cli.error(f"Auto-promotion failed: {e}")

    move_logic(cli, filename, new_status, yes=yes)
    cli.log(f"Moved: [{task_id_num}] {tt} | {title} -> {new_status}")
    cli.finish(
        {
            "id": task_id_num,
            "task_id": task_id,
            "title": title,
            "status": new_status,
        }
    )


def move_logic(cli, filename, new_status, force=False, yes=False, sync=True):
    """Internal move logic with pipeline gate enforcement."""
    new_status = new_status.upper()
    filepath, current_state = cli.find_task(filename)
    if not filepath:
        cli.error(f"Task '{filename}' not found.")

    filepath_str = str(filepath)
    task = FM.load(filepath_str)
    task_type, _ = parse_filename(os.path.basename(filepath_str))
    allowed_transitions = cli.pipeline.get_allowed_transitions(task_type)

    if not force:
        cli._validate_pipeline_gate(task, new_status, filepath_str)

    if current_state == new_status:
        return

    # Perform Git Merge if applicable
    if sync and not force:
        cli._git_merge_transition(task, new_status, yes=yes)

    # Archived check: Enforce branch merge to main
    if new_status == "ARCHIVED" and not force:
        _, branch = parse_filename(os.path.basename(filepath_str))
        if not cli.git.is_merged(branch, "main"):
            cli.error("BRANCH_NOT_MERGED", branch=branch)

    if (
        new_status not in allowed_transitions.get(current_state, [])
        and not force
    ):
        cli.error(
            "FORBIDDEN_TRANSITION",
            from_state=current_state,
            to_state=new_status
        )

    # 1. Run Exit Hooks (Pre-move checks and actions)
    cli.hook_registry.run_exit_hooks(cli, task, current_state, new_status, filepath_str)

    # 2. Final Execution (Physical move)
    new_task = perform_move(cli, task, current_state, new_status, filepath_str)

    # 3. Run Enter Hooks (Post-move actions)
    new_filepath = os.path.join(
        cli.tasks_path,
        STATE_FOLDERS[new_status],
        os.path.basename(filepath_str),
    )
    cli.hook_registry.run_enter_hooks(cli, new_task, current_state, new_status, new_filepath)
