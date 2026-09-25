import os
import tempfile
import unittest
from tasks_ai.cli import TasksCLI
from tasks_ai.models import Task

class TestArtifactHealing(unittest.TestCase):

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.tasks_path = os.path.join(self.test_dir, '.tasks')
        os.makedirs(self.tasks_path)
        self.cli = TasksCLI(dev=True)
        self.cli.tasks_path = self.tasks_path

    def test_verify_and_regenerate_patches(self):
        review_path = os.path.join(self.tasks_path, 'review', '288-task-test-task')
        os.makedirs(review_path, exist_ok=True)
        task = Task(metadata={'Id': '288', 'PatchFiles': [{'file': 'f1', 'patch_path': os.path.join(review_path, 'f1.patch')}]})
        self.cli._atomic_write(review_path, task)
if __name__ == '__main__':
    unittest.main()