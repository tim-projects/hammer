import json
import os
import signal
import subprocess
import sys

from tests.hammer_test_base import HammerTestBase

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TASKS_SCRIPT = os.path.join(PROJECT_ROOT, "tasks.py")

STORY = "Sufficiently long story content here to pass validation"
CRITERIA = "Sufficiently long acceptance criteria here to pass validation"
PLAN = "Sufficiently long planning details here to pass validation"


class TestSigpipe(HammerTestBase):
    def test_early_closed_output_has_no_traceback(self):
        tech_file = os.path.join(self.test_root, "large-tech.txt")
        with open(tech_file, "w") as handle:
            handle.write("x" * (256 * 1024))

        result = self.run_tasks(
            [
                "create",
                "Early closed pipe regression task",
                "--story",
                STORY,
                "--tech",
                tech_file,
                "--criteria",
                CRITERIA,
                "--plan",
                PLAN,
            ]
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        task_id = json.loads(result.stdout)["data"]["file"].split("-")[0]

        process = subprocess.Popen(
            [sys.executable, TASKS_SCRIPT, "--dev", "show", task_id],
            cwd=self.repo_path,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        try:
            self.assertTrue(process.stdout.readline())
            process.stdout.close()
            stderr = process.stderr.read()
            returncode = process.wait(timeout=10)
        finally:
            if process.stdout and not process.stdout.closed:
                process.stdout.close()
            process.stderr.close()

        self.assertNotIn("BrokenPipeError", stderr)
        self.assertNotIn("Traceback", stderr)
        self.assertEqual(returncode, -signal.SIGPIPE)

    def test_sigpipe_configuration_is_platform_safe(self):
        if not hasattr(signal, "SIGPIPE"):
            self.skipTest("SIGPIPE is unavailable on this platform")

        from tasks_ai.cli_io import configure_sigpipe

        original = signal.getsignal(signal.SIGPIPE)
        try:
            configure_sigpipe()
            self.assertEqual(signal.getsignal(signal.SIGPIPE), signal.SIG_DFL)
        finally:
            signal.signal(signal.SIGPIPE, original)
