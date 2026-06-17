import unittest
from tasks_ai.validator import Validator


class TestValidation(unittest.TestCase):
    def test_run_all(self):
        v = Validator(".")
        results = v.run_all()
        # Ensure all results have a success key
        for r in results:
            self.assertIn("success", r)
