import os

import yaml


def load_config(tasks_path):
    config_path = os.path.join(tasks_path, 'config.yaml')
    if os.path.exists(config_path):
        try:
            with open(config_path, 'r') as f:
                return yaml.safe_load(f) or {}
        except Exception:  # noqa: BLE001
            return {}
    return {}

def get_workflows(tasks_path):
    cfg = load_config(tasks_path)
    return cfg.get('workflows', {})

def save_config(tasks_path, cfg):
    config_path = os.path.join(tasks_path, 'config.yaml')
    try:
        with open(config_path, 'w') as f:
            yaml.safe_dump(cfg, f)
    except Exception:  # noqa: BLE001, S110
        pass
TASKS_DIR = '.tasks'
TASKS_BRANCH = 'tasks'
CURRENT_TASK_FILENAME = 'current-task.md'
STATE_FOLDERS = {'BACKLOG': 'backlog', 'READY': 'ready', 'PROGRESSING': 'progressing', 'TESTING': 'testing', 'REVIEW': 'review', 'STAGING': 'staging', 'DONE': 'done', 'ARCHIVED': 'archived', 'REJECTED': 'rejected'}
PIPELINE_STAGES = ['BACKLOG', 'READY', 'PROGRESSING', 'TESTING', 'REVIEW', 'STAGING', 'DONE', 'ARCHIVED']
DEFAULT_ALLOWED_TRANSITIONS = {'BACKLOG': ['READY', 'REJECTED'], 'READY': ['PROGRESSING'], 'PROGRESSING': ['TESTING', 'BLOCKED', 'REJECTED'], 'TESTING': ['REVIEW', 'BLOCKED', 'REJECTED', 'PROGRESSING'], 'REVIEW': ['STAGING', 'TESTING', 'BLOCKED', 'PROGRESSING', 'REJECTED'], 'STAGING': ['DONE', 'ARCHIVED', 'REVIEW', 'BLOCKED', 'REJECTED', 'PROGRESSING'], 'DONE': ['ARCHIVED', 'STAGING', 'TESTING', 'BLOCKED', 'PROGRESSING'], 'BLOCKED': ['READY', 'PROGRESSING', 'TESTING', 'REVIEW', 'STAGING', 'DONE'], 'ARCHIVED': ['READY', 'TESTING'], 'REJECTED': ['PROGRESSING']}
ALLOWED_TRANSITIONS = DEFAULT_ALLOWED_TRANSITIONS
KEY_MAP = {'Id': 'Id', 'Ti': 'Title', 'St': 'State', 'Cr': 'Created', 'Bl': 'BlockedBy', 'Pr': 'Priority', 'Ar': 'ArchivedAt', 'Tp': 'TestsPassed', 'Rc': 'RegressionCheck'}
ALLOWED_CONFIG_KEYS = {'story', 'tech', 'criteria', 'plan', 'tasks_dir', 'repo.lint', 'repo.test', 'repo.type_check', 'repo.format', 'repo.skip_user_test_prompt', 'workflows'}
AGENT_GUIDANCE = '\nAGENT OPERATIONAL PROTOCOL:\n0. HELP: Always use -j for JSON output. Use tasks <command> -h for any subcommand.\n1. OUTPUT: Always use -j flag for machine-parseable JSON. \n   Schema: {"success": bool, "error": str|null, "messages": [str], "data": {}}\n2. TASK REFERENCES: Use the numeric Id (e.g., "1") instead of the filename for all operations. \n   Run \'list\' to see task Ids alongside titles.\n\n   This bypasses the need for 3 separate move commands.\n4. CREATION: \'create\' requires --story, --tech, --criteria, and --plan. \n   --repro is mandatory for --type issue. Titles must be >= 10 chars.\n 6. REVIEW & REGRESSION CHECK:\n    - When moving to REVIEW, a diff is auto-generated at `.tasks/review/<task_id>.patch`.\n    - Audit the diff for regressions, breaking changes, or unexpected side-effects.\n    - If issues found, move task back to PROGRESSING/TESTING to fix, then re-test.\n    - Once clean, run `tasks modify <id> --regression-check` to set Rc flag.\n    - STAGING/DONE/ARCHIVED transitions require Rc flag (regression check passed).\n 7. PROGRESS: Use \'modify\' to update --progress, --findings, or --mitigations.\n    - Updates to the active task automatically sync to \'current-task.md\'.\n    - Use \'.tasks/progressing/<task_id>/current-task.md\' as primary scratchpad.\n 8. SYNC: Use \'checkpoint\' to pull git commits and current-task.md into task file.\n    Use \'hammer sync\' to keep testing, staging, and main branches aligned.\n  9. ARCHIVING: When moving STAGING -> ARCHIVED:\n     - Branch must be merged to main first (use \'hammer repo promote <branch>\')\n     - Use \'tasks move <id> ARCHIVED -y\' to auto-push and delete branch\n     - Or move to REJECTED if code was not merged\n 10. BACKUP & RESTORE:\n     - The \'tasks\' branch (local and remote) serves as a continuous backup of the .tasks worktree.\n     - Archiving a task automatically triggers a save to the remote \'tasks\' branch.\n     - Use \'hammer tasks restore\' to recover .tasks from backup if lost or corrupted.\n     - Use \'hammer tasks save\' to manually create a backup at any time.\n 11. RULES: \n     - All blockers (Bl) in metadata MUST be ARCHIVED before moving to PROGRESSING.\n     - Use \'list\' to find tasks and \'current\' to see full metadata/logs.\n 12. ERROR RECOVERY: If a command fails, read the \'error\' field in the JSON response. \n     The \'hint\' provides actionable next steps.\n'
RETENTION_DAYS = 90