# plan-cleanup.md

## Goal
Start a clean repository at `~/git/hammer` using the current `main` branch code of `~/git/tasks-ai`, audit the old task backlog, and recreate only the tasks that are still relevant. Drop the corrupt/duplicate/historical noise.

## Context
- The `.tasks` worktree is corrupt: duplicate IDs, placeholder tasks, and tasks that were nuked and replaced.
- Task states (BACKLOG/PROGRESSING/etc.) are unreliable — the state machine's view cannot be trusted.
- The worktree-based task system (task 87) changed how branches/worktrees are tracked, so pre-migration tasks carry stale worktree metadata.
- Two backups exist: `~/git/tasks-ai.backup` and `~/git/tasks-ai.backup.30.7.2026`.
- Guard tooling (`hammer guard`) can detect duplicate IDs and worktree anomalies; it cannot tell us whether a task's work is already in `main`.

## Strategy
Fresh start. The old `.tasks` is treated as a **data source for auditing**, not as the new repo's task store. The new repo gets a clean `.tasks` populated only with verified-relevant tasks.

## Phase 1 — Snapshot and inventory
1. Snapshot current state: `cp -a ~/git/tasks-ai/.tasks /tmp/.tasks-snapshot`.
2. Build a cross-source task inventory (ignore state dirs — they lie):
   - Sources: `~/git/tasks-ai/.tasks`, `~/git/tasks-ai.backup/.tasks`, `~/git/tasks-ai.backup.30.7.2026/.tasks`.
   - For each ID, collect every copy from every source and every state dir.
   - Merge per ID by content richness (story + tech + criteria + progress), not by state.
   - Record: `id, sources, state_conflict, best_copy_source, content_hash, title, summary`.
3. Output: `/tmp/ledger.csv`.

Decision rule: same ID in multiple sources/state dirs is expected; the richest copy wins, conflicts get flagged for manual review.

## Phase 2 — Evidence-based triage against `main`
For each task in the ledger, determine completion status using **code evidence, not state labels**:

1. Extract concrete signals from the task content: file paths, function/CLI command names, error codes, feature keywords.
2. Grep the current `main` codebase for those signals.
3. Check `git log --all --grep=<task-id>` and branch existence.
4. Check `git merge-base --is-ancestor <branch> main` for any related branch.

Output per task: `done-in-main | partially-done | not-done | unknown`, with grep evidence (file:line) and commit/branch evidence cited.

Rules:
- `done-in-main` and `partially-done` tasks are dropped from the new repo unless they have a follow-up (e.g., "extend X" or "fix regression in X").
- `unknown` defaults to **keep** — safer than dropping.
- High-priority `not-done` tasks are always kept.
- Every drop decision must cite evidence so it is reviewable.

## Phase 3 — Build the new repo
1. `mkdir ~/git/hammer && cd ~/git/hammer && git init`.
2. Copy the code from `main` of `~/git/tasks-ai` (the tool code: `hammer`, `repo.py`, `tasks.py`, `tasks_ai/`, `data/`, `tests/`, etc.) — **not** the old `.tasks`.
3. Copy README/docs as-is, regenerate config as needed for the new repo.
4. Initialize a fresh `.tasks` (no old task dirs carried over).
5. Initial commit: the clean baseline.

## Phase 4 — Recreate kept tasks
For each task surviving Phase 2:
1. Allocate a fresh ID in the new repo (do not reuse old IDs — they are corrupt).
2. Create the task with the rich content from the ledger's best copy.
3. Post-migration tasks: preserve branch/worktree fidelity if still valid.
4. Pre-migration tasks: content-only fidelity (discard stale worktree/branch metadata).
5. Re-point any dependency links to the new IDs, rewriting inbound references.
6. Record the old-ID mapping in a `migration.md` in the new repo for traceability.

## Phase 5 — Validation
1. `hammer guard rebuild` and `hammer guard scan` in the new repo — must be clean.
2. Run the test suite in the new repo against the fresh `.tasks`.
3. Confirm no dangling references (grep `links:` and old IDs across the new `.tasks`).
4. Confirm the counter is above the highest allocated ID.

## Risks
- **Heuristic completion check**: a task may be partially implemented without obvious grep hits. `unknown` keeps the task; `partially-done` needs a human read before dropping.
- **Lost history**: old branches and worktrees are not carried over. That is intentional, but keep the old repo read-only as a reference archive — do not delete it.
- **Cross-source divergence**: two backups may disagree on a task's content. Flagged copies go to manual review, not auto-drop.
- **Link rewriting**: missed inbound dependency links create dangling blockers. Grep-verify before swap.
- **Guard cache**: rebuild from scratch; never carry forward old guard state.

## Non-goals
- Do not repair the old `.tasks` in place.
- Do not rename or rewrite old task IDs.
- Do not delete the old repo or backups.
- Do not port pre-migration worktree/branch metadata.

## Status
- [ ] Phase 1 — snapshot + cross-source inventory
- [ ] Phase 2 — evidence-based triage
- [ ] Phase 3 — new repo baseline
- [ ] Phase 4 — recreate kept tasks
- [ ] Phase 5 — validate
