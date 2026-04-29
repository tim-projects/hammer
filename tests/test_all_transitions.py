import unittest
import json
from hammer_test_base import HammerTestBase
from tasks_ai.constants import ALLOWED_TRANSITIONS, STATE_FOLDERS

class TestAllTransitions(HammerTestBase):
    def test_transitions(self):
        # Create a task
        res = self.run_tasks(["create", "Comprehensive Test Task", 
             "--story", "Sufficiently long story content here...", 
             "--tech", "Sufficiently long technical description here...", 
             "--criteria", "Sufficiently long acceptance criteria here...", 
             "--plan", "Sufficiently long planning details here..."])
        task_id = json.loads(res.stdout)["data"]["id"]
        
        # Test all transitions
        # We start at READY (after init + move to READY)
        self.run_tasks(["move", str(task_id), "READY"])
        current = "READY"
        
        # Define the set of states to test
        states_to_test = [s for s in STATE_FOLDERS.keys() if s not in ["BACKLOG"]]
        
        # Exhaustive loop
        for target in states_to_test:
            if target == current: continue
            
            # Execute transition
            res = self.run_tasks(["move", str(task_id), target])
            
            # Ensure JSON is valid
            try:
                output = json.loads(res.stdout)
            except json.JSONDecodeError:
                self.fail(f"Invalid JSON from transition {current}->{target}. Stderr: {res.stderr}")
            
            # Validate transition logic
            allowed = ALLOWED_TRANSITIONS.get(current, [])
            if target in allowed:
                self.assertTrue(output.get("success"), f"Valid transition {current}->{target} failed: {output.get('error')}")
                current = target
            else:
                self.assertFalse(output.get("success", True), f"Invalid transition {current}->{target} should have failed")

if __name__ == "__main__":
    unittest.main()
