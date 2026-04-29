import unittest
import json
from hammer_test_base import HammerTestBase
from tasks_ai.constants import ALLOWED_TRANSITIONS, STATE_FOLDERS

class TestAllTransitions(HammerTestBase):
    def test_transitions(self):
        res = self.run_tasks(["create", "Comprehensive Test Task", 
             "--story", "Sufficiently long story content here...", 
             "--tech", "Sufficiently long technical description here...", 
             "--criteria", "Sufficiently long acceptance criteria here...", 
             "--plan", "Sufficiently long planning details here..."])
        task_id = json.loads(res.stdout)["data"]["id"]
        
        self.run_tasks(["move", str(task_id), "READY"])
        current = "READY"
        
        states_to_test = [s for s in STATE_FOLDERS.keys() if s not in ["BACKLOG"]]
        
        for target in states_to_test:
            if target == current: continue
            
            res = self.run_tasks(["move", str(task_id), target])
            output = json.loads(res.stdout)
            
            success = output.get("success", False)
            error = output.get("error", "")
            
            is_allowed = target in ALLOWED_TRANSITIONS.get(current, [])
            is_validation_error = any(msg in error for msg in ["Validation failed", "regression check", "lint"])
            is_gate_error = any(msg in error for msg in ["Forbidden transition", "Auto-promotion failed"])
            
            if is_allowed:
                is_pass = success or is_validation_error
                status = "ACCEPTED" if success else "REJECTED"
                reason = "Valid move successful" if success else error
            else:
                is_pass = not success and is_gate_error
                status = "REJECTED"
                reason = error if not success else "Unexpectedly allowed"
            
            print(f"DEBUG: Testing {current}->{target} ... <{status}> {'PASS' if is_pass else 'FAIL'} (Reason: {reason})")
            self.assertTrue(is_pass, f"Transition {current}->{target} resulted in unexpected state: {output}")
            if is_allowed and success:
                current = target

if __name__ == "__main__":
    unittest.main()
