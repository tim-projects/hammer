import os
from datetime import datetime
from ..constants import STATE_FOLDERS
from ..file_manager import FM
from ..utils import parse_filename, perform_move
from ..pipeline import PipelineError


def run(cli, filename, new_status=None, yes=False):
    """Execution logic for 'tasks move'."""
    filepath, current_state = cli.find_task(filename)
    if not filepath:
        cli.error("TASK_NOT_FOUND", filename=filename)

    task = FM.load(filepath)

    # 1. Derive target status if not provided
    if not new_status:
        new_status = cli.git.get_next_logical_state(current_state)
        if not new_status:
            cli.log(f"Task {filename} is already in terminal state {current_state}.")
            return

        # Special case: DONE -> ARCHIVED requires 7-day grace period
        if current_state == "DONE" and new_status == "ARCHIVED":
            done_at = task.metadata.get("DoneAt")
            if done_at:
                elapsed = datetime.now().timestamp() - done_at
                grace_period = 7 * 24 * 60 * 60
                if elapsed < grace_period:
                    days_left = round((grace_period - elapsed) / (24 * 3600), 1)
                    cli.log(
                        f"Task {filename} is DONE. Auto-archiving in {days_left} days."
                    )
                    return
            else:
                # If DoneAt is missing, set it now and wait 7 days
                task.metadata["DoneAt"] = datetime.now().timestamp()
                cli._atomic_write(filepath, task)
                cli.log(
                    f"Task {filename} marked as DONE today. Auto-archiving in 7 days."
                )
                return

    # Single-step transition
    cli.pipeline.check_transition(cli, filename, new_status)

    fname = os.path.basename(filepath)
    task_id = fname.rsplit(".", 1)[0]
    title = task.metadata.get("Ti", "")
    task_id_num = task.metadata.get("Id", "")
    tt, _ = parse_filename(fname)

    # Check if we are already in the target state
    if current_state == new_status.upper():
        cli.log(f"You are already on {new_status.upper()}")
        return

    if move_logic(cli, filename, new_status, yes=yes):
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
        cli.error("TASK_NOT_FOUND", filename=filename)

    if current_state == new_status:
        cli.log(f"You are already on {new_status}")
        return False

    filepath_str = str(filepath)
    task = FM.load(filepath_str)
    task_type, _ = parse_filename(os.path.basename(filepath_str))
    allowed_transitions = cli.pipeline.get_allowed_transitions(task_type)

    if not force:
        try:
            cli._validate_pipeline_gate(task, new_status, filepath_str)
        except PipelineError as e:
            # Handle audit failures: move back to PROGRESSING and instruct user
            if e.code in [
                "AUDIT_MISSING",
                "AUDIT_PATCH_MISSING",
                "PROOF_MISSING",
                "HASH_MISSING",
                "AUDIT_MISMATCH",
                "INTEGRITY_MISMATCH",
            ]:
                cli.log(f"Audit failed: {e.code}. Moving task back to PROGRESSING.")
                perform_move(cli, task, current_state, "PROGRESSING", filepath_str)
                cli.error(
                    "AUDIT_FAILURE",
                    hint_code="AUDIT_FAILURE",
                    audit_code=e.code,
                    task_id=str(task.metadata.get("Id", "unknown")),
                )
            else:
                raise e

    # 1. Run Exit Hooks (Pre-move checks and actions)
    cli.hook_registry.run_exit_hooks(
        cli, task, current_state, new_status, filepath_str, force=force
    )

    if not force:
        if new_status not in allowed_transitions.get(current_state, []):
            cli.error(
                "FORBIDDEN_TRANSITION",
                from_state=current_state,
                to_state=new_status,
                task_id=os.path.basename(filepath_str).split("-")[0],
                next_valid_state="PROGRESSING",
            )

        # Archived check: Enforce branch merge to main
        if new_status == "ARCHIVED":
            _, branch = parse_filename(os.path.basename(filepath_str))
            if not cli.git.is_merged(branch, "main"):
                cli.error("BRANCH_NOT_MERGED", branch=branch)

    # Perform Git Merge if applicable
    if sync and not force:
        cli._git_merge_transition(task, new_status, yes=yes)

    # 2. Final Execution (Physical move)
    new_task = perform_move(cli, task, current_state, new_status, filepath_str)

    # 3. Run Enter Hooks (Post-move actions)
    new_filepath = os.path.join(
        cli.tasks_path,
        STATE_FOLDERS[new_status],
        os.path.basename(filepath_str),
    )
    cli.hook_registry.run_enter_hooks(
        cli, new_task, current_state, new_status, new_filepath
    )
    return True
