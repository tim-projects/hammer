# Plan: `hammer guard` — Git-as-Database Integrity Enforcement

**Status:** Proposed
**Date:** 2026-11-01
**Scope:** New `hammer guard` tool + pipeline gate enforcement. No change to task content format.

---

## 1. Problem Statement

Hammer occasionally produces **duplicate task IDs** (two tasks/branches/folders claiming the same numeric ID). A single duplicate ID fundamentally breaks the workflow: `find_task` resolves ambiguously, transitions target the wrong task, and state is silently corrupted. Today the only remedy is `doctor` — *repair after corruption*.

Observed corruption artifacts (from repo history):

- `.tasks/backlog/178-task-consolidate-repo-merge-and-tas/` and `.tasks/progressing/178-task-consolidate-repo-merge-and-tas/` both existed; the backlog copy carried `{"Id": 181}` (`TASK_ID_MISMATCH_BUG_REPORT.md`).
- `.tasks/backlog/4-task-test-verification-gate-task/` carried `{"Id": 158}` (`TASK_ID_MISMATCH_ROOT_CAUSE.md`).
- `doctor` has generated a standing pile of `hammer-bug-*.md` reports in `.tasks/` (missing metadata, state mismatch, orphan branch, stale counter), i.e. corruption is recurring, not historical.

## 2. Findings (verified in code)

### 2.1 Four uncoordinated sources of truth

| # | Store | Location | Failure mode |
|---|-------|----------|--------------|
| F1 | ID counter | `.tasks/.task_counter` (+ `.hash`, `.backup`) — `tasks_ai/counter.py:13` | Mutable plain file: stale, manually edited, deleted, or clobbered by `tasks`-branch sync. Every increment does a full git commit into the tasks worktree (`counter.py:45-51`). Recovery is a heuristic scan (`cli.py:1186`). |
| F2 | Task locations | `.tasks/<state>/{id}-{type}-{slug}/` folders | `TaskService.find_task` (`task_service.py:12-74`) prefix-scans folders, then falls back to loading `meta.json` and matching `Id`. When an ID exists in two folders it picks by state-priority heuristic (`task_service.py:53-67`) — a guess, not an authority. |
| F3 | Metadata | `meta.json` inside each folder | Freely editable by humans/agents. Documented root cause of the 178/181 and 4/158 mismatches. `list.py:45-48` already "recovers" IDs from directory names, i.e. the system does not trust its own metadata. |
| F4 | Worktree registry | `.tasks/worktrees.json` — `worktree_manager.py:31-49` | Unconstrained JSON: no uniqueness, no FK to task ID, stores branch/path/task_file redundantly. Stale entries only cleaned lazily by `prune_worktrees` (`worktree_manager.py:162-175`). |

### 2.2 Structural observations

- **F5 — Every command re-derives everything from disk.** `find_task` and `_recover_task_counter_from_tasks` scan all state folders (and `ls-remote` for branches) on every invocation. Even `_migrate_live_to_done` and `_clear_delete_marks` run on every CLI construction (`cli.py:164-167`). This is today's hidden cost, and it is also why nothing enforces invariants globally: no single place computes a complete picture.
- **F6 — The pipeline gate mechanism already exists and works.** `HookRegistry.run_exit_hooks` (`hooks.py:27-32`) runs pre-transition gates inside `move_logic` (`commands/move.py:133`) *before* the physical move (`move.py:167-215`). A hook calling `cli.error()` exits 1 (`cli_io.py:31`) and aborts the transition. Enforcement points exist; they just don't have an integrity checker to call.
- **F7 — Force bypass exists and is used.** `--force` skips exit hooks entirely (`hooks.py:28`) and skips gate validation (`move.py:108,137`). Any enforcement design must keep this escape hatch but make its use loud.
- **F8 — Git hooks are partially wired already.** `install_hooks` (`cli.py:522-553`) installs pre-commit (branch-name regex `^[0-9]+-(task|issue|docs)-[a-zA-Z0-9-]+$`), pre-merge, post-merge, pre-receive. They enforce naming convention and merge discipline but no cross-ref invariants.
- **F9 — `install_hooks` is broken inside task worktrees.** It writes to `os.path.join(self.root, ".git", "hooks")` (`cli.py:523`), but in a linked worktree `.git` is a *file*. Task worktrees (`.task-worktrees/<branch>/`) are where commits actually happen (`worktree_manager.py:96-104`), so hook installation silently no-ops from there today.
- **F10 — Topology is three-tier:** main repo (branches `main`/`testing`/`staging` + one branch per task, worktrees at `.task-worktrees/<branch>/`), `.tasks/` as a **separate clone** on the `tasks` branch (`cli.py:684`), and the remote `tasks` branch as backup (`push_tasks_branch`, `git_service.py:189`).
- **F11 — `refs/heads` is repository-wide, not per-worktree.** `git for-each-ref` from any linked worktree enumerates every task branch; git itself refuses to check out a branch that is already out in another worktree (`worktree_manager.py:100-104` works around this). A uniqueness map built from refs is global by construction.
- **F12 — Context resolution is already worktree-correct.** `ProjectContext._get_main_repo_root` (`context.py:37-42`) uses `git rev-parse --git-common-dir`; the documented workflow runs `hammer tasks move` from inside task worktrees (AGENTS.md), so worktree-safe resolution is proven in production paths.
- **F13 — Dev mode clones the same topology.** Tests (`tests/hammer_test_base.py:24-55`) clone the repo, point `HAMMER_DEV_TASKS_DIR` at a temp dir, and run `hammer tasks --dev init --force`. Guard must work identically in dev and prod, or tests prove nothing.
- **F14 — Tests depend on the counter file.** `.task_counter` is seeded/inspected in `tests/test_tasks.py:52`, `tests/test_init_backup.py:20`, `tests/test_audit_verify_integration.py:65`, `tests/test_robustness.py:1814`.
- **F15 — `repo.py` has a worktree-unsafe root finder.** `find_project_root` (`repo.py:71-80`) walks up looking for a `.git` *directory*; from a task worktree it escapes to the main repo (which happens to be the desired target for guard, by accident). Guard must not inherit this pattern — it should use `ProjectContext`.

### 2.3 Why the earlier approaches failed

- **Sidecar authoritative DB (first proposal):** makes a binary file the source of truth → merge conflicts on the `tasks` branch, backup/restore hazards. Rejected in this session.
- **JSON cache of refs (intermediate proposal):** two maps (local + remote) to reconcile in Python, full-file rewrite per refresh, no indexed query, no safe multi-writer story. Rejected: "JSON is not going to cut it."
- **SQLite cache over git (this plan):** git stays the immutable database; SQLite is a *disposable local index* that can be deleted and rebuilt from one `for-each-ref`. It exists purely to make gate checks fast and cross-map queries indexed.

## 3. Design Principles

1. **Git is the database.** Immutable history, refs as globally-unique names, `tasks` branch as content store. Guard never becomes a source of truth.
2. **The cache is disposable.** `guard.db` must be reconstructible from git alone at any moment. Corrupt → rebuild, never guess.
3. **Rejection beats repair.** Duplicates may still be *created* by accident (races, manual `git branch -f`). They must never *pass a gate*. This inverts the current model: corruption becomes loud and immediate instead of latent.
4. **Deterministic.** Identical git state → identical cache content → identical verdict. No clocks in the query path.
5. **Fast enough to run on every gate.** Budget: ~1 git subprocess + indexed queries in steady state (<50 ms).
6. **Read-only against git and `.tasks`.** Guard's only writes are to its own cache dir.
7. **Loud failure (alpha posture).** Hammer is pre-1.0. A gate that cannot verify — for any reason — halts the transition with an explicit, actionable error. Silence is the failure mode that produced the duplicate-ID corruption in the first place.

## 4. Architecture

### 4.1 Components

```
hammer                          (hammer:32 TOOLS, hammer:39 COMMAND_TO_TOOL)
├── guard.py                    NEW standalone CLI (~150 lines, mirrors repo.py)
└── tasks_ai/
    ├── guard_engine.py         NEW core: cache, RefMap, IntegrityChecker (~250 lines)
    └── pipeline_hooks.py       GuardGateHook (in-process import = fast path)
```

One implementation, two entry points: the pipeline hook imports `guard_engine` directly (no subprocess on the hot path); `guard.py` wraps the same engine for CLI use and git-hook use. Stdlib only (`sqlite3`, `subprocess`, `json`).

### 4.2 Cache location — the common git dir

**`<common_git_dir>/hammer-guard/guard.db`**, resolved via `git rev-parse --git-common-dir` (see F12: `context.py:37-42` already does this correctly). Rationale:

- Inside a linked worktree, `.git` is a file — a naive `.git/hammer-guard/` path crashes or fragments into per-worktree caches with partial views (the bug in the intermediate design).
- One authoritative cache per repository regardless of invocation directory (main repo, task worktree, or CI).
- Inside `.git` it can never be accidentally committed to the `tasks` branch (which would recreate the binary-merge problem that killed the sidecar-DB design) and survives `git clean`.

### 4.3 Schema

```sql
PRAGMA journal_mode=WAL;            -- multi-process safe; busy_timeout=5000 set at connect

CREATE TABLE meta (                -- cache provenance
  k TEXT PRIMARY KEY,
  v TEXT NOT NULL
);                                 -- schema_version, built_from_refs_sha, last_remote_snapshot

CREATE TABLE refs (                -- both ref namespaces, one table
  refname TEXT PRIMARY KEY,        -- '178-task-x' | 'origin/178-task-x' | 'tasks'
  object  TEXT NOT NULL,
  kind    TEXT NOT NULL            -- 'branch' | 'remote' | 'tag' | 'tasks-branch'
);

CREATE TABLE tasks (               -- one row per task; local and remote maps side by side
  task_id       INTEGER NOT NULL,  -- leading digits of folder/branch name
  folder        TEXT NOT NULL,     -- dir basename (also derived from remote path if local absent)
  branch        TEXT,              -- local branch name; NULL for folder-only (archived, branch deleted)
  local_state   TEXT,              -- from .tasks worktree listing; NULL if absent locally
  remote_state  TEXT,              -- from origin/tasks tree;   NULL if absent remotely
  remote_object TEXT,              -- sha of meta.json blob on the tasks branch
  ref_sha       TEXT,              -- object the task's branch points at
  PRIMARY KEY (task_id, folder)
);
CREATE INDEX idx_tasks_branch  ON tasks(branch);
CREATE INDEX idx_tasks_task_id ON tasks(task_id);

CREATE TABLE worktrees (           -- git-truth worktree map (replaces worktrees.json)
  task_id INTEGER NOT NULL,
  branch  TEXT NOT NULL,
  path    TEXT NOT NULL,
  PRIMARY KEY (task_id, path)
);

CREATE TABLE anomalies (           -- last computed report; recomputed on refresh, never trusted
  id      INTEGER PRIMARY KEY AUTOINCREMENT,
  code    TEXT NOT NULL,
  task_id INTEGER,
  detail  TEXT NOT NULL,
  ts      TEXT NOT NULL
);
```

Key shape decision: **one row per task holding both maps.** Local-vs-remote divergence ("remote still has `178-x`, local renamed to `179-x`" — two IDs claimed over the task's lifetime) becomes a single-row field comparison instead of reconciling two JSON documents.

### 4.4 Refresh algorithm — two subprocesses, O(changes)

```
1. git for-each-ref refs/heads refs/remotes refs/tags \
     --format='%(refname:short)%09%(objectname)%09%(objecttype)'
     → upsert refs table (one executemany transaction)

2. git ls-tree -r <tasks-ref> -- '*/meta.json' \
     --format='%(objectname) %(path)'
     → tasks.remote_state / tasks.remote_object
     (path 'backlog/178-task-x/meta.json' ⇒ state=backlog, folder=178-task-x)

3. os.listdir(.tasks/<state>) for 9 state folders
     → tasks.local_state                 (zero subprocesses)

4. git worktree list --porcelain        (only when ref set changed, see step 6)
     → worktrees table

5. SQL diff of refs vs step 1 output  → changed/new/deleted ref set

6. If no refs changed AND tasks-ref object unchanged since meta.built_from_refs_sha:
     skip 2-4 entirely; answer queries from the index (steady state)
```

Steady-state gate cost: **1 subprocess (~10-20 ms for ~250 refs) + a few indexed queries (~1 ms)**. Ref-set-changed adds one `ls-tree` (~10 ms) and, rarely, `worktree list` (~5 ms). Worst realistic gate ~50 ms, against a `move` that today already spawns dozens of git subprocesses in its hooks.

### 4.5 Which tasks-ref does the remote map read?

Prefer `refs/remotes/origin/tasks` if present, else the local `tasks` branch (created by `init` at `cli.py:645-651`). If neither exists, the remote map is empty and `guard check` emits a *warning* (not a rejection) — a missing remote map must not block local work. Guard never fetches; the remote snapshot reflects the last fetch (existing `is_merged` at `git_service.py:108-128` already runs `fetch --all` on some paths, so fetches happen elsewhere in the pipeline already).

## 5. Invariants (what guard enforces)

Checked by `GuardEngine.verdict(task_id, from_state, to_state, branch)`.

**Every finding is REJECT. There is no warning tier.** The guard's sole job is to
assess whether a task is valid and may be worked on by hammer; it never repairs,
renames, or deletes anything (repair belongs to `hammer doctor`). Its answer is
binary, and no config key, dev mode, or per-code exemption can downgrade it.

| Code | Invariant | Check | Severity |
|------|-----------|-------|----------|
| `GUARD_DUPLICATE_ID` | Exactly one local branch claims `task_id` across `refs/heads` | `SELECT branch FROM tasks WHERE task_id=? AND branch IS NOT NULL` | REJECT |
| `GUARD_DUPLICATE_REMOTE_ID` | Same across `refs/remotes/origin` | same, kind='remote' | REJECT |
| `GUARD_BRANCH_NONCONFORMANT` | Branch matches `^[0-9]+-(task\|issue\|docs)-[a-zA-Z0-9-]+$` and the ID matches the transition's task | regex, absorbs the existing pre-commit check (`cli.py:530`) | REJECT |
| `GUARD_BRANCH_MISSING` | Task branch exists locally when `to_state ∈ {TESTING, REVIEW, STAGING, DONE, ARCHIVED}` | refs lookup | REJECT (subsumes part of `WorktreeCheckHook`) |
| `GUARD_BRANCH_NOT_MERGED` | Promotion ancestry: `merge-base --is-ancestor src pipeline-branch` | delegates to existing `git_service.is_merged` (`git_service.py:108`) — guard does not re-implement merge logic | REJECT |
| `GUARD_STATE_DUPLICATE` | No task folder exists in two state folders simultaneously (the 178/181 scenario) | local scan of `.tasks` | REJECT |
| `GUARD_REF_REGRESSED` | Branch tip did not move backward (force-push accident) | reflog of changed refs only | REJECT |
| `GUARD_WORKTREE_ORPHAN` | Live worktree with no matching branch; or two worktrees for one task_id | `git worktree list --porcelain` | REJECT |
| `GUARD_WORKTREE_MISSING` | Worktree absent for an ACTIVE task (`PROGRESSING..STAGING`) | worktrees table | REJECT |

Enforcement rule (fail closed — alpha posture):

- **Integrity violations → REJECT** the transition. The gate is the choke point; a duplicate ID must never progress through the pipeline, regardless of how it was created.
- **"Cannot verify" → REJECT as `GUARD_UNAVAILABLE`.** Engine exception, SQLite corruption, git subprocess failure, lock timeout, or an inexplicable total loss of known refs all halt the transition with an actionable message (see below). Guard does not guess, and it does not wave work through on its own malfunction. Hammer is in alpha: a loud halt is cheaper than a silently corrupted task graph. There is no `fail_open` escape hatch: the emergency remedy is `--force`, which is recorded and surfaced by `guard scan` and `doctor`.
- **Rebuild-before-reject.** Before declaring `GUARD_UNAVAILABLE`, the engine attempts one automatic cache rebuild from git (delete cache, re-derive from the two subprocess calls in §4.4). A corrupt cache is the *expected* disposable-cache failure and must not cost the user a workflow halt; only a rebuild that itself fails (or a deterministic ref-loss) escalates to rejection.
- **Total ref loss is `GUARD_UNAVAILABLE`, not "clean repo."** If a cache that previously held N>0 refs now sees zero refs — branches deleted wholesale, `git gc` accident, wrong repo — refuse to verify rather than interpret the wipe as an empty repository.
- **`--force` remains the deliberate override** (existing hammer behavior: `hooks.py:28` skips exit hooks on force). Under force, GuardGateHook never runs at the exit gate, so the bypass is recorded **after the fact** by the post-transition enter hook (§7.1), which appends to `anomalies` and prints a banner. Forced violations are thus surfaced by `guard scan` and `doctor`, never silent.
- **Remote staleness is a violation, not an excuse** (§4.5): a local task whose branch is gone is a real integrity problem. It blocks like any other finding; `hammer tasks mount <id>` or `doctor --fix` is the remedy. Fresh-cache staleness after N minutes (`guard.staleness_warn_min`) is still printed on every report as an operational note, but it never exempts a verdict.

## 6. CLI surface

```
hammer guard check <task-id> [--from STATE] [--to STATE] [--json]
    # gate verdict; exit 0 = pass, 1 = reject. Used by GuardGateHook-equivalent external callers
hammer guard scan [--all] [--json] [--fix-plan]
    # full anomaly report, read-only; --all includes archived
hammer guard refresh [--fetch]
    # rebuild/refresh cache now (implicit on check when stale)
hammer guard hooks --install | --emit
    # install/emit git-hook wrappers into the COMMON hooks dir
hammer guard rebuild
    # delete cache, rebuild from scratch, report differences (sanity/verification)
```

`check` rejection output example:

```
GUARD REJECT: GUARD_DUPLICATE_ID 178
  refs/heads/178-task-consolidate-repo-merge-and-tas
  refs/heads/178-issue-consolidate-repo-merge-and-tas   (created 2 days ago)
Run 'hammer guard scan' for the full report. Resolve the duplicate, then retry.
```

## 7. Integration points

### 7.1 Pipeline gates (primary)

Register `GuardGateHook` as an exit hook in `cli.py:56-66` alongside existing hooks, for states READY, PROGRESSING, TESTING, REVIEW, STAGING, DONE. It runs in-process inside `move_logic`'s exit-hook phase (`commands/move.py:133`), *before* the physical move, so a rejection leaves the task folder exactly where it was. It derives `task_id`/`branch` from `task.metadata` (`Id`, `Br`) with the `parse_filename` fallback used everywhere else.

A second, lighter **enter hook** on the target state confirms the post-transition expectation (e.g. branch pushed by the time TESTING is reached) — catches "transition claimed but git state didn't follow." Enter hooks run regardless of `--force` (`hooks.py:24-26` has no force check), so this hook doubles as the **forced-bypass recorder**: after a forced transition past a violation it appends to `anomalies` and prints a banner naming the bypassed invariant. It does *not* reject — the forced move already completed, and the record (not a second halt) is what `guard scan` and `doctor` surface.

Cleanup opportunity while integrating: `WorktreeCheckHook`'s push-state check (`pipeline_hooks.py:166-169`) and `WorktreeExistsHook`'s branch check (`pipeline_hooks.py:549-554`) overlap `GUARD_BRANCH_MISSING`/`GUARD_BRANCH_NOT_PUSHED`. Guard absorbs them so `move.py`'s hook list gets *shorter*, not longer.

### 7.2 Git hooks

`hammer guard hooks --install` writes pre-commit/pre-push wrappers into the common hooks dir via `git rev-parse --git-path hooks` (fixes F9). Wrapper body: `hammer guard check --branch "$(git rev-parse --abbrev-ref HEAD)" || exit 1`. This catches duplicates at commit time — before the pipeline is involved — and works in every worktree because hooks are shared. This also fixes the latent bug where `install_hooks` from a worktree writes to a nonexistent `.git/hooks` path (F9).

### 7.3 Repo promotions

`hammer repo merge/sync` (`repo.py:27` `PIPELINE = ["testing","staging","main"]`) calls `guard check --branch <src>` before merging into pipeline branches: last defense before `main`. Implemented as a subprocess call to the guard CLI from `repo.py` (mirrors how `cli.py:392` `_run_repo` already shells out to `repo.py`).

### 7.4 Doctor as the repair counterpart

`hammer tasks doctor` (`commands/doctor.py`) gains a mode that reads guard's `anomalies` table and auto-repairs: duplicate-ID resolution (quarantine the loser to `.tasks/quarantine/<ts>/`, never silent delete), `meta.json` `Br`/`Id`/`St` fixes (existing logic, now driven by guard's list instead of its own ad-hoc scan), stale-counter fix. Guard prevents; doctor repairs. This keeps the F4-style heuristics in one place (doctor) instead of smeared across `list.py` and `find_task`.

## 8. Configuration

New keys in `.tasks/config.yaml` (alongside existing `workflows`/`repo.*` keys, `constants.py:35`):

```yaml
guard:
  enforce: true        # false → all invariants degrade to WARN (kill switch for rollout)
  fail_open: false       # engine failure → GUARD_UNAVAILABLE reject (default); true = emergency warn+allow
  staleness_warn_min: 60   # warn when remote snapshot older than N minutes
```

Read via the existing `load_config` (`constants.py:6-14`).

## 9. Phase 0 — Research & Verification (mandatory before Phase 1 code)

Phase 0 exists because three load-bearing git behaviors were assumed from documentation but **not yet verified in this repository** (verification commands were blocked in the environment where this plan was written). Each item has a concrete verification method; record results in this file's Phase 0 log.

| # | Question | Verification method | Blocks |
|---|----------|---------------------|--------|
| R1 | `git for-each-ref refs/heads` run from inside a task worktree lists **all** task branches (refs are common-dir-wide) | `git -C .task-worktrees/241-issue-fast-track-gate-bypass-on-unco for-each-ref refs/heads --format='%(refname:short)'` vs same from main root | Cache design (§4.2), G1/G2 |
| R2 | `git worktree list --porcelain` from inside a worktree lists **all** worktrees | same pattern with `worktree list --porcelain` | G8 |
| R3 | `git rev-parse --git-path hooks` from inside a worktree resolves to the **common** hooks dir (hooks shared) | `git -C .task-worktrees/... rev-parse --git-path hooks`; compare with `<main>/.git/hooks` | §7.2, F9 fix |
| R4 | `ls-tree` path glob works: `git ls-tree -r <tasks-ref> -- '*/meta.json'` filters server-side and covers the real layout | Run against `.tasks`'s branch; check output covers `backlog/178-task-x/meta.json` style paths only; measure line count vs unscoped `-r` | Remote map (§4.4 step 2); fallback is unscoped `-r` + Python filter |
| R5 | Task layout is uniformly `<state>/<id>-<type>-<slug>/meta.json` on the tasks branch (spot-check 20 folders across states for exceptions: single-file `.md` tasks, missing `meta.json`) | sample the `ls-tree` output from R4 + `.tasks` listing | task_id extraction rule (§4.4 step 3) |
| R6 | Does the main repo have a local `tasks` branch (and/or `origin/tasks` tracking ref)? Which should guard prefer when both exist? | `git branch --list tasks`, `git branch -r` | §4.5 |
| R7 | Should `create` mint IDs through guard's cached map (pre-flight uniqueness + high-water sanity) instead of / in addition to `.task_counter`? | Decide: keep counter file as backend backstopped by guard (Phase 2), vs. `git branch`-atomic allocation + guard rejection (later phase) | Scope boundary of Phase 2; affects F1's fate |
| R8 | Guard in dev mode: do dev fixtures have branches/worktrees (so G4/G8 can run), or must G4/G8 degrade to WARN when `cli.dev`? | Inspect a `--dev` fixture: does `create` call `create_task_worktree` in dev? (`commands/create.py:180` — verify path, some hooks skip on dev: `pipeline_hooks.py:149,350`) | Test design (§11); dev behavior |
| R9 | refname charset safety for the `%09`-separated `for-each-ref` format (refnames containing tabs/newlines) | branch names are constrained to `[a-zA-Z0-9-]` by the pre-commit regex (F8) — confirm no legacy branch violates it: `git for-each-ref refs/heads --format='%(refname:short)'` scan | Parser correctness |
| R10 | Full inventory of call sites that must change | grep for `.task_counter`, `worktrees.json`, `_get_next_id`, `find_task`, `install_hooks` across `tasks_ai/`, `repo.py`, root scripts, `tests/` | Phase task list (§12) |
| R11 | Is `tasks_ai/cli_engine.py` truly dead code (duplicate `TasksCLI`)? | verify no imports of it anywhere before deleting in Phase 4 | Phase 4 scope |
| R12 | Decide exit-code/JSON contract for `guard check` used by git hooks vs pipeline hook (hook needs machine-readable reason for `cli.error` message registry) | draft `messages.py` entries `GUARD_*` with hints, mirroring existing codes; include `GUARD_UNAVAILABLE` with action hint (run `guard rebuild`, then retry; `--force` overrides and logs) | Phase 2 message registry |

**Phase 0 exit criteria:** R1-R6 answered empirically with recorded outputs; R7-R12 decided and recorded in this file. No production code written in Phase 0 beyond scaffolding, if any.

## 10. Implementation Phases

### Phase 1 — Engine + cache + read-only CLI (no behavior change)

- New `tasks_ai/guard_engine.py`: connection management (`guard.db`, WAL, `busy_timeout=5000`), `ensure_schema()`, refresh (§4.4), `verdict()`, anomaly computation into the `anomalies` table.
- New `guard.py` CLI: `scan`, `refresh`, `rebuild` only. Engine imported in-process; `guard.py` is a thin argparse wrapper + colored/text + `--json` output.
- `hammer` dispatcher: add `guard` to `TOOLS` (`hammer:32`) and its commands to `COMMAND_TO_TOOL` (`hammer:39-79`).
- Cache dir creation on first use; `meta.built_from_refs_sha` bookkeeping.
- Unit tests (`tests/test_guard_engine.py`) using fixture repos per §11.

**Acceptance:** `hammer guard scan` reports the current repo's anomalies (expected today: pre-existing duplicates from `local_branches.txt`/history, if any, plus drift) without mutating anything; `rebuild` produces byte-identical `anomalies` output twice in a row (determinism); `scan` on a repo with a seeded duplicate ID reports exactly one `GUARD_DUPLICATE_ID`.

### Phase 2 — Pipeline gate enforcement

- `GuardGateHook` in `pipeline_hooks.py` + registration in `cli.py:56-66` (exit hooks on READY/PROGRESSING/TESTING/REVIEW/STAGING/DONE; enter hook on target).
- Invariants G1-G5 active; `messages.py` entries `GUARD_*` with hints; `--force` bypass with anomaly logged.
- Absorb overlapping checks: `WorktreeCheckHook` push-state and `WorktreeExistsHook` branch checks trimmed to what guard now owns (net hook count in `move.py` decreases).
- Dev-mode behavior per R8.

**Acceptance:** seeded repo with two branches sharing an ID → every `move <id> <state>` exits 1 with the rejection reason and the task folder has **not** moved (assert on disk); clean repo → all pipeline transitions still pass end-to-end (existing suite green); guard adds <100 ms to a transition (loose timing assertion).

### Phase 3 — Git hooks, repo promotion gate, worktree mapping

- `hammer guard hooks --install/--emit` writing to `git rev-parse --git-path hooks` (fixes F9); wire into `install_hooks` (`cli.py:522`) so `init` installs correctly from any worktree.
- `repo.py` promotion gates call guard before pipeline merges.
- Worktree map populated (`git worktree list --porcelain`, R2) and G8 active; `worktrees.json` write path switched off in favor of the table (JSON stays readable as an export for one release, then removed).
- Remote-map staleness warning (§4.5).

**Acceptance:** commit on a duplicate-ID branch in a task worktree is blocked by the pre-commit wrapper; `hammer repo sync` refuses to promote a branch whose ID is duplicated; worktree map matches `git worktree list` exactly; G8 flags a planted orphan worktree.

### Phase 4 — Legacy retirement (only after Phases 1-3 bake)

- Decide fate of `.task_counter` (+ `.hash`/`.backup`) and `tasks_ai/counter.py` based on R7: either deleted (allocation via guard-validated path) or retained strictly as a *hint* with guard as the enforced authority. Update the four tests that seed it (F14) accordingly.
- Delete `worktrees.json` writing entirely; `worktree_manager.py` reads the DB table (keep method signatures to minimize blast radius).
- Delete `_recover_task_counter_from_tasks` / `_verify_counter_hash` / `_write_counter_hash` (`cli.py:1165-1184`) if the counter file is retired; `doctor.py:272` stale-counter block likewise.
- Remove `list.py:45-48` ID-recovery heuristic once G1/G2 make it unreachable.
- If R11 confirms: delete dead `tasks_ai/cli_engine.py`.

**Acceptance:** `grep -r task_counter tasks_ai/ tests/` yields only intentional references; full suite + `./hammer check all` green; a fresh clone of the repo (no cache) rebuilds guard state from git in one command and agrees with the pre-clone verdicts.

## 11. Test Plan

New `tests/test_guard.py` (extends `tests/hammer_test_base.py` infra: clones repo, temp dev tasks dir, `hammer tasks --dev init --force`, `run_tasks()` helper at `hammer_test_base.py:62`):

1. **Uniqueness (core bug):** two branches `178-task-x`, `178-issue-y` in the fixture → guard rejects at every gate; `scan` reports exactly one `GUARD_DUPLICATE_ID` naming both refs.
2. **Gate rejection preserves state:** `move <dup-id> TESTING` exits 1 and the task folder is still in its pre-move location (assert `os.path.exists`).
3. **The original bug scenario:** fixtures replicating `TASK_ID_MISMATCH_BUG_REPORT.md` (same folder in `backlog` + `progressing`, meta `Id` disagreeing with folder) → `GUARD_STATE_DUPLICATE` fires; doctor repair quarantines the loser deterministically.
4. **Determinism:** same refs → `rebuild` twice → identical anomaly output; adding a branch changes verdict in exactly one way.
5. **Cache corruption:** truncate/corrupt `guard.db` → next command auto-rebuilds and produces the correct verdict (self-healing, per §5).
6. **Unavailable-cache rejection:** corrupt cache *and* an unwritable cache dir (rebuild fails) → gate rejects with `GUARD_UNAVAILABLE`, task folder unchanged, message names `guard rebuild` + `--force`.
7. **Total ref loss:** cache previously held N>0 refs, live `for-each-ref` returns zero → `GUARD_UNAVAILABLE`, never interpreted as an empty repo.
8. **Worktree behavior (R1/R2):** `guard check` run with cwd inside a task worktree returns the same verdict as from the main root (cache shared via common dir). Two worktrees for one task planted → `GUARD_WORKTREE_ORPHAN`/duplicate-worktree detection. Run one guard invocation from each of two worktrees concurrently → WAL serializes, both succeed.
9. **Force escape hatch:** `move --force` past a violation succeeds, prints the bypass banner, and the event appears in `anomalies` (visible to `scan`/`doctor`).
10. **Remote divergence:** delete a local branch while `origin/<branch>` still exists → remote-map fields disagree → reported as `GUARD_DUPLICATE_REMOTE_ID` or divergence detail, never silently.
11. **Performance guard:** end-to-end `move` with guard enabled stays within a loose wall-clock budget (e.g. <2s total, guard portion asserted via a unit-level timer <100 ms).
12. **Happy path:** clean fixture repo passes the full BACKLOG→...→ARCHIVED chain with guard active at every gate (regression protection for existing suite: `tests/test_all_transitions.py` etc.).
13. **Git-hook install (F9):** run `install_hooks` equivalent from inside a worktree → hook file exists in the common dir and matches the main-repo install.

## 12. Suggested hammer task breakdown (create via `./hammer tasks create` per AGENTS.md)

1. Phase 0 research: answer R1-R12, append results to this file (type: task).
2. `guard_engine.py` schema + refresh + rebuild (Phase 1).
3. `guard.py` CLI (`scan`/`refresh`/`rebuild`) + `hammer` dispatcher wiring (Phase 1).
4. `tests/test_guard.py` core fixtures + uniqueness tests (Phase 1-2).
5. `GuardGateHook` + registration + `GUARD_*` messages incl. `GUARD_UNAVAILABLE` (Phase 2).
6. Overlapping-hook cleanup in `pipeline_hooks.py`/`move.py` (Phase 2).
7. Git-hook install fix + `guard hooks` command (Phase 3).
8. `repo.py` promotion gate (Phase 3).
9. Worktree map + G8 + `worktrees.json` retirement (Phase 3).
10. Doctor integration (reads `anomalies`, quarantine repairs) (Phase 3).
11. Counter-file retirement decision + execution per R7 (Phase 4).
12. Dead code cleanup (`cli_engine.py` per R11, counter hash helpers, `list.py` recovery) (Phase 4).

## 13. Rollout & Rollback

**Rollout order:** Phase 1 (invisible, read-only) → Phase 2 with `guard.enforce: false` (violations report instead of halt, so the existing backlog of duplicates surfaces as a triage list rather than a wall) → triage/repair with `doctor` → flip to `enforce: true` on one repo → Phase 3/4. Under `enforce: false`, `GUARD_UNAVAILABLE` also downgrades to a warning — but it is logged either way, so guard's own malfunctions are visible during the report-only phase rather than discovered after the flip. Kill switch is a single config key; no migration is ever required because the cache is disposable.

**Rollback:** delete `<common_git_dir>/hammer-guard/` (or just `guard.db`) — git and `.tasks` are untouched by construction (guard only ever writes to its cache dir). Un-installing means removing the `GuardGateHook` registration lines and the two git-hook wrappers; no data migration in either direction. This is the property the sidecar-DB design lacked.

## 14. Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| R4 `ls-tree` path glob `*/meta.json` doesn't filter as expected on this git version | Medium | Remote map slow or wrong | Phase 0 verifies (R4); fallback to unscoped `ls-tree -r --name-only` + Python filter (+~3 ms); test asserts the parsed path set equals `find .tasks -name meta.json` |
| Task layout not uniform (single-file `.md` tasks, missing `meta.json`) | Medium (history shows both formats: `FM.load` handles `.md` single files, `file_manager.py:27-59`) | task_id extraction misses rows → guard blind to some tasks | R5 samples the layout; parser accepts any folder shape: ID from folder prefix, state from parent dir; `meta.json` not required |
| Guard defects produce false rejections that halt legitimate work | Medium | Workflow wedged on correct transitions | Rebuild-before-reject (§5) makes the *expected* failure (disposable cache corrupt) self-healing; remaining failures reject with an actionable `GUARD_UNAVAILABLE` message naming `guard rebuild` and `--force`; `guard.fail_open`/`guard.enforce` are the deliberate human kill switches; Phase 2 report-only mode means these fire as warnings before ever blocking |
| Cache and git drift (guard.db stale after out-of-band `git branch -f`) | Medium | Guard trusts stale index | Refresh diffs live `for-each-ref` output **every** check (step 5) — the cache can never be stale for refs it already tracks; `rebuild` as drift audit; doctor reads `anomalies` |
| An agent/human deletes `guard.db` or it's lost on clone | High (by design) | Apparent "guard stopped working" | It's disposable: auto-rebuilds from git on next command (same code path as first run); `guard rebuild` command documents the recovery |
| Concurrency: multiple hammer processes (agents, hooks, CI) hit the DB | Medium | Lock contention | WAL + `busy_timeout=5000` + tiny transactions; steady state is read-mostly; `anomalies` rewritten only on refresh |
| Stale remote map causes a false `GUARD_DUPLICATE_REMOTE_ID` | Medium | Wrong rejection | Remote map never rejects on absence (warn), only on positive duplicate evidence; staleness warning with `staleness_warn_min` |
| Hook count grows, slowing `move` | Low | Speed | Design absorbs existing hooks (Phase 2 cleanup); steady-state guard cost <50 ms measured in tests (§11.9) |
| Rename of a branch (doctor's `expected_br` fixes) trips `GUARD_REF_REGRESSED` | Low | Wrong rejection | Reflog regression check only flags *backward* tip moves caused explicitly, and is scoped to refs whose object changed since last refresh |
| Tests that seed `.task_counter` (F14) break during counter retirement | Medium | Red Phase 4 | Update the four test sites in the same phase; keep counter file behavior until R7 decision is executed |

## 15. Explicit Non-Goals (scope boundaries)

- **No new authoritative DB.** SQLite here is a disposable index; git remains the database.
- **No change to task content format.** Folders + `meta.json` + `.md` parts stay exactly as they are.
- **No fetch/network at gate time.** Remote map reflects the object database; fetch stays an explicit pipeline action.
- **No daemon or file watcher.** Every state change flows through gates that trigger guard; out-of-band tampering is `doctor`'s job.
- **No allocation redesign inside Phase 1-3.** ID minting stays in `create.py`/counter for now; R7 decides its fate in Phase 4.
- **No doctor relocation.** Doctor stays a `tasks` subcommand (wired at `tasks.py:159`); guard is the prevention counterpart, doctor remains repair.

## 16. Appendix — Key References

| Concern | Location |
|---------|----------|
| Counter (F1) | `tasks_ai/counter.py:13-52`; `.task_counter` + `.hash` + `.backup` in `.tasks/` |
| Counter recovery heuristics | `tasks_ai/cli.py:1186-1254`; stale check `tasks_ai/commands/doctor.py:272-289` |
| Task lookup heuristics (F2) | `tasks_ai/task_service.py:12-74` |
| ID recovery in list | `tasks_ai/commands/list.py:43-48` |
| Bug history | `TASK_ID_MISMATCH_BUG_REPORT.md`, `TASK_ID_MISMATCH_ROOT_CAUSE.md` |
| Pipeline gate mechanism (F6) | `tasks_ai/hooks.py:10-32`; `tasks_ai/commands/move.py:92-217` |
| Error/exit plumbing | `tasks_ai/cli_io.py:18-31` |
| Git hooks (F8/F9) | `tasks_ai/cli.py:522-553` |
| Worktree registry (F4) | `tasks_ai/worktree_manager.py:31-175` |
| Worktree topology | `.task-worktrees/<branch>/`; `git worktree add` at `worktree_manager.py:96-104` |
| Context resolution (F12) | `tasks_ai/context.py:37-42` |
| `.tasks` clone creation | `tasks_ai/cli.py:684-695` |
| Merge/promotion semantics | `tasks_ai/git_service.py:108-128,189-245,303-385` |
| Tool dispatch | `hammer:32,39-79`; standalone pattern `repo.py` |
| Test harness | `tests/hammer_test_base.py:24-63` |
| Counter-dependent tests (F14) | `tests/test_tasks.py:52`, `tests/test_init_backup.py:20`, `tests/test_audit_verify_integration.py:65`, `tests/test_robustness.py:1814` |
| Suspected dead code | `tasks_ai/cli_engine.py` (verify via R11) |

---

## Phase 0 Log

*(Record R1-R12 results here as they are verified.)*

- **2026-11-01:** Plan written. R1-R3 git-verification commands were blocked in the authoring environment; they remain open. R4-R6 verified-by-reading assumptions noted; empirical confirmation pending.
