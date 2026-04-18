import os
import sys
import subprocess
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from .cli import TasksCLI

class Validation:
    def __init__(self, cli: 'TasksCLI'):
        self.cli = cli

    def run_lint(self, fix=False):
        check_path = os.path.join(self.cli.root, "check.py")
        if not os.path.exists(check_path):
            return
        result = subprocess.run(
            [sys.executable, check_path, "lint"] + (["--fix"] if fix else []),
            cwd=self.cli.root,
            capture_output=True,
            text=True,
            timeout=60,
        )
        if result.returncode != 0:
            self.cli.error(
                "❌ HAMMER SAY NO! VALIDATION BROKEN! FIX NOW! 🔨",
                hint="RUN 'check lint' TO SEE ERRORS. HAMMER NO BYPASS TOOL!",
            )

    def run_tests(self, fail_safe=False):
        check_path = os.path.join(self.cli.root, "check.py")
        if not os.path.exists(check_path):
            return subprocess.CompletedProcess("", 0)
        result = subprocess.run(
            [sys.executable, check_path, "test"],
            cwd=self.cli.root,
            capture_output=True,
            text=True,
            timeout=120,
        )
        if result.returncode != 0:
            if fail_safe:
                return result
            self.cli.error(
                "❌ TEST BREAK! HAMMER SAY NO! FIX NOW! 🔨",
                hint="RUN 'check test' TO SEE FAILURES. HAMMER NO BYPASS TOOL!",
            )
        return result
