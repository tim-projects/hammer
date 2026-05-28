import os
from ..constants import STATE_FOLDERS, ALLOWED_TRANSITIONS, CURRENT_TASK_FILENAME
from ..file_manager import FM
from ..models import Task
from ..utils import parse_filename, perform_move

def run(cli, filename, new_status, yes=False):
    """Execution logic for 'tasks move'."""
    cli.pipeline.check_transition(cli, filename, new_status)
    filepath, current_state_from_folder = cli.find_task(filename)
    if not filepath:
        cli.error(
            f"Task '{filename}' not found.",
            hint="Use 'hammer tasks list' to see all available task filenames/IDs.",
        )
    
    task = FM.load(filepath)
    fname = os.path.basename(filepath)
    task_id = fname.rsplit(".", 1)[0]
    title = task.metadata.get("Ti", "")
    task_id_num = task.metadata.get("Id", "")
    tt, _ = parse_filename(fname)

    # Chained auto-promotion
    max_steps = 10
    while (
        new_status not in ALLOWED_TRANSITIONS.get(current_state_from_folder, [])
        and current_state_from_folder != new_status
        and max_steps > 0
    ):
        allowed = ALLOWED_TRANSITIONS.get(current_state_from_folder, [])
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
    cli.finish({
        "id": task_id_num,
        "task_id": task_id,
        "title": title,
        "status": new_status,
    })

def move_logic(cli, filename, new_status, force=False, yes=False, sync=True):
    """Internal move logic with pipeline gate enforcement."""
    new_status = new_status.upper()
    filepath, current_state = cli.find_task(filename)
    if not filepath:
        cli.error(f"Task '{filename}' not found.")
    
    filepath_str = str(filepath)
    task = FM.load(filepath_str)
    
    if not force:
        cli._validate_pipeline_gate(task, new_status)

    if current_state == new_status:
        return

    # Perform Git Merge if applicable
    if sync and not force:
        cli._git_merge_transition(task, new_status, yes=yes)

    # Archived from non-standard state check
    is_merged_branch = False
    if new_status == "ARCHIVED" and current_state not in ["DONE", "STAGING", "REJECTED"]:
        _, branch = parse_filename(os.path.basename(filepath_str))
        branch_commit = None
        if cli._run_git(["rev-parse", "--verify", branch]).returncode == 0:
            branch_commit = cli._run_git(["rev-parse", branch]).stdout.strip()
        
        if not branch_commit:
            origin_check = cli._run_git(["ls-remote", "--heads", "origin", branch]).stdout.strip()
            if origin_check:
                cli._run_git(["fetch", "origin", branch], cwd=cli.root)
                branch_commit = cli._run_git(["rev-parse", f"origin/{branch}"]).stdout.strip()

        if branch_commit:
            is_merged_branch = cli._run_git(["merge-base", "--is-ancestor", branch_commit, "main"]).returncode == 0

        if is_merged_branch:
            for flag in ["Rc", "Tp", "Vp"]:
                if not task.metadata.get(flag):
                    task.metadata[flag] = True
            task.metadata["Ar"] = "true"
            FM.dump(task, filepath_str)

    if new_status not in ALLOWED_TRANSITIONS.get(current_state, []) and not force and not is_merged_branch:
        hint = f"Allowed transitions from {current_state} are: {', '.join(ALLOWED_TRANSITIONS.get(current_state, []))}. Do not bypass this tool."
        if current_state == "REJECTED" and new_status == "ARCHIVED":
            hint += " Use 'hammer tasks delete <id>' to permanently remove the task."
        if is_merged_branch:
            hint += "\nNote: Branch is merged to main. You can archive this task directly."
        cli.error(
            f"Forbidden transition: {current_state} -> {new_status}",
            hint=f"Allowed transitions from {current_state} are: {', '.join(ALLOWED_TRANSITIONS.get(current_state, []))}. "
                 f"Pipeline flow: BACKLOG → READY → PROGRESSING → TESTING → REVIEW → STAGING → DONE → ARCHIVED. "
                 f"Do not bypass this tool."
        )

    # Gates and Validations
    if current_state == "TESTING" and new_status == "REVIEW":
        task = FM.load(filepath_str)
        if not task.metadata.get("Tp", False):
            cli.error("Tests must be passed before moving to REVIEW.", hint="Run 'hammer tasks modify <id> --tests-passed' to mark tests as passed.")
        cli._run_validation()
        cli._run_tests()
        cli.log("--- ⚠️  REVIEW GATE ENTERED ⚠️ ---\nMandatory gates remaining: Cryptographic Audit, Regression Check, and Staging Promotion.")

    if current_state in ["TESTING", "PROGRESSING"]:
        cli.log("Running pre-transition validation...")
        cli._run_validation()
        cli._run_tests()
    
    if current_state == "TESTING" and new_status != "REVIEW":
        cli._run_validation()
        task = FM.load(filepath_str)
        task.metadata["Vp"] = True
        FM.dump(task, filepath_str)

    if current_state == "PROGRESSING" and new_status == "TESTING":
        cli._run_validation()
        cli.log("Validation passed. Marking validation_passed...")
        task = FM.load(filepath_str)
        task.metadata["Vp"] = True
        FM.dump(task, filepath_str)

    # Content sufficiency checks
    def has_complete_content(t, fn):
        for part in ["story", "tech", "criteria", "plan"]:
            if not t.parts.get(part) or len(str(t.parts.get(part)).strip()) < 10:
                return False
        tt, _ = parse_filename(fn)
        if tt == "issue" and (not t.parts.get("repro") or len(str(t.parts.get("repro")).strip()) < 10):
            return False
        return True

    if current_state == "BACKLOG" and new_status not in ("BACKLOG", "REJECTED"):
        if not has_complete_content(task, os.path.basename(filepath_str)):
            cli.error("Task lacks required content to leave BACKLOG.")

    if new_status == "PROGRESSING":
        bl = task.metadata.get("Bl", [])
        for b in bl:
            _, bs = cli.find_task(str(b))
            if bs != "ARCHIVED":
                cli.error(f"Blocked by {b}. Blocker must be ARCHIVED first.")
        if not has_complete_content(task, os.path.basename(filepath_str)):
            cli.error("Task lacks sufficient detail to move to PROGRESSING.")

    # Branch checks
    _, branch = parse_filename(os.path.basename(filepath_str))
    branch_sha_res = cli._run_git(["rev-parse", branch])
    branch_sha = branch_sha_res.stdout.strip() if branch_sha_res.returncode == 0 else ""
    if not branch_sha:
        res = cli._run_git(["log", "-1", "--format=%H", branch])
        if res.returncode == 0:
            branch_sha = res.stdout.strip()

    if new_status == "PROGRESSING" and not branch_sha:
        has_origin = cli._run_git(["remote", "get-url", "origin"]).returncode == 0
        if has_origin:
            remote_check = cli._run_git(["ls-remote", "--heads", "origin", branch])
            if remote_check.stdout.strip():
                cli.log(f"Branch '{branch}' not found locally. Restoring from remote...")
                cli._run_git(["checkout", "-b", branch, f"origin/{branch}"], cwd=cli.root)
                branch_sha = cli._run_git(["rev-parse", branch]).stdout.strip()

    if not force:
        has_origin = cli._run_git(["remote", "get-url", "origin"]).returncode == 0
        if new_status in ("REVIEW", "STAGING", "DONE", "ARCHIVED"):
            if has_origin:
                if not cli._run_git(["ls-remote", "--heads", "origin", branch]).stdout:
                    cli.error(f"Branch '{branch}' not pushed to remote. Push and try again.")
        
        if new_status == "TESTING" and current_state in ("READY", "BACKLOG", "PROGRESSING"):
            # Detailed progress check (unstaged + commits vs testing/main)
            pass

    # Final Execution
    perform_move(cli, task, current_state, new_status, filepath_str)
    
    # Post-move hooks
    if new_status == "TESTING":
        from repo import cmd_promote, FLAGS
        FLAGS.update({"yes": yes, "quiet": cli.quiet, "json": True, "dev": cli.dev})
        try:
            cmd_promote(branch)
        except Exception as e:
            cli.error(f"Promotion failed: {e}")
    
    if new_status == "ARCHIVED":
        cli._run_git(["add", "--all"], cwd=cli.tasks_path)
        cli._run_git(["commit", "-m", f"Archive [{task.metadata.get('Id')}] {task.metadata.get('Ti')}"], cwd=cli.tasks_path)
        try:
            cli._push_tasks_branch("tasks", fatal=False)
        except Exception:
            pass
    else:
        cli._run_git(["add", "--all"], cwd=cli.tasks_path)
        cli._run_git(["commit", "--allow-empty", "-m", f"Mv {os.path.basename(filepath_str)} -> {new_status}"], cwd=cli.tasks_path)

    if new_status == "PROGRESSING":
        dump_path = os.path.join(os.path.join(cli.tasks_path, STATE_FOLDERS[new_status], os.path.basename(filepath_str)), CURRENT_TASK_FILENAME)
        d = Task(metadata={"Task": os.path.basename(filepath_str)}, parts={"content": task.parts.get("notes", "- Progress: \n")})
        cli._atomic_write(dump_path, d)

    if new_status == "REVIEW":
        cli._generate_review_diff(os.path.join(cli.tasks_path, STATE_FOLDERS[new_status], os.path.basename(filepath_str)), branch)
        task.metadata["Rc"] = ""
        cli._atomic_write(os.path.join(cli.tasks_path, STATE_FOLDERS[new_status], os.path.basename(filepath_str)), task)
