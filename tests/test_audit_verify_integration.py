import json
import os
import shutil
import subprocess
import tempfile


def run_dev(cmd, force=False, cwd=None):
    full_cmd = ["./hammer", "tasks", "-j", "--dev"] + cmd
    if force and cmd and cmd[0] == "init":
        full_cmd.append("--force")
    result = subprocess.run(full_cmd, capture_output=True, text=True, cwd=cwd)  # noqa: PLW1510
    return result


def setup_dev_config(dev_tasks_dir):
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


def test_pipeline_audit_verify_gates():
    test_root = tempfile.mkdtemp(prefix="hammer_pipeline_test_")
    repo_dir = os.path.join(test_root, "repo")
    dev_tasks_dir = tempfile.mkdtemp(prefix="hammer_tasks_")
    os.environ["HAMMER_DEV_TASKS_DIR"] = dev_tasks_dir
    try:
        subprocess.run(
            ["git", "clone", "--single-branch", "--branch", "main", os.getcwd(), repo_dir],
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "checkout", "main"], cwd=repo_dir, check=True, capture_output=True
        )
        for branch in ["testing", "staging"]:
            subprocess.run(
                ["git", "branch", "-D", branch], cwd=repo_dir, check=False, capture_output=True
            )

        setup_dev_config(dev_tasks_dir)
        run_dev(["init"], force=True, cwd=repo_dir)

        create_result = run_dev(
            [
                "create",
                "Integration Test Task",
                "--story",
                "Sufficiently long story content here to pass validation",
                "--tech",
                "Sufficiently long technical description here to pass validation",
                "--criteria",
                "- [ ] Sufficiently long acceptance criteria here to pass validation",
                "--plan",
                "Sufficiently long planning details here to pass validation",
            ],
            cwd=repo_dir,
        )
        create_data = json.loads(create_result.stdout)
        task_id = str(create_data["data"]["id"])
        branch = create_data["data"]["branch"]

        # Debug: check dev_tasks_dir contents
        for root, dirs, files in os.walk(dev_tasks_dir):
            level = root.replace(dev_tasks_dir, '').count(os.sep)
            indent = ' ' * 2 * level
            print(f'{indent}{os.path.basename(root)}/')
            for f in files:
                print(f'{indent}  {f}')
            for d in dirs:
                if d != '.git':
                    print(f'{indent}  {d}/')

        run_dev(["modify", task_id, "--criteria", "- [x] Sufficiently long acceptance criteria here to pass validation"], cwd=repo_dir)
        run_dev(["move", task_id, "READY"], cwd=repo_dir)
        run_dev(["move", task_id, "PROGRESSING"], cwd=repo_dir)

        subprocess.run(["git", "checkout", "-b", "testing"], cwd=repo_dir, check=True, capture_output=True)
        subprocess.run(["git", "merge", branch, "-m", f"Merge {branch} into testing"], cwd=repo_dir, check=True, capture_output=True)
        subprocess.run(["git", "checkout", "main"], cwd=repo_dir, check=True, capture_output=True)
        run_dev(["move", task_id, "TESTING"], cwd=repo_dir)

        subprocess.run(["git", "checkout", "testing"], cwd=repo_dir, check=True, capture_output=True)
        subprocess.run(["git", "checkout", "-b", "staging"], cwd=repo_dir, check=True, capture_output=True)
        subprocess.run(["git", "merge", branch, "-m", f"Merge {branch} into staging"], cwd=repo_dir, check=True, capture_output=True)
        subprocess.run(["git", "checkout", "main"], cwd=repo_dir, check=True, capture_output=True)
        run_dev(["move", task_id, "REVIEW"], cwd=repo_dir)

        run_dev(["audit", task_id], cwd=repo_dir)
        run_dev(["verify", task_id, "--proof", "Integration proof"], cwd=repo_dir)
        run_dev(["modify", task_id, "--regression-check"], cwd=repo_dir)

        list_res = run_dev(["list"], cwd=repo_dir)
        print("LIST rc:", list_res.returncode)
        print("LIST stdout:", list_res.stdout[:500])

        move_res = run_dev(["move", task_id, "STAGING"], cwd=repo_dir)
        assert move_res.returncode == 0, (
            f"Failed to move to STAGING: {move_res.stderr} {move_res.stdout}"
        )
    finally:
        shutil.rmtree(test_root, ignore_errors=True)
        shutil.rmtree(dev_tasks_dir, ignore_errors=True)
        os.environ.pop("HAMMER_DEV_TASKS_DIR", None)
