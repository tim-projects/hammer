RESEARCH (495 - legacy retirement):
- Verified live: .task_counter, .task_counter.hash, .task_counter.backup(.hash) (4 files) still written; worktree_manager.py:15 MANIFEST_NAME = 'worktrees.json'; list.py:62 ID-recovery fallback (task_id = item.split('-')[0]).
- Counter-recovery helpers live in cli.py (~684, ~781-785, ~1257+ - confirm exact lines at implementation time; they moved between merges).
- CONSTRAINT: do NOT delete tasks_ai/cli_engine.py - tasks_ai/__init__.py:1 imports TasksCLI from it; hammer-issues-1.md 6.3d records the old plan-guard item as factually wrong.
- After 455 (lazy creation) ids must derive from refs/derive_task_id alone - that is what makes the retirement safe; the guard DB table (guard_engine) replaces the manifest's role.
