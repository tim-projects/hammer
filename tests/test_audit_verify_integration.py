import subprocess

# Helper to run hammer commands
def run_dev(cmd, force=False):
    full_cmd = ["./hammer", "tasks", "--dev"]
    if force:
        full_cmd += ["--force"]
    full_cmd += cmd
    result = subprocess.run(full_cmd, capture_output=True, text=True)
    return result

def test_pipeline_audit_verify_gates():
    # 1. Init dev env with force to clean up
    run_dev(["init"], force=True)
    
    # 2. Create task
    run_dev(["create", "Integration Test Task", "--story", "Sufficiently long story content here to pass validation", "--tech", "Sufficiently long technical description here to pass validation", "--criteria", "- [ ] Task", "--plan", "Sufficiently long planning details here to pass validation"])
    task_id = "1"
    
    # 3. Mark criteria as done
    run_dev(["modify", task_id, "--criteria", "- [x] Task"])
    
    # 4. Multi-step move
    run_dev(["move", task_id, "READY,PROGRESSING,TESTING,REVIEW"])
    
    # 5. Audit
    run_dev(["audit", task_id])
    
    # 6. Verify
    run_dev(["verify", task_id, "--proof", "Integration proof"])
    
    # 7. Regression Check
    run_dev(["modify", task_id, "--regression-check"])
    
    # 8. Move to STAGING
    move_res = run_dev(["move", task_id, "STAGING"])
    
    # 9. Verify result
    assert move_res.returncode == 0, f"Failed to move to STAGING: {move_res.stderr} {move_res.stdout}"

