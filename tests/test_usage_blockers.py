import os
import subprocess
import unittest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HAMMER = os.path.join(PROJECT_ROOT, "hammer")

INVALID_USAGE = [
    (["tasks", "checkpoint"], "the following arguments are required: filename"),
    (["tasks", "show", "999999", "invalid-section"], "invalid choice"),
    (["tasks", "list", "--unknown-option"], "unrecognized arguments"),
    (
        ["tasks", "create", "Valid task title", "--priority", "not-a-number"],
        "invalid int value",
    ),
    (["check", "not-a-command"], "invalid choice"),
    (["check", "lint", "--unknown-option"], "unrecognized arguments"),
    (["repo", "not-a-command"], "invalid choice"),
    (["repo", "merge"], "the following arguments are required: src, dest"),
    (["repo", "branch"], "the following arguments are required: action"),
    (["guard", "not-a-command"], "invalid choice"),
    (["guard", "check"], "check requires a task id or --branch"),
]


def run_hammer(*args):
    return subprocess.run(  # noqa: PLW1510
        [HAMMER, *args],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )


class TestUsageBlockers(unittest.TestCase):
    def test_invalid_usage_is_reported_as_a_blocker(self):
        for args, detail in INVALID_USAGE:
            with self.subTest(command=" ".join(args)):
                result = run_hammer(*args)

                self.assertEqual(result.returncode, 2)
                self.assertIn("usage:", result.stderr.lower())
                self.assertIn(": blocker:", result.stderr)
                self.assertNotIn(": error:", result.stderr)
                self.assertIn(detail, result.stderr)

    def test_successful_help_is_not_a_blocker(self):
        invocations = [
            ("tasks", "--help"),
            ("check", "--help"),
            ("repo", "--help"),
            ("guard", "--help"),
        ]

        for args in invocations:
            with self.subTest(command=" ".join(args)):
                result = run_hammer(*args)

                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertNotIn(": blocker:", result.stderr)


if __name__ == "__main__":
    unittest.main()
