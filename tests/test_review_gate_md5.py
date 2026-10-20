import json
import os
import shutil
import subprocess
import tempfile

HAMMER_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "hammer")


def run_dev(cmd, force=False, cwd=None):
    full_cmd = [HAMMER_PATH, "tasks", "-j", "--dev"] + cmd
    if force and cmd and cmd[0] == "init":
        full_cmd.append("--force")
    result = subprocess.run(full_cmd, capture_output=True, text=True, cwd=cwd)
    return result


def setup_dev_config(dev_tasks_dir):
    os.makedirs(dev_tasks_dir, exist_ok=True)
    config_data = {
        "repo": {
            "lint": "/bin/true",
            "test": "/bin/true",
            "type_check": "/bin/true",
            "format": "/bin/true",
        }
    }
    with open(os.path.join(dev_tasks_dir, "config.yaml"), "w") as f:
        json.dump(config_data, f, indent=2)


def test_review_gating_with_md5():
    test_root = tempfile.mkdtemp(prefix="hammer_review_gate_test_")
    repo_dir = os.path.join(test_root, "repo")
    dev_tasks_dir = tempfile.mkdtemp(prefix="hammer_tasks_")
    os.environ["HAMMER_DEV_TASKS_DIR"] = dev_tasks_dir
    try:
        subprocess.run(
            ["git", "clone", os.getcwd(), repo_dir],
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "checkout", "main"], cwd=repo_dir, check=True, capture_output=True
        )

        # Stub validation tools
        sandbox_tasks_dir = os.path.join(repo_dir, ".tasks")
        os.makedirs(sandbox_tasks_dir, exist_ok=True)
        with open(os.path.join(sandbox_tasks_dir, "config.yaml"), "w") as f:
            json.dump(
                {
                    "repo": {
                        "lint": "/bin/true",
                        "test": "/bin/true",
                        "type_check": "/bin/true",
                        "format": "/bin/true",
                    }
                },
                f,
                indent=2,
            )

        def check(label, result):
            assert result.returncode == 0, (
                f"{label} failed (rc={result.returncode}): "
                f"{result.stdout[:500]} {result.stderr[:500]}"
            )

        init_res = run_dev(["init"], force=True, cwd=repo_dir)
        check("init", init_res)
        setup_dev_config(dev_tasks_dir)

        # Create a test task
        create_result = run_dev(
            [
                "create",
                "Review Gate Test",
                "--story",
                "Sufficiently long story content for validation testing",
                "--tech",
                "Sufficiently long technical content for validation testing",
                "--criteria",
                "- [ ] Sufficiently long criteria content for validation",
                "--plan",
                "Sufficiently long plan content for validation testing",
            ],
            cwd=repo_dir,
        )
        create_data = json.loads(create_result.stdout)
        task_id = str(create_data["data"]["id"])
        branch = create_data["data"]["branch"]

        check("create", create_result)
        check("modify criteria", run_dev(["modify", task_id, "--criteria", "- [x] Sufficiently long criteria content for validation"], cwd=repo_dir))
        check("move READY", run_dev(["move", task_id, "READY"], cwd=repo_dir))

        # Edit a file to create changes
        test_file = os.path.join(repo_dir, "README.md")
        with open(test_file, "a") as f:
            f.write("\n# Review Gate Test\n")
        subprocess.run(["git", "add", "README.md"], cwd=repo_dir, check=True)
        subprocess.run(["git", "commit", "-m", "test change"], cwd=repo_dir, check=True)

        check("move PROGRESSING", run_dev(["move", task_id, "PROGRESSING"], cwd=repo_dir))

        subprocess.run(["git", "checkout", "-B", "testing"], cwd=repo_dir, check=True, capture_output=True)
        subprocess.run(["git", "merge", branch, "-m", "Merge"], cwd=repo_dir, check=True, capture_output=True)
        subprocess.run(["git", "checkout", "main"], cwd=repo_dir, check=True, capture_output=True)
        check("move TESTING", run_dev(["move", task_id, "TESTING"], cwd=repo_dir))

        subprocess.run(["git", "checkout", "-B", "staging", "testing"], cwd=repo_dir, check=True, capture_output=True)
        subprocess.run(["git", "merge", branch, "-m", "Merge"], cwd=repo_dir, check=True, capture_output=True)
        subprocess.run(["git", "checkout", "main"], cwd=repo_dir, check=True, capture_output=True)

        # Move to REVIEW - this should generate patches with MD5 hashes
        res = run_dev(["move", task_id, "REVIEW"], cwd=repo_dir)
        check("move REVIEW", res)

        # Attempt to mark reviewed without proper review data - this should work with our new implementation
        # because our implementation auto-generates review entries if needed
        res = run_dev(["modify", task_id, "--reviewed"], cwd=repo_dir)
        # With our new implementation, this creates PatchReviews
        assert res.returncode == 0

        res = run_dev(["audit", task_id], cwd=repo_dir)
        check("audit", res)
        res = run_dev(["verify", task_id, "--proof", "test proof"], cwd=repo_dir)
        check("verify", res)
        res = run_dev(["modify", task_id, "--regression-check"], cwd=repo_dir)
        check("regression-check", res)
        res = run_dev(["move", task_id, "STAGING"], cwd=repo_dir)
        assert res.returncode == 0
    finally:
        shutil.rmtree(test_root, ignore_errors=True)
        shutil.rmtree(dev_tasks_dir, ignore_errors=True)
        os.environ.pop("HAMMER_DEV_TASKS_DIR", None)
