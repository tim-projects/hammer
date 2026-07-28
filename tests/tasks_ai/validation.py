import os
import subprocess
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .cli import TasksCLI


class Validation:
    def __init__(self, cli: "TasksCLI"):
        self.cli = cli

    def run_lint(self, fix=False):
        if os.environ.get("TASKS_TESTING") == "1":
            return
        from tasks_ai.validator import Validator

        validator = Validator(self.cli.root)
        validator.run_check("lint", fix)

    def run_tests(self, fail_safe=False):
        if os.environ.get("TASKS_TESTING") == "1":
            return subprocess.CompletedProcess("", 0)
        from tasks_ai.validator import Validator

        validator = Validator(self.cli.root)
        try:
            return validator.run_check("test", False)
        except Exception:
            if fail_safe:
                return subprocess.CompletedProcess("", 1)
            self.cli.error(
                "❌ TEST BREAK! HAMMER SAY NO! FIX NOW! 🔨",
                hint="RUN 'check test' TO SEE FAILURES. HAMMER NO BYPASS TOOL!",
            )
            return subprocess.CompletedProcess("", 1)
