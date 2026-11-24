import os
import shutil

from ..constants import STATE_FOLDERS
from ..file_manager import FM
from ..guard_engine import GuardUnavailable
from ..pipeline_hooks import get_guard_engine
from ..utils import (
    commit_task_paths,
    derive_task_folder,
    derive_task_id,
    parse_filename,
    worktree_path_matches,
)

# Every guard anomaly is structural: none are repaired by doctor.
REPAIRABLE_GUARD_CODES = frozenset()


def extract_id_from_string(s):
    """Extract numeric ID from string if it starts with digits followed by hyphen"""
    if not s or not isinstance(s, str):
        return None
    if "-" in s:
        parts = s.split("-", 1)
        if parts[0].isdigit():
            return int(parts[0])
    return None


def run(cli, fix=False):
    """Execution logic for 'tasks doctor'."""
    bugs = []
    fix_id = None
    if isinstance(fix, str):
        fix_id = int(fix)

    # Check each state folder for inconsistencies
    guard_tasks = []
    for state, folder in STATE_FOLDERS.items():
        state_path = os.path.join(cli.tasks_path, folder)
        if not os.path.exists(state_path):
            continue

        for item in os.listdir(state_path):
            if item == ".gitkeep":
                continue

            item_path = os.path.join(state_path, item)
            if not os.path.isdir(item_path):
                continue

            # Load task
            task = FM.load(item_path)

            # Get IDs from different sources
            dir_id = extract_id_from_string(item)
            metadata_id = task.metadata.get("Id")
            branch_id = None
            branch_from_metadata = task.metadata.get("Br")

            if branch_from_metadata and isinstance(branch_from_metadata, str):
                branch_id = extract_id_from_string(branch_from_metadata)

            # Determine what the correct ID should be
            correct_id = None

            if metadata_id and str(metadata_id).isdigit():
                correct_id = int(metadata_id)
            elif branch_id is not None:
                correct_id = branch_id
            elif dir_id is not None:
                correct_id = dir_id

            if correct_id is None:
                continue

            guard_tasks.append((correct_id, branch_from_metadata))

            # If fix_id is provided, only process that task
            if fix_id is not None and correct_id != fix_id:
                continue

            # Check for inconsistencies
            inconsistencies = []

            # Check metadata.Id
            if not (
                metadata_id
                and str(metadata_id).isdigit()
                and int(metadata_id) == correct_id
            ):
                inconsistencies.append(("metadata.Id", metadata_id, correct_id))

            # Check metadata.Br
            expected_br = None
            # Try to construct expected branch from task metadata
            title_for_branch = task.metadata.get("Ti", "")
            if not title_for_branch:
                # Try to get title from directory name if metadata is missing
                if "-" in item and len(item.split("-", 2)) >= 3:
                    title_for_branch = "-".join(item.split("-", 2)[2:])
                else:
                    title_for_branch = "unknown"

            task_type, _ = parse_filename(item)
            task_type = task.metadata.get("Ty", task_type)

            expected_br = derive_task_id(correct_id, task_type, title_for_branch)
            expected_dir = derive_task_folder(correct_id, task_type, title_for_branch)
            legacy_br = expected_dir
            valid_branches = {expected_br, legacy_br}

            if not (
                branch_from_metadata
                and isinstance(branch_from_metadata, str)
                and branch_from_metadata in valid_branches
            ):
                inconsistencies.append(
                    ("metadata.Br", branch_from_metadata, expected_br)
                )

            # Check state mismatch: metadata state should match folder
            metadata_state = task.metadata.get("St")
            if metadata_state and metadata_state != state:
                inconsistencies.append(
                    (
                        "state-mismatch",
                        f"metadata.St={metadata_state}",
                        f"folder={state}",
                    )
                )

            # Check directory name
            if item != expected_dir:
                inconsistencies.append(("directory name", item, expected_dir))

            # The worktree directory must be the branch name, so no agent has to
            # guess which spelling resolves the task's path.
            wt_path = cli.git.worktrees.get_worktree_path(str(correct_id))
            expected_worktree_branch = (
                branch_from_metadata
                if branch_from_metadata in valid_branches
                else expected_br
            )
            if wt_path and not worktree_path_matches(
                wt_path, cli.git.worktrees.worktrees_base, expected_worktree_branch
            ):
                inconsistencies.append(
                    (
                        "worktree path",
                        wt_path,
                        os.path.join(
                            cli.git.worktrees.worktrees_base, expected_worktree_branch
                        ),
                    )
                )

            # If there are inconsistencies and fix is enabled, repair them
            if inconsistencies and fix:
                # Determine the correct directory name
                correct_dir_name = expected_dir

                # Determine target state folder based on metadata state or current folder
                target_state = task.metadata.get("St", state)
                target_folder = STATE_FOLDERS.get(target_state, state)
                target_path = os.path.join(
                    cli.tasks_path, target_folder, correct_dir_name
                )

                # Only move if directory name is wrong or state folder is wrong
                if item != correct_dir_name or state != target_state:
                    # Ensure target doesn't already exist
                    if not os.path.exists(target_path):
                        # Move the directory to the correct state folder
                        shutil.move(item_path, target_path)
                        item_path = target_path  # Update path for subsequent operations

                        # Log the move
                        cli.log(
                            f"Moved task directory: {item} [{state}] -> {correct_dir_name} [{target_state}]"
                        )
                    else:
                        cli.log(
                            f"Cannot move {item} to {target_path}: target already exists"
                        )
                        # Skip fixing if target exists to avoid data loss
                        inconsistencies = [
                            (
                                "state-mismatch",
                                f"{item} in {state}",
                                f"{correct_dir_name} in {target_state}",
                            )
                        ]

                # Fix metadata.Id if wrong
                id_changed = False
                if not (
                    metadata_id
                    and str(metadata_id).isdigit()
                    and int(metadata_id) == correct_id
                ):
                    task.metadata["Id"] = correct_id
                    id_changed = True

                # Fix metadata.Br if wrong (independent of Id fix)
                if not (
                    branch_from_metadata
                    and isinstance(branch_from_metadata, str)
                    and branch_from_metadata in valid_branches
                ):
                    task.metadata["Br"] = expected_br
                    id_changed = True

                # Fix state mismatch if needed
                if metadata_state and metadata_state != target_state:
                    task.metadata["St"] = target_state
                    id_changed = True

                if id_changed:
                    # Save the fixed metadata
                    FM.dump(task, item_path)
                    cli.log(
                        f"Fixed metadata for task {item_path}: Id={correct_id}, Br={expected_br}, St={target_state}"
                    )

                # If we moved the directory, we need to reload the task for git operations
                if item != correct_dir_name or state != target_state:
                    task = FM.load(item_path)

                # Git operations to record the fixes. Scoped to this task's
                # old and new paths: the store-wide add this replaces committed
                # every other agent's pending work as 'Doctor: fixed...'.
                commit_task_paths(
                    cli,
                    item_path,
                    f"Doctor: fixed task inconsistencies for {correct_dir_name}",
                    os.path.join(state_path, item),
                )

            # Report bugs (whether fixed or not)
            if inconsistencies:
                for field, actual, expected in inconsistencies:
                    bugs.append(
                        {
                            "id": f"{state}-{item}-{field}",
                            "title": f"Task {field} mismatch: {item}",
                            "repro": "Run 'hammer tasks list' to see task ID/branch mismatches",
                            "expected": f"{field} should be '{expected}'",
                            "actual": f"{field} is '{actual}'",
                        }
                    )

    # Guard anomalies are structural: the correct winner is ambiguous, so
    # doctor reports them but never repairs them.
    try:
        engine = get_guard_engine(cli)
        guard_findings = engine.scan()
        for task_id, branch in guard_tasks:
            guard_findings.extend(
                finding
                for finding in engine.verdict(
                    task_id, to_state="TESTING", branch=branch
                )
                if finding["code"] == "GUARD_BRANCH_MISSING"
            )
    except GuardUnavailable as exc:
        guard_findings = [
            {
                "code": "GUARD_UNAVAILABLE",
                "task_id": None,
                "detail": str(exc),
            }
        ]

    if fix_id is not None:
        guard_findings = [
            finding
            for finding in guard_findings
            if finding.get("task_id") in (None, fix_id)
        ]

    for finding in guard_findings:
        code = finding["code"]
        if code in REPAIRABLE_GUARD_CODES:
            continue
        task_id = finding.get("task_id")
        detail = finding.get("detail", "")
        hint = cli.messages.get_hint(code, task_id=task_id, branch="", to_state="")
        bugs.append(
            {
                "id": code,
                "title": code.replace("_", " ").title(),
                "code": code,
                "task_id": task_id,
                "detail": detail,
                "hint": hint,
                "repairable": False,
                "repro": "Run 'hammer tasks doctor' to see the blocking guard anomaly",
                "expected": "The guard engine reports no structural anomaly",
                "actual": detail,
            }
        )

    if bugs:
        cli.log(f"Found {len(bugs)} issues:")
        for b in bugs:
            if "code" in b:
                cli.log(f"- {b['code']} [{b['task_id']}]: {b['detail']}")
                cli.log(f"  {b['hint']}")
            else:
                cli.log(f"- {b['title']} ({b['id']})")
        if fix:
            cli.log("Issues have been fixed.")
    else:
        cli.log("No issues found.")

    cli.finish({"bugs": bugs})
