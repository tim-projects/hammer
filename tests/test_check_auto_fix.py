import importlib.util
import os
import unittest
from unittest.mock import patch

from tasks_ai.validator import Validator

ROOT_CHECK_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "check.py"
)
SPEC = importlib.util.spec_from_file_location("root_check", ROOT_CHECK_PATH)
root_check = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(root_check)


class TestCheckAllAutoFixesRuff(unittest.TestCase):
    def test_ruff_command_keeps_json_output_and_adds_fix(self):
        validator = Validator(".")
        regular = validator._get_commands(False)["lint"]["ruff"]
        auto_fixed = validator._get_commands(False, auto_fix_ruff=True)["lint"]["ruff"]
        legacy_regular = root_check.get_commands(False)["lint"]["ruff"]
        legacy_auto_fixed = root_check.get_commands(False, auto_fix_ruff=True)["lint"][
            "ruff"
        ]

        for command in (regular, legacy_regular):
            self.assertNotIn("--fix", command)
            self.assertIn("--output-format=json", command)
        for command in (auto_fixed, legacy_auto_fixed):
            self.assertIn("--fix", command)
            self.assertIn("--output-format=json", command)

    def test_validator_check_all_auto_fixes_only_ruff_lint(self):
        validator = Validator(".")
        calls = []

        def record_call(tool, fix=False, timeout=300, auto_fix_ruff=False):
            calls.append((tool, auto_fix_ruff))
            return {"success": True}

        with patch.object(validator, "run_check", side_effect=record_call):
            validator.run_all()

        self.assertEqual(
            calls,
            [
                ("lint", True),
                ("test", False),
                ("typecheck", False),
                ("format", False),
            ],
        )

    def test_legacy_check_all_auto_fixes_only_ruff_lint(self):
        calls = []

        def record_call(tool, fix=False, as_json=False, dev=False, auto_fix_ruff=False):
            calls.append((tool, auto_fix_ruff))
            return 0

        with (
            patch.object(root_check, "run_check", side_effect=record_call),
            patch.object(root_check, "run_debug_check", return_value=0),
        ):
            root_check.run_all()

        self.assertEqual(
            calls,
            [
                ("lint", True),
                ("test", False),
                ("typecheck", False),
                ("format", False),
            ],
        )


if __name__ == "__main__":
    unittest.main()
