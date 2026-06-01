import subprocess
import time


def run_dev(cmd):
    full_cmd = ["./hammer", "tasks", "--dev"] + cmd
    result = subprocess.run(full_cmd, capture_output=True, text=True)
    return result


subprocess.run(["./hammer", "tasks", "--dev", "init", "--force"], capture_output=True)
run_dev(
    [
        "create",
        "Integration Test Task",
        "--story",
        "Sufficiently long story content here to pass validation",
        "--tech",
        "Sufficiently long technical description here to pass validation",
        "--criteria",
        "- [ ] Task",
        "--plan",
        "Sufficiently long planning details here",
    ]
)
time.sleep(1)
print(run_dev(["list"]).stdout)
