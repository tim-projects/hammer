#!/usr/bin/env python3
"""
Test suite for repo tool
"""

import os
import subprocess
import tempfile
import shutil
import json
import sys
import pytest

REPO_SCRIPT = os.path.abspath("repo")


@pytest.fixture
def repo_dir():
    """Create a temporary git repository for testing."""
    test_dir = tempfile.mkdtemp()
    repo_path = os.path.join(test_dir, "repo")
    os.makedirs(repo_path)

    subprocess.run(["git", "init"], cwd=repo_path, capture_output=True, check=True)
    subprocess.run(
        ["git", "config", "user.email", "test@test.com"], cwd=repo_path, check=True
    )
    subprocess.run(["git", "config", "user.name", "Test"], cwd=repo_path, check=True)

    readme = os.path.join(repo_path, "README.md")
    with open(readme, "w") as f:
        f.write("# Test Repo\n")
    subprocess.run(["git", "add", "README.md"], cwd=repo_path, check=True)
    subprocess.run(["git", "commit", "-m", "Initial"], cwd=repo_path, check=True)

    yield repo_path
    shutil.rmtree(test_dir)


def run_repo(repo_path, args):
    """Run repo command and return output."""
    cmd = [REPO_SCRIPT] + args
    result = subprocess.run(cmd, cwd=repo_path, capture_output=True, text=True)
    return result


def test_repo_git_status(repo_dir):
    """Test 'repo git status' command."""
    res = run_repo(repo_dir, ["git", "status"])
    assert res.returncode == 0
    assert (
        "nothing to commit" in res.stdout.lower()
        or "working tree clean" in res.stdout.lower()
    )


def test_repo_git_branch(repo_dir):
    """Test 'repo git branch' command."""
    res = run_repo(repo_dir, ["git", "branch"])
    assert res.returncode == 0
    assert "main" in res.stdout or "master" in res.stdout


def test_repo_branch_list(repo_dir):
    """Test 'repo branch list' command."""
    res = run_repo(repo_dir, ["branch", "list"])
    assert res.returncode == 0
    assert "main" in res.stdout or "master" in res.stdout


def test_repo_branch_exists(repo_dir):
    """Test 'repo branch exists master' command - checks local only."""
    res = run_repo(repo_dir, ["branch", "exists", "master"])
    assert (
        res.returncode == 0
        or "true" in res.stdout.lower()
        or "false" in res.stdout.lower()
    )


def test_repo_branch_create(repo_dir):
    """Test 'repo branch create feature-test' command."""
    res = run_repo(repo_dir, ["branch", "create", "feature-test"])
    assert res.returncode == 0

    res = run_repo(repo_dir, ["git", "branch"])
    assert "feature-test" in res.stdout


def test_repo_branch_delete(repo_dir):
    """Test 'repo branch delete' command."""
    run_repo(repo_dir, ["branch", "create", "to-delete"])
    run_repo(repo_dir, ["git", "checkout", "master"])
    res = run_repo(repo_dir, ["branch", "delete", "to-delete"])
    assert res.returncode == 0


def test_repo_merged(repo_dir):
    """Test 'repo merged master master' command."""
    res = run_repo(repo_dir, ["merged", "master", "master"])
    assert res.returncode == 0
    assert "true" in res.stdout.lower() or "false" in res.stdout.lower()


def test_repo_merge_base(repo_dir):
    """Test 'repo merge-base master master' command."""
    res = run_repo(repo_dir, ["merge-base", "master", "master"])
    assert res.returncode == 0


def test_repo_worktree_list(repo_dir):
    """Test 'repo worktree' command (no args defaults to list)."""
    res = run_repo(repo_dir, ["worktree"])
    assert res.returncode == 0


def test_repo_json_output(repo_dir):
    """Test 'repo -j status' command."""
    res = run_repo(repo_dir, ["-j", "status"])
    assert res.returncode == 0


def test_repo_quiet_mode(repo_dir):
    """Test 'repo -q status' command."""
    res = run_repo(repo_dir, ["-q", "status"])
    assert res.returncode == 0
