import json
import os
import subprocess


# Helper to run hammer commands
def run_dev(cmd, force=False):
    full_cmd = ["./hammer", "tasks", "-j", "--dev"] + cmd
    if force and cmd and cmd[0] == "init":
        full_cmd.append("--force")
    result = subprocess.run(full_cmd, capture_output=True, text=True)  # noqa: PLW1510
    return result


def setup_dev_config():
    dev_tasks_dir = os.environ.get("HAMMER_DEV_TASKS_DIR", "/tmp/.tasks")
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
    # 1. Init dev env with force to clean up
    run_dev(["init"], force=True)
    setup_dev_config()

    # 2. Create task
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
        ]
    )
    create_data = json.loads(create_result.stdout)
    task_id = str(create_data["data"]["id"])
    branch = create_data["data"]["branch"]

    # 3. Mark criteria as done
    run_dev(
        [
            "modify",
            task_id,
            "--criteria",
            "- [x] Sufficiently long acceptance criteria here to pass validation",
        ]
    )

    # 4. Move through READY -> PROGRESSING
    run_dev(["move", task_id, "READY"])
    run_dev(["move", task_id, "PROGRESSING"])

    # 5. Set up testing branch and move to TESTING
    subprocess.run(
        ["git", "checkout", "-b", "testing"],
        cwd=os.getcwd(),
        capture_output=True,
    )
    subprocess.run(
        ["git", "merge", branch, "-m", f"Merge {branch} into testing"],
        cwd=os.getcwd(),
        capture_output=True,
    )
    subprocess.run(["git", "checkout", "main"], cwd=os.getcwd(), capture_output=True)
    testing_res = run_dev(["move", task_id, "TESTING"])
    print("TESTING rc:", testing_res.returncode)
    print("TESTING stdout:", testing_res.stdout[:300])

    # 6. Set up staging branch and move to REVIEW
    subprocess.run(
        ["git", "checkout", "-b", "staging"],
        cwd=os.getcwd(),
        capture_output=True,
    )
    subprocess.run(
        ["git", "merge", branch, "-m", f"Merge {branch} into staging"],
        cwd=os.getcwd(),
        capture_output=True,
    )
    subprocess.run(["git", "checkout", "main"], cwd=os.getcwd(), capture_output=True)
    review_res = run_dev(["move", task_id, "REVIEW"])
    print("REVIEW rc:", review_res.returncode)
    print("REVIEW stdout:", review_res.stdout[:300])

    # 7. Audit
    run_dev(["audit", task_id])

    # 8. Verify
    run_dev(["verify", task_id, "--proof", "Integration proof"])

    # 9. Regression Check
    regression_res = run_dev(["modify", task_id, "--regression-check"])
    print("REGRESSION rc:", regression_res.returncode)
    print("REGRESSION stdout:", regression_res.stdout[:300])

    # 10. Move to STAGING
    move_res = run_dev(["move", task_id, "STAGING"])

    # 11. Verify result
    assert move_res.returncode == 0, (
        f"Failed to move to STAGING: {move_res.stderr} {move_res.stdout}"
    )
