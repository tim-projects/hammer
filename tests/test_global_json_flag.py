"""Global -j/--json directive placement and output contract."""

import json
import os
import subprocess
import unittest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HAMMER = os.path.join(PROJECT_ROOT, "hammer")


def run_hammer(*args):
    return subprocess.run(
        [HAMMER, *args],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


class TestGlobalJsonFlag(unittest.TestCase):
    def assert_json(self, result):
        try:
            json.loads(result.stdout)
        except json.JSONDecodeError as exc:
            self.fail(f"not JSON: {result.stdout!r}: {exc}")

    def test_json_is_valid_in_every_tool_position(self):
        invocations = [
            ("-j", "tasks", "list"),
            ("tasks", "-j", "list"),
            ("tasks", "list", "-j"),
            ("--json", "tasks", "list"),
            ("tasks", "--json", "list"),
            ("tasks", "list", "--json"),
            ("-j", "repo", "status"),
            ("repo", "-j", "status"),
            ("repo", "status", "-j"),
            ("-j", "check", "lint"),
            ("check", "-j", "lint"),
            ("check", "lint", "-j"),
            ("-j", "guard", "scan"),
            ("guard", "-j", "scan"),
            ("guard", "scan", "-j"),
        ]
        for args in invocations:
            with self.subTest(args=args):
                result = run_hammer(*args)
                self.assert_json(result)

    def test_auto_detected_command_accepts_json(self):
        for args in (("-j", "list"), ("list", "-j"), ("--json", "list")):
            with self.subTest(args=args):
                self.assert_json(run_hammer(*args))

    def test_help_overrides_json(self):
        for args in (
            ("-j", "tasks", "list", "-h"),
            ("tasks", "-j", "list", "--help"),
            ("--json", "repo", "merge", "-h"),
            ("repo", "--json", "status", "-h"),
        ):
            with self.subTest(args=args):
                result = run_hammer(*args)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertTrue(result.stdout.lstrip().startswith("usage"))
                self.assertNotIn('"success"', result.stdout)

    def test_invalid_json_command_is_json(self):
        result = run_hammer("-j", "not-a-command")
        self.assertEqual(result.returncode, 1)
        self.assert_json(result)


if __name__ == "__main__":
    unittest.main()
