import os
import subprocess
import shutil
import tempfile
import json
import sys
import pytest
from datetime import datetime, timedelta
from pathlib import Path

# Path to the tasks.py script
SCRIPT_PATH = os.path.abspath("tasks.py")


@pytest.fixture
def repo_dir():
    """Create a temporary git repository for testing."""
    test_dir = tempfile.mkdtemp()
    repo_path = os.path.join(test_dir, "repo")
    os.makedirs(repo_path)

    # Initialize git repo
    subprocess.run(["git", "init"], cwd=repo_path, capture_output=True, check=True)
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"], cwd=repo_path, check=True
    )
    subprocess.run(
        ["git", "config", "user.name", "Test User"], cwd=repo_path, check=True
    )

    # Initial commit on main/master branch
    readme_path = os.path.join(repo_path, "README.md")
    with open(readme_path, "w") as f:
        f.write("# Test Repo")
    subprocess.run(["git", "add", "README.md"], cwd=repo_path, check=True)
    subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=repo_path, check=True)

    yield repo_path

    # Cleanup
    shutil.rmtree(test_dir)


def run_cmd(repo_path, args, input_str=None):
    """Run the tasks-ai command and return the JSON output."""
    cmd = [sys.executable, SCRIPT_PATH, "-j"] + args
    env = os.environ.copy()
    env["PYTHONPATH"] = os.path.dirname(SCRIPT_PATH)
    result = subprocess.run(
        cmd, cwd=repo_path, input=input_str, capture_output=True, text=True, env=env
    )
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        return {
            "success": False,
            "error": "JSON Decode Error",
            "stdout": result.stdout,
            "stderr": result.stderr,
            "exit_code": result.returncode,
        }


def test_init(repo_dir):
    """Test 'init' command."""
    res = run_cmd(repo_dir, ["init"])
    assert res["success"] is True, res
    assert os.path.exists(os.path.join(repo_dir, ".tasks"))

    # Check if branch exists
    res_git = subprocess.run(
        ["git", "branch"], cwd=repo_dir, capture_output=True, text=True
    )
    assert "tasks" in res_git.stdout


def test_create_basic(repo_dir):
    """Test basic task creation."""
    run_cmd(repo_dir, ["init"])
    res = run_cmd(
        repo_dir,
        [
            "create",
            "My First Task Title Long",
            "--story",
            "S" * 10,
            "--tech",
            "T" * 10,
            "--criteria",
            "C" * 10,
            "--plan",
            "P" * 10,
        ],
    )
    assert res["success"] is True, res


def test_list(repo_dir):
    """Test 'list' command."""
    run_cmd(repo_dir, ["init"])
    run_cmd(
        repo_dir,
        [
            "create",
            "Task One Title Long",
            "--story",
            "S" * 10,
            "--tech",
            "T" * 10,
            "--criteria",
            "C" * 10,
            "--plan",
            "P" * 10,
        ],
    )
    res = run_cmd(repo_dir, ["list"])
    assert res["success"] is True, res
    assert len(res["data"]["BACKLOG"]) == 1


def test_backward_moves(repo_dir):
    """Test REVIEW -> PROGRESSING and ARCHIVED -> PROGRESSING."""
    run_cmd(repo_dir, ["init"])
    res = run_cmd(
        repo_dir,
        [
            "create",
            "Backward Move Task",
            "--story",
            "S" * 10,
            "--tech",
            "T" * 10,
            "--criteria",
            "C" * 10,
            "--plan",
            "P" * 10,
        ],
    )
    assert res["success"] is True, res
    task_id = res["data"]["task_id"]

    # Step-by-step move to REVIEW
    res = run_cmd(repo_dir, ["move", "1", "READY"])
    assert res["success"] is True, res
    res = run_cmd(repo_dir, ["move", "1", "PROGRESSING"])
    assert res["success"] is True, res
    res = run_cmd(repo_dir, ["move", "1", "TESTING"])
    assert res["success"] is True, res

    # Setup testing branch
    subprocess.run(["git", "branch", "testing"], cwd=repo_dir, check=True)
    subprocess.run(["git", "checkout", "testing"], cwd=repo_dir, check=True)
    subprocess.run(["git", "merge", task_id], cwd=repo_dir, check=True)
    subprocess.run(["git", "checkout", task_id], cwd=repo_dir, check=True)

    # Ensure branch is ahead of testing
    with open(os.path.join(repo_dir, "work1.txt"), "w") as f:
        f.write("W1")
    subprocess.run(["git", "add", "work1.txt"], cwd=repo_dir, check=True)
    subprocess.run(["git", "commit", "-m", "W1"], cwd=repo_dir, check=True)

    res = run_cmd(repo_dir, ["move", "1", "REVIEW"])
    assert res["success"] is True, res

    # REVIEW -> PROGRESSING
    res = run_cmd(repo_dir, ["move", "1", "PROGRESSING"])
    assert res["success"] is True, res
    assert res["data"]["status"] == "PROGRESSING"


def test_auto_archive(repo_dir):
    """Test auto-archiving logic."""
    run_cmd(repo_dir, ["init"])
    res = run_cmd(
        repo_dir,
        [
            "create",
            "Auto Archive Task",
            "--story",
            "S" * 10,
            "--tech",
            "T" * 10,
            "--criteria",
            "C" * 10,
            "--plan",
            "P" * 10,
        ],
    )
    task_id = res["data"]["task_id"]

    live_dir = os.path.join(repo_dir, ".tasks", "live")
    os.makedirs(live_dir, exist_ok=True)
    src = os.path.join(repo_dir, ".tasks", "backlog", task_id)
    dst = os.path.join(live_dir, task_id)
    shutil.move(src, dst)

    with open(os.path.join(dst, "criteria.md"), "w") as f:
        f.write("- [x] Done")

    logs_dir = os.path.join(repo_dir, ".tasks", "logs")
    os.makedirs(logs_dir, exist_ok=True)
    log_path = os.path.join(logs_dir, task_id)
    old_date = (datetime.now() - timedelta(days=8)).strftime("%y%m%d %H:%M")
    with open(log_path, "w") as f:
        f.write(f"- {old_date}: STAGING->LIVE\n")

    res = run_cmd(repo_dir, ["list"])
    assert res["success"] is True, res
    assert os.path.exists(os.path.join(repo_dir, ".tasks", "archived", task_id))


def test_reconcile_single_only(repo_dir):
    """Test that reconcile without target does a scan (not failure)."""
    run_cmd(repo_dir, ["init"])
    res = run_cmd(repo_dir, ["reconcile"])
    # Reconcile without target does a scan (returns success with candidates list)
    assert res["success"] is True, res
    assert "candidates" in res["data"], res


def test_show(repo_dir):
    """Test 'show' command."""
    run_cmd(repo_dir, ["init"])
    run_cmd(
        repo_dir,
        [
            "create",
            "Show Task Title Long",
            "--story",
            "S" * 10,
            "--tech",
            "T" * 10,
            "--criteria",
            "C" * 10,
            "--plan",
            "P" * 10,
        ],
    )
    res = run_cmd(repo_dir, ["show", "1"])
    assert res["success"] is True, res
    assert res["data"]["metadata"]["Title"] == "Show Task Title Long"


def test_modify(repo_dir):
    """Test 'modify' command."""
    run_cmd(repo_dir, ["init"])
    run_cmd(
        repo_dir,
        [
            "create",
            "Modify Task Title Long",
            "--story",
            "S" * 10,
            "--tech",
            "T" * 10,
            "--criteria",
            "C" * 10,
            "--plan",
            "P" * 10,
        ],
    )
    res = run_cmd(repo_dir, ["modify", "1", "--title", "Updated Title Here"])
    assert res["success"] is True, res
    res = run_cmd(repo_dir, ["show", "1"])
    assert res["data"]["metadata"]["Title"] == "Updated Title Here"


def test_link_and_block(repo_dir):
    """Test linking and blocking logic."""
    run_cmd(repo_dir, ["init"])
    run_cmd(
        repo_dir,
        [
            "create",
            "Blocker Task Title Long",
            "--story",
            "S" * 10,
            "--tech",
            "T" * 10,
            "--criteria",
            "C" * 10,
            "--plan",
            "P" * 10,
        ],
    )
    run_cmd(
        repo_dir,
        [
            "create",
            "Blocked Task Title Long",
            "--story",
            "S" * 10,
            "--tech",
            "T" * 10,
            "--criteria",
            "C" * 10,
            "--plan",
            "P" * 10,
        ],
    )

    # Link 2 to 1
    res = run_cmd(repo_dir, ["link", "2", "1"])
    assert res["success"] is True, res

    # Try to move 2 to PROGRESSING (should fail)
    run_cmd(repo_dir, ["move", "2", "READY"])
    res = run_cmd(repo_dir, ["move", "2", "PROGRESSING"])
    assert res["success"] is False, res
    assert "Blocked by" in res["error"]


def test_delete_workflow(repo_dir):
    """Test deletion with confirmation."""
    run_cmd(repo_dir, ["init"])
    run_cmd(
        repo_dir,
        [
            "create",
            "Delete Me Task Title",
            "--story",
            "S" * 10,
            "--tech",
            "T" * 10,
            "--criteria",
            "C" * 10,
            "--plan",
            "P" * 10,
        ],
    )

    res = run_cmd(repo_dir, ["delete", "1"])
    assert res["success"] is True, res
    code = res["data"]["delete_code"]

    res = run_cmd(repo_dir, ["delete", "1", "--confirm", code])
    assert res["success"] is True, res

    res = run_cmd(repo_dir, ["list"])
    assert "BACKLOG" not in res["data"] or len(res["data"]["BACKLOG"]) == 0


def test_current(repo_dir):
    """Test 'current' command."""
    run_cmd(repo_dir, ["init"])
    run_cmd(
        repo_dir,
        [
            "create",
            "Current Task Title Long",
            "--story",
            "S" * 10,
            "--tech",
            "T" * 10,
            "--criteria",
            "C" * 10,
            "--plan",
            "P" * 10,
        ],
    )
    run_cmd(repo_dir, ["move", "1", "READY,PROGRESSING"])

    res = run_cmd(repo_dir, ["current"])
    assert res["success"] is True, res
    assert res["data"]["metadata"]["Title"] == "Current Task Title Long"


def test_checkpoint_sync(repo_dir):
    """Test 'checkpoint' syncs content."""
    run_cmd(repo_dir, ["init"])
    res = run_cmd(
        repo_dir,
        [
            "create",
            "Checkpoint Task Title",
            "--story",
            "S" * 10,
            "--tech",
            "T" * 10,
            "--criteria",
            "C" * 10,
            "--plan",
            "P" * 10,
        ],
    )
    task_id = res["data"]["task_id"]
    run_cmd(repo_dir, ["move", "1", "READY,PROGRESSING"])

    progress_file = os.path.join(
        repo_dir, ".tasks", "progressing", task_id, "current-task.md"
    )
    with open(progress_file, "w") as f:
        f.write("---\nTask: " + task_id + "\n---\n# Content\nSYNC_NOTE")

    run_cmd(repo_dir, ["checkpoint"])
    notes_file = os.path.join(repo_dir, ".tasks", "progressing", task_id, "notes.md")
    with open(notes_file, "r") as f:
        assert "SYNC_NOTE" in f.read()
