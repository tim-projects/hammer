import os
import shutil
import subprocess
import sys
import tempfile

import pytest

from tasks_ai.cli import TasksCLI


@pytest.fixture
def setup_tasks():
    if not hasattr(sys, '_called_from_test'):
        sys._called_from_test = True
    test_dir = tempfile.mkdtemp()
    repo_dir = os.path.join(test_dir, 'repo')
    os.makedirs(repo_dir)
    subprocess.run(['git', 'init'], cwd=repo_dir, capture_output=True, check=False)
    subprocess.run(['git', 'config', 'user.email', 'test@example.com'], cwd=repo_dir, check=False)
    subprocess.run(['git', 'config', 'user.name', 'Test User'], cwd=repo_dir, check=False)
    old_cwd = os.getcwd()
    os.chdir(repo_dir)
    cli = TasksCLI()
    cli.init()
    yield cli
    os.chdir(old_cwd)
    shutil.rmtree(test_dir)
    del sys._called_from_test

def test_create_and_modify(setup_tasks):
    cli = setup_tasks
    cli.create('Valid Task Title', story='As a user I want to create a task.', tech='Python and Markdown.', criteria='Task is created successfully.', plan='1. Call create\n2. Verify file')
    task_id = '1'
    filepath, state = cli.find_task(task_id)
    assert state == 'BACKLOG'
    assert filepath is not None
    cli.modify(task_id, title='Updated Valid Task Title')
    filepath, _ = cli.find_task(task_id)
    assert filepath is not None

def test_move_and_delete(setup_tasks):
    cli = setup_tasks
    cli.create('Move Test Task Name Here', story='As a user I want to move tasks between states.', tech='Python and Git for state management.', criteria='State changes correctly and task moves as expected.', plan='1. Move to READY\n2. Verify state\n3. Complete workflow')
    task_id = '1'
    cli.modify(task_id, story='As a user I want to move tasks between states.', tech='Python and Git for state management.', criteria='State changes correctly and task moves as expected.', plan='1. Move to READY\n2. Verify state\n3. Complete workflow')
    cli.move(task_id, 'READY')
    _, state = cli.find_task(task_id)
    assert state == 'READY'
    from tasks_ai.file_manager import FM
    try:
        cli.delete(task_id)
    except SystemExit:
        pass
    path, _ = cli.find_task(task_id)
    task = FM.load(path)
    assert 'DeleteCode' in task.metadata
    code = task.metadata['DeleteCode']
    cli.delete(task_id, confirm=code)
    path, _ = cli.find_task(task_id)
    assert path is None

def test_link_tasks(setup_tasks):
    cli = setup_tasks
    cli.create('Task A Title Long Enough', story='As a user I want to link tasks together.', tech='Python and Git for managing task links.', criteria='Linking works correctly between tasks.', plan='1. Create two tasks\n2. Link them together\n3. Verify link exists')
    cli.create('Task B Title Long Enough', story='As a user I want to link tasks together for dependencies.', tech='Python and Git for managing task links.', criteria='Linking works correctly between tasks.', plan='1. Create two tasks\n2. Link them together\n3. Verify link exists')
    cli.link('1', '2')
    from tasks_ai.file_manager import FM
    path, _ = cli.find_task('1')
    task = FM.load(path)
    assert any('2' in b for b in task.metadata.get('Bl', []))

def test_restore_and_undo(setup_tasks):
    cli = setup_tasks
    cli.create('Task to Undo/Restore', story='As a user I want a story that is long enough.', tech='Technical details that are long enough.', criteria='Acceptance criteria that are long enough.', plan='1. Implementation plan that is long enough.')
    task_id = '1'
    cli.modify(task_id, title='Modified Title')
    try:
        cli.undo(task_id)
    except SystemExit:
        pass
    path, _ = cli.find_task(task_id)
    from tasks_ai.file_manager import FM
    task = FM.load(path)
    assert task.metadata.get('Ti') == 'Task to Undo/Restore'