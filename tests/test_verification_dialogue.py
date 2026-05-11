import os
import subprocess
import pytest
import shutil
import glob

def run_hammer(args):
    return subprocess.run(["python3", "tasks.py", "--dev"] + args, capture_output=True, text=True)

@pytest.fixture
def setup_env():
    if os.path.exists("/tmp/.tasks"):
        shutil.rmtree("/tmp/.tasks")
    subprocess.run(["python3", "tasks.py", "--dev", "init"], check=True)
    yield

def test_tamper_resistance(setup_env):
    run_hammer(["create", "Tamper Task", "--type", "task", 
                "--story", "Testing tamper resistance.", 
                "--tech", "Testing tamper resistance.", 
                "--criteria", "- [ ] Item 1", 
                "--plan", "Testing tamper resistance."])
    
    task_id = "1-task-tamper-task"
    
    run_hammer(["verify", task_id, "--proof", "Verified proof."])
    
    # Find the criteria file dynamically
    criteria_path = glob.glob(f"/tmp/.tasks/*/*{task_id}*/criteria.md")[0]
    with open(criteria_path, "a") as f:
        f.write("\n- [ ] Tampered item")
        
    run_hammer(["move", task_id, "TESTING"])
    run_hammer(["move", task_id, "REVIEW"])
    move_res = run_hammer(["move", task_id, "STAGING"])
    
    assert "TAMPER ALERT" in move_res.stderr or "tamper" in move_res.stderr.lower()
