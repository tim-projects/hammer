import importlib.util
import json
import os
import subprocess
import unittest
from unittest.mock import patch

from tasks_ai.constants import ALLOWED_CONFIG_KEYS
from tasks_ai.validation import Validation
from tasks_ai.validator import Validator

ROOT_CHECK_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "check.py"
)
SPEC = importlib.util.spec_from_file_location("root_check_unref", ROOT_CHECK_PATH)
root_check = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(root_check)


def completed(command, returncode=0, stdout="", stderr=""):
    return subprocess.CompletedProcess(
        args=command,
        returncode=returncode,
        stdout=stdout,
        stderr=stderr,
    )


class TestOptionalUnrefLint(unittest.TestCase):
    def test_configuration_command_accepts_secondary_lint(self):
        self.assertIn("repo.lint_secondary", ALLOWED_CONFIG_KEYS)

    def validator(self, secondary=None):
        validator = Validator.__new__(Validator)
        validator.project_root = os.getcwd()
        validator.dev = False
        validator.config = {"repo": {"lint": "ruff"}}
        if secondary is not None:
            validator.config["repo"]["lint_secondary"] = secondary
        return validator

    def test_secondary_is_disabled_by_default(self):
        validator = self.validator()
        ruff = completed(["ruff"], stdout="[]")

        with (
            patch("tasks_ai.validator.shutil.which", return_value="/usr/bin/ruff"),
            patch("tasks_ai.validator.subprocess.run", return_value=ruff) as run,
        ):
            result = validator.run_check("lint")

        self.assertTrue(result["success"])
        self.assertEqual(run.call_count, 1)
        self.assertEqual(result["secondary_stdout"], "")

    def test_enabled_unref_runs_after_ruff_and_can_fail(self):
        validator = self.validator("unref")
        ruff = completed(["ruff"], stdout="[]")
        unref = completed(
            ["unref"],
            returncode=1,
            stdout="src/app.py:10:5: unused-function 'parse_date'",
        )

        with (
            patch(
                "tasks_ai.validator.shutil.which",
                side_effect=["/usr/bin/ruff", "/usr/bin/unref"],
            ),
            patch(
                "tasks_ai.validator.subprocess.run",
                side_effect=[ruff, unref],
            ) as run,
        ):
            result = validator.run_check("lint")

        self.assertFalse(result["success"])
        self.assertEqual(result["exit_code"], 1)
        self.assertIn("unused-function", result["secondary_stdout"])
        self.assertEqual(run.call_count, 2)
        self.assertEqual(run.call_args_list[1].args[0], ["/usr/bin/unref"])
        self.assertEqual(run.call_args_list[1].kwargs["cwd"], validator.project_root)

    def test_unref_runs_even_when_ruff_fails(self):
        validator = self.validator("unref")
        ruff = completed(["ruff"], returncode=1, stdout="[]")
        unref = completed(["unref"], stdout="unused-function")

        with (
            patch(
                "tasks_ai.validator.shutil.which",
                side_effect=["/usr/bin/ruff", "/usr/bin/unref"],
            ),
            patch(
                "tasks_ai.validator.subprocess.run",
                side_effect=[ruff, unref],
            ) as run,
        ):
            result = validator.run_check("lint")

        self.assertFalse(result["success"])
        self.assertEqual(run.call_count, 2)
        self.assertIn("unused-function", result["secondary_stdout"])

    def test_enabled_unref_missing_is_an_actionable_failure(self):
        validator = self.validator("unref")
        ruff = completed(["ruff"], stdout="[]")

        with (
            patch(
                "tasks_ai.validator.shutil.which",
                side_effect=["/usr/bin/ruff", None],
            ),
            patch("tasks_ai.validator.subprocess.run", return_value=ruff),
        ):
            result = validator.run_check("lint")

        self.assertFalse(result["success"])
        self.assertEqual(result["exit_code"], 127)
        self.assertIn("Tool 'unref' not found", result["secondary_stdout"])
        self.assertIn("repo.lint_secondary", result["secondary_stdout"])

    def test_fix_keeps_ruff_fix_and_does_not_fix_unref(self):
        validator = self.validator("unref")
        ruff = completed(["ruff"], stdout="[]")
        unref = completed(["unref"])

        with (
            patch(
                "tasks_ai.validator.shutil.which",
                side_effect=["/usr/bin/ruff", "/usr/bin/unref"],
            ),
            patch(
                "tasks_ai.validator.subprocess.run",
                side_effect=[ruff, unref],
            ) as run,
        ):
            validator.run_check("lint", fix=True)

        ruff_command = run.call_args_list[0].args[0]
        unref_command = run.call_args_list[1].args[0]
        self.assertIn("--fix", ruff_command)
        self.assertNotIn("--fix", unref_command)
        self.assertEqual(unref_command, ["/usr/bin/unref"])

    def test_promotion_message_keeps_secondary_failure_without_primary_output(self):
        class FakeCLI:
            as_json = True
            dev = False

            def __init__(self):
                self.context = type(
                    "Context",
                    (),
                    {"repo_root": os.getcwd(), "main_repo_root": os.getcwd()},
                )()
                self.next_steps = []

            def next_step(self, code, **kwargs):
                self.next_steps.append((code, kwargs))
                raise RuntimeError(code)

        cli = FakeCLI()
        payload = {
            "success": False,
            "tool": "lint",
            "stdout": "",
            "stderr": "",
            "secondary_stdout": "Tool 'unref' not found in PATH or venv.",
            "exit_code": 127,
        }
        result = completed(
            ["check.py", "lint", "--json"],
            returncode=1,
            stdout=json.dumps(payload),
        )

        with (
            patch("tasks_ai.validation.subprocess.run", return_value=result),
            self.assertRaises(RuntimeError),
        ):
            Validation(cli).run_tool("lint")

        code, details = cli.next_steps[0]
        self.assertEqual(code, "VALIDATION_FAILED")
        self.assertIn("unref:", details["msg"])
        self.assertIn("not found in PATH", details["msg"])

    def test_legacy_gate_supports_the_same_opt_in_contract(self):
        config = {"repo": {"lint": "ruff", "lint_secondary": "unref"}}
        ruff = completed(["ruff"], stdout="[]")
        unref = completed(["unref"], returncode=1, stdout="unused-function")

        with (
            patch.object(root_check, "load_config", return_value=config),
            patch.object(root_check, "find_project_root", return_value=os.getcwd()),
            patch.object(
                root_check.shutil,
                "which",
                side_effect=["/usr/bin/ruff", "/usr/bin/unref"],
            ),
            patch.object(
                root_check.subprocess,
                "run",
                side_effect=[ruff, unref],
            ) as run,
        ):
            result = root_check.run_check("lint", as_json=True)

        self.assertEqual(result, 1)
        self.assertEqual(run.call_count, 2)
        self.assertEqual(run.call_args_list[1].args[0], ["/usr/bin/unref"])


if __name__ == "__main__":
    unittest.main()
