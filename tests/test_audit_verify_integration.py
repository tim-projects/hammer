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


def test_pipeline_audit_verify_gates():
    test_root = tempfile.mkdtemp(prefix="hammer_pipeline_test_")
    repo_dir = os.path.join(test_root, "repo")
    dev_tasks_dir = tempfile.mkdtemp(prefix="hammer_tasks_")
    os.environ["HAMMER_DEV_TASKS_DIR"] = dev_tasks_dir
    try:
        subprocess.run(
            ["git", "clone", os.getcwd(), repo_dir],
            ["git", "clone", os.getcwd(), repo_dir],
            ["git", "clone", "--single-branch", "--branch", "main", os.getcwd(), repo_dir],
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "checkout", "main"], cwd=repo_dir, check=True, capture_output=True
        )
        subprocess.run(
            ["git", "fetch", "origin", "tasks"], cwd=repo_dir, check=True, capture_output=True
        )
        subprocess.run(
            ["git", "branch", "tasks", "origin/tasks"], cwd=repo_dir, check=True, capture_output=True
        )
        for branch in ["testing", "staging"]:
            subprocess.run(
                ["git", "branch", "-D", branch], cwd=repo_dir, check=False, capture_output=True
            )

        # Stub validation tools in the sandbox repo's .tasks so check.py uses /bin/true
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
            if result.returncode != 0:
                print(f"FULL OUTPUT for {label}:")
                print(result.stdout)
                print(result.stderr)
            assert result.returncode == 0, (
                f"{label} failed (rc={result.returncode}): "
                f"{result.stdout[:500]} {result.stderr[:500]}"
            )

        init_res = run_dev(["init"], force=True, cwd=repo_dir)
        check("init", init_res)
        setup_dev_config(dev_tasks_dir)

        # 5. Set up testing branch and move to TESTING
        subprocess.run(
            ["git", "checkout", "testing"],
                cwd=os.getcwd(),
            capture_output=True,
        )
        subprocess.run(
            ["git", "merge", branch, "-m", f"Merge {branch} into testing"],
            cwd=os.getcwd(),
            capture_output=True,
        )
        subprocess.run(["git", "checkout", "main"], cwd=os.getcwd(), capture_output=True)
        run_dev(["move", task_id, "TESTING"])

        # 6. Set up staging branch and move to REVIEW
        subprocess.run(
            ["git", "checkout", "testing"],
                cwd=os.getcwd(),
            capture_output=True,
        )
        subprocess.run(
            ["git", "branch", "-f", "staging", "testing"],
            cwd=os.getcwd(),
            capture_output=True,
        )
        subprocess.run(
            ["git", "checkout", "staging"],
            cwd=os.getcwd(),
            capture_output=True,
        )
        subprocess.run(
            ["git", "merge", branch, "-m", f"Merge {branch} into staging"],
            cwd=os.getcwd(),
            capture_output=True,
        )
        subprocess.run(["git", "checkout", "main"], cwd=os.getcwd(), capture_output=True)
        run_dev(["move", task_id, "REVIEW"])
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

        check("create", create_result)
        check("modify criteria", run_dev(["modify", task_id, "--criteria", "- [x] Sufficiently long acceptance criteria here to pass validation"], cwd=repo_dir))
        check("move READY", run_dev(["move", task_id, "READY"], cwd=repo_dir))
        check("move PROGRESSING", run_dev(["move", task_id, "PROGRESSING"], cwd=repo_dir))

        subprocess.run(["git", "checkout", "-b", "testing"], cwd=repo_dir, check=True, capture_output=True)
        subprocess.run(["git", "merge", branch, "-m", f"Merge {branch} into testing"], cwd=repo_dir, check=True, capture_output=True)
        subprocess.run(["git", "checkout", "main"], cwd=repo_dir, check=True, capture_output=True)
        check("move TESTING", run_dev(["move", task_id, "TESTING"], cwd=repo_dir))

        subprocess.run(["git", "checkout", "testing"], cwd=repo_dir, check=True, capture_output=True)
        subprocess.run(["git", "checkout", "-b", "staging"], cwd=repo_dir, check=True, capture_output=True)
        subprocess.run(["git", "merge", branch, "-m", f"Merge {branch} into staging"], cwd=repo_dir, check=True, capture_output=True)
        subprocess.run(["git", "checkout", "main"], cwd=repo_dir, check=True, capture_output=True)
        check("move REVIEW", run_dev(["move", task_id, "REVIEW"], cwd=repo_dir))

        check("audit", run_dev(["audit", task_id], cwd=repo_dir))
        check("verify", run_dev(["verify", task_id, "--proof", "Integration proof"], cwd=repo_dir))
        check("regression-check", run_dev(["modify", task_id, "--regression-check"], cwd=repo_dir))

        check("move STAGING", run_dev(["move", task_id, "STAGING"], cwd=repo_dir))
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
