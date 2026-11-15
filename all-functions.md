tasks_ai/commands.py:class Commands:
tasks_ai/file_manager.py:def _atomic_write(path, content):
tasks_ai/file_manager.py:class FM:
tasks_ai/pipeline.py:class PipelineError(Exception):
tasks_ai/pipeline.py:class PipelineService:
tasks_ai/counter.py:class TaskCounterProtector:
tasks_ai/git_client.py:class GitClient:
tasks_ai/help_text.py:def get_help_text():
tasks_ai/validation.py:class Validation:
tasks_ai/libs/list_layout.py:def render_table(all_data):
tasks_ai/cli.py:def get_terminal_width():
tasks_ai/cli.py:class TasksCLI:
tasks_ai/context.py:class ProjectContext:
tasks_ai/models.py:class Task:
tasks_ai/commands/save.py:def run(cli, branch="tasks", fatal=True):
tasks_ai/commands/modify.py:def run(cli, filename, task_type=None, title=None, story=None, tech=None, criteria=None, plan=None, repro=None, 
tasks_ai/commands/link.py:def run(cli, filename, blocked_by_filename):
tasks_ai/commands/move.py:def run(cli, filename, new_status, yes=False):
tasks_ai/commands/move.py:def move_logic(cli, filename, new_status, force=False, yes=False, sync=True):
tasks_ai/commands/cleanup.py:def run(cli, dry_run=False, yes=False):
tasks_ai/commands/create.py.bak:def run(cli, title, task_type="task", priority=None, story=None, tech=None, criteria=None, plan=None, repro=None, branch=False):
tasks_ai/commands/verify.py:def run(cli, task_id, proof):
tasks_ai/commands/list.py.bak:def run(cli, show_all=False):
tasks_ai/commands/checkpoint.py:def run(cli, filename=None):
tasks_ai/commands/current.py:def run(cli, filename=None):
tasks_ai/commands/delete.py:def run(cli, filename, confirm=None):
tasks_ai/commands/show.py:def run(cli, filename, section=None):
tasks_ai/commands/list.py:def run(cli, show_all=False):
tasks_ai/commands/create.py:def run(cli, title, task_type="task", priority=None, story=None, tech=None, criteria=None, plan=None, repro=None, branch=False):
tasks_ai/commands/audit.py:def run(cli, task_id):
tasks_ai/commands/doctor.py:def run(cli, fix=False):
tasks_ai/commands/config.py:def run(cli, action=None, key=None, value=None, save=False):
tasks_ai/audit.py:def generate_audit(task_id, patch_path, output_path):
tasks_ai/audit.py:def verify_audit(patch_path, audit_path):
tasks_ai/utils.py:def parse_filename(name: str) -> Tuple[str, str]:
tasks_ai/utils.py:def atomic_write(path: str, task_or_content: Any, fm=None):
tasks_ai/utils.py:def sync_task_content(cli, filepath, task, is_final=False) -> bool:
tasks_ai/utils.py:def perform_move(cli, task, current_state, new_status, filepath):
tasks_ai/utils.py:def has_path(start_id: str, target_id: str, tasks_path: str, fm, visited=None) -> bool:
