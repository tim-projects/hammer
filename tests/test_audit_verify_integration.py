import json
import os
import subprocess

def run_dev(cmd, force=False):
    full_cmd = ['./hammer', 'tasks', '--dev'] + cmd
    if force and cmd and (cmd[0] == 'init'):
        full_cmd.append('--force')
    result = subprocess.run(full_cmd, capture_output=True, text=True, check=False)
    return result

def setup_dev_config():
    dev_tasks_dir = os.environ.get('HAMMER_DEV_TASKS_DIR', '/tmp/.tasks')
    config_data = {'repo': {'lint': '/bin/true', 'test': '/bin/true', 'type_check': '/bin/true', 'format': '/bin/true'}}
    with open(os.path.join(dev_tasks_dir, 'config.yaml'), 'w') as f:
        json.dump(config_data, f, indent=2)

def test_pipeline_audit_verify_gates():
    run_dev(['init'], force=True)
    setup_dev_config()
    run_dev(['create', 'Integration Test Task', '--story', 'Sufficiently long story content here to pass validation', '--tech', 'Sufficiently long technical description here to pass validation', '--criteria', '- [ ] Sufficiently long acceptance criteria here to pass validation', '--plan', 'Sufficiently long planning details here to pass validation'])
    task_id = '1'
    run_dev(['modify', task_id, '--criteria', '- [x] Sufficiently long acceptance criteria here to pass validation'])
    run_dev(['move', task_id, 'READY,PROGRESSING,TESTING,REVIEW'])
    run_dev(['audit', task_id])
    run_dev(['verify', task_id, '--proof', 'Integration proof'])
    run_dev(['modify', task_id, '--regression-check'])
    move_res = run_dev(['move', task_id, 'STAGING'])
    assert move_res.returncode == 0, f'Failed to move to STAGING: {move_res.stderr} {move_res.stdout}'