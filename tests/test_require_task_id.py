import json
import os
import unittest

from hammer_test_base import HammerTestBase

STORY = 'Sufficiently long story content here to pass validation'
TECH = 'Sufficiently long technical description here to pass validation'
CRITERIA = 'Sufficiently long acceptance criteria here to pass validation'
PLAN = 'Sufficiently long planning details here to pass validation'


def make_processing_task(base, title):
    res = base.run_tasks([
        'create', title,
        '--story', STORY,
        '--tech', TECH,
        '--criteria', CRITERIA,
        '--plan', PLAN,
    ])
    data = json.loads(res.stdout)['data']
    task_file = data['file']
    base.run_tasks(['move', str(data['id']), 'READY,PROGRESSING'])
    return str(data['id']), task_file


def run_cli(base, args):
    res = base.run_tasks(args)
    try:
        return json.loads(res.stdout)
    except json.JSONDecodeError:
        return {'success': False, 'stdout': res.stdout, 'stderr': res.stderr}


def snapshot(base, task_file):
    snap = {}
    root = os.path.join(base.dev_tasks_dir, 'progressing', task_file)
    for name in sorted(os.listdir(root)):
        with open(os.path.join(root, name)) as handle:
            snap[name] = handle.read()
    return snap


class TestRequireTaskId(HammerTestBase):
    """checkpoint/current/undo must never operate on an arbitrary PROGRESSING task."""

    def test_no_id_is_rejected(self):
        # Above every real task id: a fixture id that collides with a real
        # branch is a genuine duplicate-id violation, not a test target.
        self.seed_counter(9000)
        make_processing_task(self, 'Alpha task for id requirement testing')
        make_processing_task(self, 'Beta task for id requirement testing')
        for cmd in ('checkpoint', 'current', 'undo'):
            res = run_cli(self, [cmd])
            self.assertFalse(res['success'], f'{cmd} without id must fail: {res}')

    def test_no_id_writes_nothing(self):
        self.seed_counter(9000)
        _, file_a = make_processing_task(self, 'Gamma task for id requirement testing')
        _, file_b = make_processing_task(self, 'Delta task for id requirement testing')
        before = (snapshot(self, file_a), snapshot(self, file_b))
        for cmd in ('checkpoint', 'current', 'undo'):
            run_cli(self, [cmd])
        self.assertEqual(
            (snapshot(self, file_a), snapshot(self, file_b)),
            before,
            'no-id commands must not touch any task record',
        )

    def test_explicit_id_hits_only_that_task(self):
        self.seed_counter(9000)
        id_a, file_a = make_processing_task(self, 'Epsilon task for id requirement testing')
        _, file_b = make_processing_task(self, 'Zeta task for id requirement testing')
        before_b = snapshot(self, file_b)
        res = run_cli(self, ['checkpoint', id_a])
        self.assertTrue(res['success'], res)
        self.assertEqual(str(res['data']['id']), id_a)
        self.assertEqual(before_b, snapshot(self, file_b), 'checkpoint touched another task record')

    def test_current_with_id_reports_that_task(self):
        self.seed_counter(9000)
        id_a, file_a = make_processing_task(self, 'Eta task for id requirement testing')
        make_processing_task(self, 'Theta task for id requirement testing')
        res = run_cli(self, ['current', id_a])
        self.assertTrue(res['success'], res)
        self.assertEqual(res['data']['name'], file_a)

    def test_unresolvable_id_is_rejected(self):
        self.seed_counter(9000)
        make_processing_task(self, 'Iota task for id requirement testing')
        make_processing_task(self, 'Kappa task for id requirement testing')
        for cmd in ('checkpoint', 'current', 'undo'):
            res = run_cli(self, [cmd, '999999'])
            self.assertFalse(res['success'], f'{cmd} with a bad id must fail: {res}')


if __name__ == '__main__':
    unittest.main()
