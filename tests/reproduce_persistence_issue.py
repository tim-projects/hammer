import os
import subprocess


def run_dev(cmd):
    full_cmd = ['./hammer', 'tasks', '--dev'] + cmd
    return subprocess.run(full_cmd, capture_output=True, text=True, check=False)
subprocess.run(['./hammer', 'tasks', '--dev', 'init', '--force'], capture_output=True, check=False)
task_dir = '/tmp/.tasks/backlog/1-task-persistent-test-task-name'
run_dev(['create', 'Persistent Test Task Name', '--story', 'Sufficiently long story content here to pass validation', '--tech', 'Sufficiently long technical description here to pass validation', '--criteria', '- [ ] Acceptance Criteria Task', '--plan', 'Sufficiently long planning details here'])
run_dev(['modify', '1', '--criteria', '- [x] Acceptance Criteria Task'])
with open(os.path.join(task_dir, 'criteria.md'), 'r') as f:
    print(f'Criteria: {f.read()}')