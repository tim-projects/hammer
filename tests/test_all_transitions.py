import unittest
import json
import os
from hammer_test_base import HammerTestBase
from tasks_ai.constants import ALLOWED_TRANSITIONS, STATE_FOLDERS


class TestAllTransitions(HammerTestBase):
    def complete_criteria(self, task_file):
        for dirpath, _, filenames in os.walk(self.dev_tasks_dir):
            if "criteria.md" not in filenames:
                continue
            criteria_path = os.path.join(dirpath, "criteria.md")
            with open(criteria_path, "r") as f:
                content = f.read()
            with open(criteria_path, "w") as f:
                f.write(content.replace("- [ ]", "- [x]"))
            return

    def test_transitions(self):
        res = self.run_tasks(
            [
                "create",
                "Comprehensive Test Task",
                "--story",
                "Sufficiently long story content here to pass validation",
                "--tech",
                "Sufficiently long technical description here to pass validation",
                "--criteria",
                "Sufficiently long acceptance criteria here to pass validation",
                "--plan",
                "Sufficiently long planning details here to pass validation",
            ]
        )
        print("DEBUG: CREATE RES:", res.stdout)
        create_data = json.loads(res.stdout).get("data", {})
        task_id = create_data.get("id")
        task_file = create_data.get("file")
        print(f"DEBUG: Task ID is {task_id}")

        self.run_tasks(["move", str(task_id), "READY"])
        current = "READY"

        states_to_test = [s for s in STATE_FOLDERS.keys() if s not in ["BACKLOG"]]

        for target in states_to_test:
            if target == current:
                continue

            if target == "TESTING":
                self.complete_criteria(task_file)

            res = self.run_tasks(["move", str(task_id), target])
            output = json.loads(res.stdout)

            success = output.get("success", False)
            error = output.get("error", "")

            is_allowed = target in ALLOWED_TRANSITIONS.get(current, [])
            is_validation_error = any(
                msg.lower() in error.lower()
                for msg in ["Validation failed", "regression check", "lint"]
            )
            is_gate_error = any(
                msg.lower() in error.lower()
                for msg in ["Forbidden transition", "Auto-promotion failed", "Regression check not passed"]
            )

            if is_allowed:
                is_pass = success or is_validation_error
                status = "ACCEPTED" if success else "REJECTED"
                reason = "Valid move successful" if success else error
            else:
                is_pass = not success and is_gate_error
                status = "REJECTED"
                reason = error if not success else "Unexpectedly allowed"

            print(
                f"DEBUG: Testing {current}->{target} ... <{status}> {'PASS' if is_pass else 'FAIL'} (Reason: {reason})"
            )
            self.assertTrue(
                is_pass,
                f"Transition {current}->{target} resulted in unexpected state: {output}",
            )
            if is_allowed and success:
                current = target


if __name__ == "__main__":
    unittest.main()
