import re
def get_task_id(branch_name):
    match = re.match(r'^(\d+)-', branch_name)
    return match.group(1) if match else None

print(get_task_id('274-task-formalize-commit-messages-to-i'))
