import json
import subprocess
import unittest
from unittest.mock import patch

from tasks_ai.messages import MessageRegistry
from tasks_ai.validation import Validation
from tasks_ai.validator import Validator, format_check_results


class FakeCLI:
    as_json = True
    dev = False

    def __init__(self, root):
        self.context = type(
            "Context",
            (),
            {"repo_root": root, "main_repo_root": root},
        )()
        self.errors = []

    def error(self, code, **kwargs):
        self.errors.append((code, kwargs))
        raise RuntimeError(code)


class TestValidationBlockers(unittest.TestCase):
    def run_validation(self, payload, returncode=1):
        cli = FakeCLI("/tmp/repo")
        result = subprocess.CompletedProcess(
            args=["check.py", "all", "--json"],
            returncode=returncode,
            stdout=json.dumps(payload) + "\n",
            stderr="",
        )
        with (
            patch("tasks_ai.validation.subprocess.run", return_value=result),
            self.assertRaises(RuntimeError),
        ):
            Validation(cli).run_tool("all")
        return cli.errors[0]

    def test_failed_lint_output_is_preserved_as_the_blocker(self):
        code, details = self.run_validation(
            {
                "success": False,
                "tool": "lint",
                "stdout": json.dumps(
                    [
                        {
                            "code": "F401",
                            "filename": "tasks_ai/example.py",
                            "location": {"row": 1, "column": 8},
                            "message": "`os` imported but unused",
                            "severity": "error",
                        }
                    ]
                ),
                "stderr": "",
                "exit_code": 1,
            }
        )

        self.assertEqual(code, "PIPELINE_VALIDATION_FAILED")
        self.assertEqual(details["tool"], "lint")
        self.assertIn("BLOCKER F401", details["msg"])
        self.assertIn("Found 1 lint blocker", details["msg"])
        self.assertNotIn('"severity": "error"', details["msg"])

    def test_failed_tool_without_output_keeps_tool_and_exit_code(self):
        code, details = self.run_validation(
            {
                "success": False,
                "tool": "typecheck",
                "stdout": "",
                "stderr": "",
                "exit_code": 2,
            }
        )

        self.assertEqual(code, "PIPELINE_VALIDATION_FAILED")
        self.assertTrue(details["msg"].startswith("BLOCKER typecheck:"))
        self.assertIn("2", details["msg"])
        self.assertNotIn("Tool execution failed", details["msg"])

    def test_check_results_render_each_failure_as_a_readable_blocker(self):
        output = format_check_results(
            [
                {
                    "success": False,
                    "status": "blocker",
                    "tool": "test",
                    "stdout": "1 failed, 99 passed",
                    "stderr": "test details",
                    "exit_code": 1,
                }
            ]
        )

        self.assertIn("CHECK test: BLOCKER", output)
        self.assertIn("exit_code: 1", output)
        self.assertIn("1 failed, 99 passed", output)
        self.assertIn("test details", output)
        self.assertNotIn("Results: [", output)

    def test_validator_marks_every_failed_check_as_a_blocker(self):
        validator = Validator.__new__(Validator)
        validator.project_root = "/tmp/repo"
        validator.dev = False
        validator.config = {"repo": {"lint": "ruff"}}
        result = subprocess.CompletedProcess(
            args=["ruff"],
            returncode=1,
            stdout="[]",
            stderr="",
        )

        with (
            patch("tasks_ai.validator.shutil.which", return_value="/usr/bin/ruff"),
            patch("tasks_ai.validator.subprocess.run", return_value=result),
        ):
            check = validator.run_check("lint")

        self.assertFalse(check["success"])
        self.assertEqual(check["status"], "blocker")

    def test_validation_message_describes_a_promotion_blocker(self):
        messages = MessageRegistry()
        error = messages.get_error("PIPELINE_VALIDATION_FAILED")
        hint = messages.get_hint("PIPELINE_VALIDATION_FAILED", msg="lint failed")

        self.assertIn("blocked", error.lower())
        self.assertIn("blocker", hint.lower())
        self.assertIn("remains in its current state", hint)
        self.assertIn("hammer check all", hint)
        self.assertNotIn("Governance rules broken", hint)


if __name__ == "__main__":
    unittest.main()
