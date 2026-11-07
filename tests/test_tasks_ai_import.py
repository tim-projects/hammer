"""`import tasks_ai` must resolve to the project package, never a copy under tests/.

Regression test for issue 340: a stale tasks_ai snapshot was tracked in tests/
and pytest put tests/ ahead of the project root on sys.path, so tests silently
imported the shadowed copy and crashed on modules it lacked.
"""

import os
import sys
import unittest

import tasks_ai


class TestTasksAiResolution(unittest.TestCase):
    def setUp(self):
        self.root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    def test_package_is_the_project_one(self):
        self.assertEqual(
            os.path.realpath(tasks_ai.__path__[0]),
            os.path.join(os.path.realpath(self.root), "tasks_ai"),
        )

    def test_no_shadowing_copy_in_tests(self):
        self.assertFalse(os.path.exists(os.path.join(self.root, "tests", "tasks_ai")))
        self.assertEqual(
            [p for p in sys.path if p.endswith(os.path.join("tests", "tasks_ai"))],
            [],
        )
