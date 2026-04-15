import pytest
import os
import shutil
import sys
import tempfile
import subprocess
from tasks_ai.cli import TasksCLI


@pytest.fixture
def setup_tasks():
    # Setup a temp environment
    sys._called_from_test = True  # type: ignore[attr-defined]
    test_dir = tempfile.mkdtemp()
    repo_dir = os.path.join(test_dir, "repo")
    os.makedirs(repo_dir)

    # Init git
    subprocess.run(["git", "init"], cwd=repo_dir, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo_dir)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=repo_dir)

    # Move to repo_dir
    old_cwd = os.getcwd()
    os.chdir(repo_dir)

    cli = TasksCLI()
    cli.init()

    yield cli

    # Cleanup
    os.chdir(old_cwd)
    shutil.rmtree(test_dir)
    del sys._called_from_test  # type: ignore[attr-defined]


def test_create_and_modify(setup_tasks):
    cli = setup_tasks
    cli.create(
        "Valid Task Title",
        story="As a user I want to create a task.",
        tech="Python and Markdown.",
        criteria="Task is created successfully.",
        plan="1. Call create\n2. Verify file",
    )
    task_id = "1"
    filepath, state = cli.find_task(task_id)
    assert state == "BACKLOG"
    assert filepath is not None

    cli.modify(task_id, title="Updated Valid Task Title")
    filepath, _ = cli.find_task(task_id)
    assert filepath is not None


def test_move_and_delete(setup_tasks):
    cli = setup_tasks
    cli.create(
        "Move Test Task Name",
        story="As a user I want to move tasks.",
        tech="Python logic.",
        criteria="State changes correctly.",
        plan="1. Move to READY\n2. Verify state",
    )
    task_id = "1"

    # We need to add repro for issues or make it a regular task
    # It's a regular task by default.
    # But it needs fields to leave BACKLOG.
    cli.modify(
        task_id,
        story="As a user I want to move tasks.",
        tech="Python logic.",
        criteria="State changes correctly.",
        plan="1. Move to READY\n2. Verify state",
    )

    # Move through states
    cli.move(task_id, "READY")
    _, state = cli.find_task(task_id)
    assert state == "READY"

    # Test delete confirmation
    from tasks_ai.file_manager import FM

    path, _ = cli.find_task(task_id)

    # First call marks for deletion
    try:
        cli.delete(task_id)
    except SystemExit:
        pass

    # Reload to get DeleteCode
    task = FM.load(path)
    assert "DeleteCode" in task.metadata

    code = task.metadata["DeleteCode"]
    cli.delete(task_id, confirm=code)
    path, _ = cli.find_task(task_id)
    assert path is None


def test_link_tasks(setup_tasks):
    cli = setup_tasks
    cli.create(
        "Task A Title Long",
        story="As a user I want to link tasks.",
        tech="Python and Git.",
        criteria="Linking works correctly.",
        plan="1. Create two tasks\n2. Link them",
    )
    cli.create(
        "Task B Title Long",
        story="As a user I want to link tasks.",
        tech="Python and Git.",
        criteria="Linking works correctly.",
        plan="1. Create two tasks\n2. Link them",
    )
    # Linking 1 to 2
    cli.link("1", "2")

    from tasks_ai.file_manager import FM

    path, _ = cli.find_task("1")
    task = FM.load(path)
    # TasksCLI.link adds the branch name or Id to 'Bl' list
    assert any("2" in b for b in task.metadata.get("Bl", []))
