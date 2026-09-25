import json
import os
import unittest

from hammer_test_base import HammerTestBase


class TestBacklogToRejected(HammerTestBase):

    def test_backlog_to_rejected_transition(self):
        res = self.run_tasks(['create', 'Metadata Preservation Test Task', '--story', 'Testing metadata preservation during BACKLOG -> REJECTED transition', '--tech', 'Verify all metadata fields are intact after transition', '--criteria', 'All metadata preserved', '--plan', '1. Create task 2. Move to REJECTED 3. Verify metadata'])
        create_data = json.loads(res.stdout).get('data', {})
        task_id = create_data.get('id')
        task_file = create_data.get('file')
        self.assertIsNotNone(task_id)
        self.assertIsNotNone(task_file)
        list_res = self.run_tasks(['list'])
        list_data = json.loads(list_res.stdout)
        all_tasks = []
        for state_tasks in list_data.get('data', {}).values():
            all_tasks.extend(state_tasks)
        task_ids = [t.get('id') for t in all_tasks]
        self.assertIn(task_id, task_ids)
        res = self.run_tasks(['move', str(task_id), 'REJECTED'])
        output = json.loads(res.stdout)
        self.assertTrue(output.get('success', False), f'Move to REJECTED failed: {output}')
        task_dir = os.path.join(self.dev_tasks_dir, 'rejected', os.path.basename(task_file))
        self.assertTrue(os.path.exists(task_dir), f'Task directory not found in rejected: {task_dir}')
        meta_path = os.path.join(task_dir, 'meta.json')
        self.assertTrue(os.path.exists(meta_path), f'meta.json not found in {task_dir}')
        with open(meta_path, 'r') as f:
            meta = json.load(f)
        self.assertEqual(meta.get('Id'), task_id)
        self.assertEqual(meta.get('Ti'), 'Metadata Preservation Test Task')
        self.assertEqual(meta.get('Ty'), 'task')
        self.assertEqual(meta.get('Pr'), 2)
        self.assertIsInstance(meta.get('Cr'), str)
        self.assertIsInstance(meta.get('Bl'), list)
        self.assertIsInstance(meta.get('Br'), str)
        required_files = ['story.md', 'tech.md', 'criteria.md', 'plan.md', 'meta.json']
        for req_file in required_files:
            self.assertTrue(os.path.exists(os.path.join(task_dir, req_file)), f'Required file {req_file} not found in {task_dir}')
if __name__ == '__main__':
    unittest.main()