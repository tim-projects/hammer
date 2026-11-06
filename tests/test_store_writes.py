"""checkpoint and move must own their own slice of the shared .tasks store.

Locked down here:

1. Scope: 'tasks checkpoint <id>' and 'tasks move' stage only that task's paths,
   so one agent's write never commits another agent's uncommitted work.
2. Loudness: a failing 'git add' or 'git commit' in the store fails the command
   (error, non-zero exit, no 'Done.') instead of silently losing the record.
3. Cleanliness: after a move the store has nothing pending for the moved task -
   no .ops/staging copy, no old-state-folder deletions.
4. Sync: all task markdown parts reach the record, from any cwd (main repo root
   or a task worktree).
"""
import json
import os
import shutil
import subprocess
import tempfile
import unittest

STORY = 'Sufficiently long story content here to pass validation'
TECH = 'Sufficiently long technical description here to pass validation'
CRITERIA = 'Sufficiently long acceptance criteria here to pass validation'
PLAN = 'Sufficiently long planning details here to pass validation'

STORE_CONFIG = {
    'repo': {
        'lint': '/bin/true',
        'test': '/bin/true',
        'type_check': '/bin/true',
        'format': '/bin/true',
        'skip_push': True,
    }
}


class TestCheckpointStoreWrites(unittest.TestCase):

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.repo_dir = os.path.join(self.test_dir, 'repo')
        os.makedirs(self.repo_dir)
        subprocess.run(['git', 'init'], cwd=self.repo_dir, capture_output=True)  # noqa: PLW1510
        subprocess.run(['git', 'config', 'user.email', 'test@example.com'], cwd=self.repo_dir)  # noqa: PLW1510
        subprocess.run(['git', 'config', 'user.name', 'Test User'], cwd=self.repo_dir)  # noqa: PLW1510
        with open(os.path.join(self.repo_dir, 'README.md'), 'w') as handle:
            handle.write('# Test Repo')
        subprocess.run(['git', 'add', 'README.md'], cwd=self.repo_dir, capture_output=True)  # noqa: PLW1510
        subprocess.run(['git', 'commit', '-m', 'Initial commit'], cwd=self.repo_dir, capture_output=True)  # noqa: PLW1510
        # The symlinked hammer resolves to the working tree under test, so these
        # tests exercise the branch code, not a clone of main.
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.script_path = os.path.join(self.repo_dir, 'hammer')
        os.symlink(os.path.join(project_root, 'hammer'), self.script_path)
        subprocess.run(['git', 'add', 'hammer'], cwd=self.repo_dir, capture_output=True)  # noqa: PLW1510
        subprocess.run(['git', 'commit', '-m', 'Add hammer'], cwd=self.repo_dir, capture_output=True)  # noqa: PLW1510
        # The store is a real git repo of its own (branch 'tasks'), mirroring
        # production: .tasks is gitignored in the main repo and never merged.
        self.seed_tasks_branch()
        res = self.run_cmd(['init'])
        self.assertTrue(res['success'], f'init must build a store repo: {res}')
        self.assertTrue(os.path.isdir(os.path.join(self.repo_dir, '.tasks', '.git')),
                        'the .tasks store must be a git repository')
        self.assertTrue(os.path.exists(os.path.join(self.repo_dir, '.gitignore')),
                        'init must gitignore the store in the main repo')

    def seed_tasks_branch(self):
        """Create an orphan 'tasks' branch carrying the store default config.

        Built with plumbing (no checkout) so the fixture's working tree - and the
        symlinked hammer - survives untouched.
        """
        index = os.path.join(self.test_dir, 'seed_index')
        config_path = os.path.join(self.test_dir, 'seed_config.yaml')
        with open(config_path, 'w') as handle:
            json.dump(STORE_CONFIG, handle)
        env = dict(os.environ, GIT_INDEX_FILE=index)

        def git(*args, **kwargs):
            return subprocess.run(  # noqa: PLW1510
                ['git'] + list(args), cwd=self.repo_dir, capture_output=True, text=True,
                env=env if kwargs.get('indexed') else None,
            ).stdout.strip()

        blob = git('hash-object', '-w', config_path, indexed=True)
        tree = git('update-index', '--add', '--cacheinfo', f'100644,{blob},config.yaml',
                   indexed=True) or git('write-tree', indexed=True)
        commit = subprocess.run(  # noqa: PLW1510
            ['git', 'commit-tree', tree, '-m', 'Store default config'],
            cwd=self.repo_dir, capture_output=True, text=True,
        ).stdout.strip()
        subprocess.run(['git', 'branch', 'tasks', commit], cwd=self.repo_dir, capture_output=True)  # noqa: PLW1510

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    # --- helpers ---

    @property
    def store(self):
        return os.path.join(self.repo_dir, '.tasks')

    def run_cmd(self, args, cwd=None, env=None):
        run_env = dict(os.environ)
        if env:
            run_env.update(env)
        result = subprocess.run(  # noqa: PLW1510
            [self.script_path, 'tasks', '-j'] + args,
            cwd=cwd or self.repo_dir,
            capture_output=True,
            text=True,
            env=run_env,
        )
        try:
            payload = json.loads(result.stdout)
        except json.JSONDecodeError:
            return {'success': False, 'stdout': result.stdout, 'stderr': result.stderr,
                    'returncode': result.returncode}
        payload['returncode'] = result.returncode
        return payload

    def store_git(self, *args):
        return subprocess.run(  # noqa: PLW1510
            ['git'] + list(args), cwd=self.store, capture_output=True, text=True
        )

    def make_processing_task(self, title):
        res = self.run_cmd([
            'create', title,
            '--story', STORY,
            '--tech', TECH,
            '--criteria', CRITERIA,
            '--plan', PLAN,
        ])
        self.assertTrue(res['success'], res)
        task_file = res['data']['file']
        for state in ('READY', 'PROGRESSING'):
            moved = self.run_cmd(['move', task_file, state])
            self.assertTrue(moved['success'], moved)
        return res['data']['id'], task_file

    def make_task(self, title):
        res = self.run_cmd([
            'create', title,
            '--story', STORY,
            '--tech', TECH,
            '--criteria', CRITERIA,
            '--plan', PLAN,
        ])
        self.assertTrue(res['success'], res)
        return res['data']['id'], res['data']['file']

    def task_dir(self, task_file, state='progressing'):
        return os.path.join(self.store, state, task_file)

    def write_part(self, task_file, part, text, state='progressing'):
        path = os.path.join(self.task_dir(task_file, state), f'{part}.md')
        with open(path, 'w', encoding='utf-8') as handle:
            handle.write(text)
        return path

    def commit_files(self, rev='HEAD'):
        # --no-renames: a move must show up as the new path added *and* the old
        # state folder deleted, not as a silent rename that hides the deletion.
        out = self.store_git('show', '--name-only', '--no-renames', '--format=', rev).stdout
        return [line for line in out.splitlines() if line.strip()]

    # --- tests ---

    def test_checkpoint_commits_only_its_own_task(self):
        _, file_a = self.make_processing_task('Alpha task for checkpoint scoping')
        _, file_b = self.make_processing_task('Beta task for checkpoint scoping')
        self.write_part(file_a, 'story', f'{STORY}\nagent A edit')
        b_edit = f'{STORY}\nagent B uncommitted edit'
        self.write_part(file_b, 'story', b_edit)
        b_stray = os.path.join(self.task_dir(file_b), 'patches', 'b-pending.diff')
        os.makedirs(os.path.dirname(b_stray), exist_ok=True)
        with open(b_stray, 'w') as handle:
            handle.write('uncommitted by B')

        res = self.run_cmd(['checkpoint', file_a])
        self.assertTrue(res['success'], res)

        subject = self.store_git('log', '-1', '--format=%s').stdout.strip()
        self.assertEqual(subject, f'Cp: {file_a}')
        committed = self.commit_files()
        a_paths = [p for p in committed if file_a in p]
        b_paths = [p for p in committed if file_b in p]
        self.assertTrue(a_paths, f"task A's own changes must be committed: {committed}")
        self.assertFalse(b_paths, f"task B's pending changes must stay out: {committed}")
        self.assertIn(f'progressing/{file_a}/story.md', committed)

        status = self.store_git('status', '--porcelain', '--untracked-files=all').stdout.splitlines()
        self.assertTrue(any(f'{file_b}/story.md' in line for line in status),
                        f'task B must still be pending: {status}')
        self.assertTrue(any('b-pending.diff' in line for line in status),
                        f'task B must still be pending: {status}')
        with open(os.path.join(self.task_dir(file_b), 'story.md')) as handle:
            self.assertEqual(handle.read(), b_edit, 'B must keep its uncommitted edit')

        # B's own checkpoint commits only B, so no write ever lands in A's commit.
        res_b = self.run_cmd(['checkpoint', file_b])
        self.assertTrue(res_b['success'], res_b)
        self.assertEqual(self.store_git('log', '-1', '--format=%s').stdout.strip(), f'Cp: {file_b}')
        committed_b = self.commit_files()
        self.assertFalse([p for p in committed_b if file_a in p], committed_b)
        self.assertTrue([p for p in committed_b if f'{file_b}/story.md' in p], committed_b)
        self.assertIn(f'progressing/{file_b}/patches/b-pending.diff', committed_b,
                      'untracked files inside the task dir must be committed too')
        # Leftovers under old state folders and .ops/ come from the move path's
        # own store-wide add (tracked separately, not checkpoint scope): only the
        # live records must be fully committed by their own checkpoints.
        leftover = [line for line in self.store_git('status', '--porcelain').stdout.splitlines()
                    if f'progressing/{file_a}/' in line or f'progressing/{file_b}/' in line]
        self.assertEqual(leftover, [], 'both task records must be fully committed')

    def test_checkpoint_add_failure_is_fatal(self):
        _, file_a = self.make_processing_task('Gamma task for checkpoint failure')
        self.write_part(file_a, 'story', f'{STORY}\nagent edit before lock')
        lock = os.path.join(self.store, '.git', 'index.lock')
        with open(lock, 'w') as handle:
            handle.write('')
        try:
            res = self.run_cmd(['checkpoint', file_a])
        finally:
            os.remove(lock)

        self.assertNotEqual(res['returncode'], 0, 'a failed store add must exit non-zero')
        self.assertFalse(res['success'], res)
        self.assertIn('Store write failed', res.get('error', ''), res)
        self.assertNotIn('Done.', json.dumps(res.get('messages', [])), res)
        pending = self.store_git('status', '--porcelain').stdout
        self.assertIn('story.md', pending, 'the failed checkpoint must leave the edit pending')

        retry = self.run_cmd(['checkpoint', file_a])
        self.assertTrue(retry['success'], retry)
        self.assertIn(f'progressing/{file_a}/story.md', self.commit_files(),
                      'retry after the lock clears must commit the pending edit')

    def test_checkpoint_commit_failure_is_fatal(self):
        _, file_a = self.make_processing_task('Delta task for commit failure')
        self.write_part(file_a, 'story', f'{STORY}\nagent edit before bad date')
        res = self.run_cmd(['checkpoint', file_a], env={'GIT_COMMITTER_DATE': 'bogus'})

        self.assertNotEqual(res['returncode'], 0, 'a failed store commit must exit non-zero')
        self.assertFalse(res['success'], res)
        self.assertIn('Store write failed', res.get('error', ''), res)
        self.assertNotIn('Done.', json.dumps(res.get('messages', [])), res)
        self.assertIn('story.md', self.store_git('status', '--porcelain').stdout,
                      'the uncommitted edit must survive the failed commit')

    def test_hand_edited_parts_reach_the_record(self):
        _, file_a = self.make_processing_task('Epsilon task for part sync')
        criteria = 'Hand written criteria the agent edited straight on disk'
        tech = 'Hand written technical notes the agent edited straight on disk'
        self.write_part(file_a, 'criteria', criteria)
        self.write_part(file_a, 'tech', tech)

        res = self.run_cmd(['checkpoint', file_a])
        self.assertTrue(res['success'], res)

        committed = self.commit_files()
        self.assertIn(f'progressing/{file_a}/criteria.md', committed, committed)
        self.assertIn(f'progressing/{file_a}/tech.md', committed, committed)
        for part, text in (('criteria', criteria), ('tech', tech)):
            shown = self.store_git('show', f'HEAD:progressing/{file_a}/{part}.md').stdout
            self.assertEqual(shown.strip(), text, f'{part} must be synced into the record')

    def test_sync_and_checkpoint_work_from_task_worktree_cwd(self):
        """The sync path must not depend on the process cwd."""
        _, file_a = self.make_processing_task('Zeta task for worktree cwd')
        worktree = os.path.join(self.test_dir, 'wt')
        base = subprocess.run(  # noqa: PLW1510
            ['git', 'rev-parse', '--abbrev-ref', 'HEAD'],
            cwd=self.repo_dir, capture_output=True, text=True,
        ).stdout.strip()
        added = subprocess.run(  # noqa: PLW1510
            ['git', 'worktree', 'add', '--detach', worktree, base],
            cwd=self.repo_dir, capture_output=True, text=True,
        )
        self.assertEqual(added.returncode, 0, added.stderr)
        self.assertTrue(os.path.exists(os.path.join(worktree, 'hammer')))

        plan = 'Plan edited while hammer ran from the task worktree'
        self.write_part(file_a, 'plan', plan)
        res = self.run_cmd(['checkpoint', file_a], cwd=worktree)

        self.assertTrue(res['success'], res)
        committed = self.commit_files()
        self.assertIn(f'progressing/{file_a}/plan.md', committed, committed)
        shown = self.store_git('show', f'HEAD:progressing/{file_a}/plan.md').stdout
        self.assertEqual(shown.strip(), plan)

    # --- move path ---

    def test_move_does_not_commit_other_task_pending_changes(self):
        _, file_a = self.make_task('Alpha task for move scoping')
        _, file_b = self.make_task('Beta task for move scoping')
        b_edit = f'{STORY}\nagent B uncommitted edit'
        self.write_part(file_b, 'story', b_edit, state='backlog')

        res = self.run_cmd(['move', file_a, 'READY'])
        self.assertTrue(res['success'], res)

        subject = self.store_git('log', '-1', '--format=%s').stdout.strip()
        self.assertEqual(subject, f'Mv {file_a} -> READY')
        committed = self.commit_files()
        self.assertTrue([p for p in committed if file_a in p], committed)
        self.assertFalse([p for p in committed if file_b in p], committed)
        self.assertIn(f'ready/{file_a}/story.md', committed,
                      'the moved record must be in the move commit')
        self.assertIn(f'backlog/{file_a}/story.md', committed,
                      'the old state folder must be recorded as deleted')

        status = self.store_git('status', '--porcelain', '--untracked-files=all').stdout
        self.assertIn(f'backlog/{file_b}/story.md', status,
                      f'task B must still be pending: {status}')
        with open(os.path.join(self.task_dir(file_b, 'backlog'), 'story.md')) as handle:
            self.assertEqual(handle.read(), b_edit, 'B must keep its uncommitted edit')

    def test_store_has_no_pending_leftovers_after_move(self):
        _, file_a = self.make_task('Gamma task for move cleanliness')
        res = self.run_cmd(['move', file_a, 'READY'])
        self.assertTrue(res['success'], res)

        status = self.store_git('status', '--porcelain', '--untracked-files=all').stdout
        ops_leftovers = [line for line in status.splitlines() if '.ops/' in line]
        self.assertEqual(ops_leftovers, [],
                         f'the .ops staging copy must not linger: {status}')
        stale = [line for line in status.splitlines() if f'backlog/{file_a}/' in line]
        self.assertEqual(stale, [],
                         f'the old state folder must be committed as deleted: {status}')
        moved = [line for line in status.splitlines() if f'ready/{file_a}/' in line]
        self.assertEqual(moved, [], f'the new record must be committed: {status}')

    def test_move_leaves_the_store_clean_for_both_agents(self):
        """The move commit must close out the move, leaving nothing pending.

        'tasks undo' cannot assert this end to end: it silently no-ops in this
        fixture (a pre-existing defect, independent of the store write), so the
        cleanup is asserted straight from the store instead.
        """
        _, file_a = self.make_task('Delta task for move cleanliness')
        _, file_b = self.make_task('Epsilon task for move cleanliness')
        self.write_part(file_b, 'story', f'{STORY}\nagent B uncommitted edit',
                        state='backlog')

        moved = self.run_cmd(['move', file_a, 'READY'])
        self.assertTrue(moved['success'], moved)

        committed = self.commit_files()
        self.assertIn(f'ready/{file_a}/story.md', committed, committed)
        self.assertIn(f'backlog/{file_a}/story.md', committed, committed)
        status = self.store_git('status', '--porcelain', '--untracked-files=all').stdout
        self.assertFalse([line for line in status.splitlines() if file_a in line],
                         f'nothing may stay pending for the moved task: {status}')
        self.assertTrue([line for line in status.splitlines() if file_b in line],
                        f'task B must still be pending: {status}')


if __name__ == '__main__':
    unittest.main()
