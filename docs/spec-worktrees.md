# Specification: Git Worktree-Based Task Management

**Status:** Implemented and verified (task 87).
**Audience:** maintainers of the `tasks-ai` / Hammer pipeline tool, contributors writing hooks,
and reviewers of pipeline state-machine changes.
**Scope:** This document exhaustively describes (1) the historical
branch-checkout workflow and (2) the current git-worktree workflow, and (3) a
side-by-side map of every change required to move from (1) to (2). It is the
single source of truth for the worktree model as of commit
`94023dd` ("merge: 87-task-implement-worktree-based-task into main").

---

## Table of contents

1. [Background and terminology](#1-background-and-terminology)
2. [The original workflow: branch-checkout model](#2-the-original-workflow-branch-checkout-model)
3. [The new workflow: worktree model](#3-the-new-workflow-worktree-model)
4. [Side-by-side: original vs. new](#4-side-by-side-original-vs-new)
5. [The WorktreeManager API contract](#5-the-worktreemanager-api-contract)
6. [Mapping of pipeline hooks](#6-mapping-of-pipeline-hooks)
7. [User commands](#7-user-commands)
8. [Validation, linting, and security considerations](#8-validation-linting-and-security-considerations)
9. [Testing strategy](#9-testing-strategy)
10. [Known limitations and open items](#10-known-limitations-and-open-items)

---

## 1. Background and terminology

`tasks-ai` (the `hammer` CLI) is a pipeline state machine over git tasks. Each
task is a markdown record tracked under the `.tasks/` directory and lives in its
own state folder:

```
.tasks/
  backlog/        task-1-foo/
  ready/          task-2-bar/
  progressing/    ...
  testing/
  review/
  staging/
  done/
  archived/
```

`STATE_FOLDERS` is defined in `tasks_ai/constants.py` and maps the canonical
`PIPELINE_STAGES` to lowercase folder names. A task file is loaded by the
`FM` (file manager) class in `tasks_ai/file_manager.py`; its metadata
(`Id`, `Ti`, `St`, `Br`, …) lives in `meta.json` alongside the markdown parts
(`story.md`, `tech.md`, `criteria.md`, `plan.md`).

The pipeline is defined in `tasks_ai/pipeline.py` (`PipelineService`) and is
driven by an ordered registry of hooks in `tasks_ai/pipeline_hooks.py`.
`PipelineHook.execute(cli, task, current_state, new_status, filepath)` is the
extension point. Hooks are registered in `tasks_ai/cli.py` on the
`TasksCLI` instance.

### Key git concepts used here

* A **worktree** is an additional working directory attached to the *same*
  repository object database. `git worktree add <path> <branch>` checks out
  `<branch>` into `<path>`. The repository’s main working tree is unaffected.
  See `git-worktree(1)`. Critically:
  * All worktrees share `.git` object storage — **no duplicated commits**.
  * A worktree is identified by its path and the branch it has checked out.
  * `git worktree list` enumerates every worktree; `git worktree remove`
    detaches one (use `--force` if it has uncommitted changes).
  * `git rev-parse --show-toplevel` resolves to the worktree root you are
    currently inside, **not** the repository root that owns the worktrees.
  This last point is the entire reason the worktree workflow redefines
  `cli.root` vs. `cli.context.main_repo_root` (see §6).
* The **`.task-worktrees/`** directory (relative to the *main* repository root)
  holds every task worktree: `.task-worktrees/<branch>`.
* The **`.tasks/`** directory is itself a checkout of the dedicated `tasks` git
  branch (see `TASKS_BRANCH` in `tasks_ai/constants.py`). It is managed
  separately from task worktrees and contains `.tasks/config.yaml`,
  `.tasks/worktrees.json`, and the per-task state folders.

### Canonical pipeline

States (in order): `BACKLOG → READY → PROGRESSING → TESTING → REVIEW →
STAGING → DONE → ARCHIVED` (with `REJECTED`/`BLOCKED`/`EPIC` off-ramps).
`DEFAULT_ALLOWED_TRANSITIONS` in `tasks_ai/constants.py` is the source of
truth for which moves are legal; `PipelineService.check_transition`
(`tasks_ai/pipeline.py`) rejects anything not listed there.

---

## 2. The original workflow: branch-checkout model

> The legacy model is retained **conceptually** for comparison; its code was
> replaced by the worktree model in `7376cfe`. The behavior below is reconstructed
> from the git history (`7376cfe~1`) and `tests/test_robustness.py` patterns that
> still exercise `git checkout -b` manually.

### 2.1 How a task claimed a branch

Every task file is named `<id>-<slug>` (e.g. `87-task-implement-worktree-base`).
The branch was **named after the task file** and was created on demand with a
plain checkout. There was no central registry: a branch existed iff a developer
had run the move that created it.

### 2.2 The four legacy branch hooks

Registered in `TasksCLI` at `7376cfe~1:tasks_ai/cli.py` (and the pre-refactor
`pipeline_hooks.py`):

| Hook (legacy) | Trigger | Effect |
|---|---|---|
| `BranchSyncHook` | exit → `PROGRESSING` | `git checkout <branch>`; fetch `main`; merge `main` (or `origin/main`) into the branch. Abort with `MERGE_CONFLICT` on failure. |
| `BranchExistsHook` | enter `TESTING`/`REVIEW`/`STAGING`/`DONE`/`ARCHIVED` | Verify `git rev-parse --verify <branch>` succeeds. If the branch is missing, auto-demote to `PROGRESSING` and raise `BRANCH_MISSING_AUTO_DEMOTED`. |
| `BranchSyncOnExitTestingHook` | exit `TESTING` (→ anything but `TESTING`) | Count `git rev-list main..branch`; if >0, merge `main` into the branch (capture missing commits). |
| `BranchCheckHook` | enter `PROGRESSING` (restoration) and enter `REVIEW`/`STAGING`/`DONE`/`ARCHIVED` | On `PROGRESSING`: if the branch is not local but exists on `origin`, `git checkout -b <branch> origin/<branch>`. On the completion states: if `origin` exists and the branch is not pushed (`ls-remote` empty), raise `BRANCH_NOT_PUSHED`. |
| `MainBranchProtectionHook` | any protected transition | Hard reject: if the **current** branch == default branch, error `MAIN_BRANCH_PROTECTION`. (No nuance — any work on `main` was blocked.) |

### 2.3 How the original model failed the worktree migration

1. **Hard block on `main`.** `tasks move` is supposed to be runnable from the main
   repository (the pipeline engine manages context). The legacy
   `MainBranchProtectionHook` rejected *any* protected transition from the
   default branch with no escape hatch, so the worktree model could not drive
   moves from `main`. This is the bug fixed in §6.
2. **Branch existence == work existence.** A branch with zero commits beyond
   `main` is indistinguishable from "the branch was never created" yet `git
   rev-parse --verify` succeeds, so `is_merged` reports it as merged (the
   fast-track bug, tracked in task 241).
3. **No isolation.** Working on two tasks meant `git checkout` thrashing on the
   single working tree; `git clean` and stash state leaked between tasks.

### 2.4 Original user workflow

```text
$ hammer tasks create 87-task-implement-worktree-based-task ...
# branch does not exist yet
$ hammer tasks move 87 READY
$ hammer tasks move 87 PROGRESSING   # BranchSyncHook: git checkout -b 87-...
$ vi code.py                          # edits on the branch in the ONLY working tree
$ git add . && git commit -m work
$ hammer tasks move 87 TESTING
$ hammer tasks move 87 REVIEW        # ReviewDiffHook + verify/audit/regression gates
$ hammer tasks move 87 STAGING         # merge 87-... into staging then main via repo
$ hammer repo promote 87-...          # merge branch → main
$ hammer tasks move 87 DONE
$ hammer tasks move 87 ARCHIVED -y    # commit/push .tasks, delete branch
```

The developer manually owned the "checkout branch → work → checkout main →
merge" dance; the tool only validated branch presence and push state.

---

## 3. The new workflow: worktree model

A task’s code now lives in a **dedicated git worktree** under
`<main_repo>/.task-worktrees/<branch>`. Tasks still carry a branch (`Br` in
`meta.json`), but that branch is the worktree’s checked-out branch, not a
context the CLI ever switches the main working tree to.

### 3.1 Worktree lifecycle mapped to pipeline states

| Pipeline transition | Worktree side effect | Responsible code |
|---|---|---|
| `create` (any state) | A worktree is created for the task branch. | `PipelineService` via `create.py` → `WorktreeManager.create_task_worktree` |
| `→ PROGRESSING` | `WorktreeSyncHook`: ensure the worktree is mounted; if not, create it (restore from `origin/<branch>` when a remote exists and the branch is present remotely). | `WorktreeSyncHook` |
| enter `TESTING`/`REVIEW`/`STAGING`/`DONE` | `WorktreeExistsHook`: verify the worktree still exists; if missing, auto-demote to `PROGRESSING` and raise `WORKTREE_MISSING_AUTO_DEMOTED`. | `WorktreeExistsHook` |
| enter `REVIEW`/`STAGING`/`DONE`/`ARCHIVED` | `WorktreeCheckHook`: if a remote exists and the branch is not pushed, raise `BRANCH_NOT_PUSHED`. | `WorktreeCheckHook` |
| exit `TESTING` | `WorktreeSyncOnExitTestingHook`: if the worktree is ahead of the default branch, merge the default branch into the worktree. | `WorktreeSyncOnExitTestingHook` |
| `→ ARCHIVED` | `ArchivedCommitHook`: after confirming the branch is merged into `main`
(`is_merged`), run `git worktree remove <path> --force`, drop the manifest
entry, and push `.tasks` to the `tasks` remote. | `ArchivedCommitHook` |
| `mount <id>` | Create (or re-create) the worktree for a task and print the path. | `tasks_ai/commands/mount.py` |
| reconcile / cleanup | Prune worktrees whose branch no longer exists; optionally remove. | `WorktreeManager.prune_worktrees`; `commands/cleanup.py` |

### 3.2 Where worktrees live and how they are named

* Base: `<main_repo>/.task-worktrees/`
  (`WorktreeManager.worktrees_base`). This path is **gitignored** (see §8).
* A worktree path is `<base>/<branch>`, e.g.
  `/home/vscode/git/tasks-ai/.task-worktrees/87-task-implement-worktree-based-task`.
* The worktree is registered in `.tasks/worktrees.json`:

```json
{
  "worktrees": {
    "87": {
      "branch": "87-task-implement-worktree-based-task",
      "path": "/home/vscode/git/tasks-ai/.task-worktrees/87-task-implement-worktree-based-task",
      "task_file": "87-task-implement-worktree-based-task"
    }
  }
}
```

Because `.task-worktrees/` is inside the main repo, every task worktree is a
full working tree backed by the shared object database — no commit duplication,
no per-task clones.

### 3.3 Detecting "are we inside a worktree"

`WorktreeManager.detect_task_in_cwd(cwd)` walks `worktrees.json`, normalises each
registered path, and returns the task id whose worktree is the longest prefix of
`cwd`. `is_in_task_worktree()` wraps that. This is what lets `MainBranchProtectionHook`
distinguish "developer on `main` outside any worktree" from "developer inside a task
worktree".

### 3.4 The new user workflow

```text
$ hammer tasks create 42-task-worktree-spec ...          # a worktree is created for the branch
$ hammer tasks mount 42 && cd $(...)                     # or: tasks mount <id>; it prints the path
$ vi code.py && git add . && git commit -m work          # edits live in the ISOLATED worktree
$ cd <main_repo>
$ hammer tasks move 42 TESTING
$ hammer tasks move 42 REVIEW
$ hammer tasks audit 42 && hammer tasks verify 42 --proof "..." \
    && hammer tasks modify 42 --reviewed \
    && hammer tasks modify 42 --regression-check
$ hammer tasks move 42 STAGING
$ hammer tasks move 42 DONE
$ hammer repo merge 42-task-worktree-spec main -y        # merge through the pipeline (DONE)
$ hammer tasks move 42 ARCHIVED -y                       # worktree is removed here
```

The CLI may be driven from the main repo or from inside the worktree;
`find_task`/`Validation.validate_path` accept both roots (§6).

---

## 4. Side-by-side: original vs. new

| Concern | Original (branch-checkout) | New (worktree) |
|---|---|---|
| Unit of isolation | a named branch on the *single* working tree | a git worktree at `.task-worktrees/<branch>` |
| Switching tasks | `git checkout <branch>` | `cd <worktree>` (or `tasks mount <id>`) |
| Branch creation | `git checkout -b <branch>` inside `BranchSyncHook` | `git worktree add <path> <branch>` via `WorktreeManager` |
| Branch restoration from remote | `BranchCheckHook`: `checkout -b <branch> origin/<branch>` | `WorktreeSyncHook`: `create_task_worktree` (which itself falls back to `add -b`) |
| Missing-branch detection | `BranchExistsHook`: `rev-parse --verify <branch>` | `WorktreeExistsHook`: `WorktreeManager.has_worktree` (path + manifest) |
| Missing-worktree auto-recovery | n/a (only auto-demotes branches) | `WorktreeExistsHook` auto-demotes to `PROGRESSING` with `WORKTREE_MISSING_AUTO_DEMOTED` |
| Exit-TESTING divergence capture | `BranchSyncOnExitTestingHook`: `rev-list main..branch` then merge | `WorktreeSyncOnExitTestingHook`: same merge, run from the worktree path |
| Push verification | `BranchCheckHook`: `ls-remote` empty → `BRANCH_NOT_PUSHED` | `WorktreeCheckHook`: same check, run from `main_repo_root` |
| Archive cleanup | `ArchivedCommitHook`: commit/push `.tasks` only | `ArchivedCommitHook`: commit/push `.tasks` **and** `git worktree remove` after merge confirmation |
| `MainBranchProtectionHook` | reject any protected move while on default branch | allow when the task has its own branch (pipeline manages the worktree); only reject when there is no task branch |
| User entrypoint | manual `git checkout` dance | `tasks mount <id>` |
| Path resolution | `cli.root` only | `cli.root` **and** `cli.context.main_repo_root` (§6 / §8) |
| Where `.tasks` lives | main repo | main repo (worktree-aware `find_task` added) |

---

## 5. The WorktreeManager API contract

`tasks_ai/worktree_manager.py` exposes a thin, intentional surface. Everything
else goes through `GitService` (which lazy-loads it as `cli.git.worktrees`).

### 5.1 Construction / context

`WorktreeManager(context, git_service, logger=None)` — `context` is the
`ProjectContext`. It exposes:
* `main_repo_root` — the owning repository (where `.task-worktrees/` lives).
* `tasks_path` — `<main_repo>/.tasks` (the `tasks` branch checkout).
* `repo_root` — the current working tree (possibly a worktree).
* `is_worktree` — true when `repo_root != main_repo_root`.

### 5.2 Methods

| Method | Returns | Semantics |
|---|---|---|
| `worktrees_base` (property) | `str` | `<main_repo>/.task-worktrees` |
| `manifest_path` (property) | `str` | `<tasks_path>/worktrees.json` |
| `_load_manifest()` | `dict` | `{"worktrees": {}}`; degrades to empty on missing/corrupt JSON |
| `_save_manifest(manifest)` | `None` | atomic via `.tmp` + `os.replace` |
| `get_worktree_path(task_id)` | `str\|None` | manifest path, else `None` |
| `get_worktree_branch(task_id)` | `str\|None` | manifest branch, else `None` |
| `has_worktree(task_id)` | `bool` | manifest entry present **and** path exists on disk |
| `detect_task_in_cwd(cwd=None)` | `str\|None` | task id whose worktree path is the longest prefix of `cwd` |
| `is_in_task_worktree(cwd=None)` | `bool` | `detect_task_in_cwd(...) is not None` |
| `create_task_worktree(task_id, branch=None)` | `str\|None` | `git worktree add <path> <branch>`; if the branch does not exist, falls back to `git worktree add -b <branch> <path>` (the normal case for a new task); records manifest entry; returns `None` on failure. Idempotent for an existing worktree. |
| `list_worktrees()` | `list[dict]` | `git worktree list --porcelain` parsed into `{path, branch, detached}` (worktrees only under `worktrees_base`). |
| `remove_task_worktree(task_id, force=False)` | `bool` | `git worktree remove <path>` (adds `--force` when `force`); erases the manifest entry; returns whether a worktree was removed. Safe to call on a missing task. |
| `prune_worktrees()` | `list[str]` | Remove manifest entries for worktrees whose path no longer exists on disk. |

### 5.3 The `create_task_worktree` two-step

```python
result = self.git.run(
    ["worktree", "add", worktree_path, branch], cwd=self.context.main_repo_root
)
if result.returncode != 0:  # branch doesn't exist yet
    result = self.git.run(
        ["worktree", "add", "-b", branch, worktree_path],
        cwd=self.context.main_repo_root,
    )
```

`git worktree add <path> <branch>` requires `<branch>` to already exist; for a
brand-new task it does not, so the `-b` form creates it. This is why the git log
parser in `GitService._handle_command_logging` must handle *both* argument
orders (fixed in this work — previously it logged `"Added worktree at '-b'`).

---

## 6. Mapping of pipeline hooks

### 6.1 Registration changes in `TasksCLI` (`tasks_ai/cli.py`)

Pre-refactor (branch model) → post-refactor (worktree model):

```diff
- self.hook_registry.register_exit_hook("TESTING", BranchSyncOnExitTestingHook())
+ self.hook_registry.register_exit_hook("TESTING", WorktreeSyncOnExitTestingHook())

  self.hook_registry.register_enter_hook("PROGRESSING", TaskRepairHook())
  self.hook_registry.register_enter_hook("PROGRESSING", ContentSufficiencyHook())
  self.hook_registry.register_enter_hook("PROGRESSING", BlockerCheckHook())
- self.hook_registry.register_enter_hook("PROGRESSING", BranchCheckHook())
- self.hook_registry.register_enter_hook("PROGRESSING", BranchSyncHook())
+ self.hook_registry.register_enter_hook("PROGRESSING", WorktreeCheckHook())
+ self.hook_registry.register_enter_hook("PROGRESSING", WorktreeSyncHook())
- self.hook_registry.register_enter_hook("TESTING", BranchExistsHook())
+ self.hook_registry.register_enter_hook("TESTING", WorktreeExistsHook())
  self.hook_registry.register_enter_hook("TESTING", ValidationPassedMarkHook())
  self.hook_registry.register_enter_hook("REVIEW", ReviewDiffHook())
- self.hook_registry.register_enter_hook("REVIEW", BranchExistsHook())
- self.hook_registry.register_enter_hook("REVIEW", BranchCheckHook())
+ self.hook_registry.register_enter_hook("REVIEW", WorktreeExistsHook())
+ self.hook_registry.register_enter_hook("REVIEW", WorktreeCheckHook())
- self.hook_registry.register_enter_hook("STAGING", BranchCheckHook())
+ self.hook_registry.register_enter_hook("STAGING", WorktreeCheckHook())

  self.hook_registry.register_enter_hook("STAGING", CleanWorkspaceHook())
- self.hook_registry.register_enter_hook("DONE", BranchCheckHook())
- self.hook_registry.register_enter_hook("ARCHIVED", BranchCheckHook())
+ self.hook_registry.register_enter_hook("DONE", WorktreeCheckHook())
+ self.hook_registry.register_enter_hook("ARCHIVED", WorktreeCheckHook())

  self.hook_registry.register_enter_hook("ARCHIVED", ArchivedCommitHook())
```

The four deleted classes (`BranchCheckHook`, `BranchSyncHook`,
`BranchExistsHook`, `BranchSyncOnExitTestingHook`) are replaced one-for-one by
their worktree-named equivalents, preserving the same guard semantics but
operating on the worktree instead of a checked-out branch.

### 6.2 `MainBranchProtectionHook` — the subtle, critical change

Old (legacy): block *any* protected transition (`PROGRESSING|TESTING|REVIEW|
STAGING|DONE`) when the current git branch == default branch. This was correct
in the branch-checkout model (you literally should not commit to `main`), but it
makes the worktree model unusable, because in the worktree model the CLI is
*expected* to be driven from `main`/the main repo while it manages the task
worktree internally.

New:

```python
if current_branch == default_branch:
    task_branch = task.metadata.get("Br", "")
    if not task_branch:  # no task branch -> genuinely on main, block
        cli.error(
            "MAIN_BRANCH_PROTECTION",
            new_status=new_status,
            default_branch=default_branch,
        )
```

Rationale: when the task carries a `Br`, the pipeline engine owns the
worktree/branch context and will route operations through it, so running a move
from `main` is intended. The block fires only when there is no task branch at
all (i.e. a real stray operation on `main`). The "not in a task worktree" case
is demoted to a `WARN` (not a hard error) telling the user to `tasks mount`.

### 6.3 `ArchivedCommitHook` — now removes the worktree

Old behavior committed/pushed `.tasks` on `ARCHIVED`. New behavior:

```python
if new_status == "ARCHIVED":
    cli._run_git(["add", "--all"], cwd=cli.tasks_path)
    cli._run_git(["commit", "-m", f"Archive [{Id}] {Ti}"], cwd=cli.tasks_path)
    try:
        cli._push_tasks_branch("tasks", fatal=False)
    except Exception:
        pass

    branch = task.metadata.get("Br", "")
    default_branch = cli.git.get_default_branch()
    if branch and not cli.git.is_merged(branch, default_branch):
        cli.error("BRANCH_NOT_MERGED", branch=branch)  # never lose work

    if cli.git.worktrees.has_worktree(task_id):
        cli.git.worktrees.remove_task_worktree(task_id, force=True)
        cli.console("worktree", "remove", f"task {task_id}")
    else:
        cli.console("worktree", "skip", f"no worktree for task {task_id}")
```

Invariants enforced:
1. The `.tasks` worktree is committed and pushed (backup of task metadata).
2. The task branch **must** be merged into `main` before the worktree is
   removed — otherwise `BRANCH_NOT_MERGED` and the archive is aborted, so no code
   is ever lost by detaching a worktree.
3. Only after both checks does `git worktree remove --force` run, and the
   manifest entry is deleted (`remove_task_worktree`).

### 6.4 Path resolution fix (`tasks_ai/validation.py`)

This is the change that makes cross-worktree operation actually work:

```python
def validate_path(self, path: str) -> bool:
    abs_path = os.path.abspath(path)
    if is_dev or is_testing or starts_tmp:
        return True
    allowed_roots = [self.cli.root, self.cli.context.main_repo_root]
    if any(abs_path.startswith(os.path.abspath(root)) for root in allowed_roots):
        return True
    self.cli.error(f"Path outside repository: {path}")
    return False
```

`self.cli.root` is `context.repo_root` (the worktree you are in), and
`context.main_repo_root` is the owning repo. Task paths under `.tasks/` always
resolve into the main repo; before this change `find_task` returned
`(None, None)` from inside a worktree, so `tasks show <id>` failed with
`"Path outside repository"`. The same root fix is applied to the
worktree-sync / reconcile logic in `cli.py`, `git_service.py`
(`merge_branches`, `promote_task`, `demote_task`, `is_merged`, `branch_exists`
all accept/forward `cwd` and default to `main_repo_root`), `repo.py`
(`cmd_demote`), and the rewrites in `commands/{cleanup,move,unarchive}.py`.

---

## 7. User commands

| Command | Worktree effect |
|---|---|
| `tasks create ...` | Creates the task **and** its worktree (`create_task_worktree`). The `worktree` path is returned in the JSON result. |
| `tasks mount <id>` | `commands/mount.py`: load the task, create its worktree if absent, print `Run: cd <path>`. |
| `tasks move <id> <STATE>` | Driven by pipeline hooks: `WorktreeSyncHook`/`WorktreeExistsHook`/`WorktreeCheckHook` create/validate/sync the worktree; `ArchivedCommitHook` removes it on `ARCHIVED`. Runs from the main repo or inside the worktree. |
| `tasks audit <id>` | Generates file-level patches from the worktree branch. |
| `tasks verify / modify / reconcile / cleanup` | Operate on `.tasks/` in the main repo; `cleanup`/`reconcile` prune dead worktrees via `WorktreeManager.prune_worktrees`. |
| `repo merge <task-branch> main` | Routes through `tasks move <id> DONE` (gated), which merges the worktree branch into `main`. |

The branch name for a task is still `<id>-<slug>` (the task file), stored in
`meta.json` as `Br`, and the worktree is checked out on exactly that branch.

---

## 8. Validation, linting, and security considerations

### 8.1 `.gitignore`

```gitignore
.task-worktrees/
```

Added because every task worktree is a full working tree under the main repo and
would otherwise appear as untracked noise (and risk being committed) in
`git status`.

### 8.2 Security: trust boundary is unchanged

`validate_path` is the repository-trust boundary. It is intentionally **broader**
in the new model (accepts `main_repo_root`), not narrower: the only new
acceptance is paths already inside the owning repository. No external or
arbitrary path is admitted. `find_task` results are still validated before use
by callers such as `task_service.find_task` (which calls
`cli._validate_path(selected_path)`).

### 8.3 Linting/type-checking posture

`npx pyright tasks_ai/` reports **0 errors**. `ruff check tasks_ai/ tests/` reports
**11 pre-existing errors** (all present at `HEAD b944cf4`, only line numbers shifted by
this work) — these are tracked in task **243** and are **out of scope** for the
worktree change. No new lint errors were introduced.

### 8.4 The dev-mode escape hatch and its test implication

`validate_path` (and several hooks) short-circuit under `--dev` (`cli.dev`) or
when `TASKS_TESTING=1` or the path starts with `/tmp`. This means:
* The existing `HammerTestBase`-based tests (which always set `--dev`) **cannot**
  exercise the production `validate_path` path.
* Tests run under `tests/test_robustness.py` use a temp repo under `/tmp`, so they
  also short-circuit `validate_path`.
* Therefore a regression guarding the path fix **must** place the repo outside
  `/tmp` and run **without** `--dev`. `tests/test_worktree_system.py` does exactly
  this (repo created under `/var/tmp`, no `--dev`); the whole module is skipped
  if no writable non-`/tmp` location is available, rather than silently passing.

---

## 9. Testing strategy

* `tests/test_worktree_system.py` — 4 tests, non-dev, repo under `/var/tmp`.
  Covers: worktree creation + manifest persistence (criteria 1, 2); task ops
  resolving from inside a worktree (criterion 4 — a verified regression test
  that fails without the `validation.py` fix); `tasks mount` round-trip
  (criterion 3); and full lifecycle through `ARCHIVED` with worktree removal
  (criterion 7). Also exercises a `move READY` from inside a worktree (criterion 9).
* `tests/test_tasks.py::test_full_lifecycle` — full pipeline to `ARCHIVED`
  (criterion 8/backward-compat path through moves).
* `tests/test_all_transitions.py`, `tests/test_pairing.py` —
  every legal transition and blocker-linking semantics.
* `tests/test_audit_verify_integration.py` — the 5-gate review/review regression
  flow including `test_staging_blocked_without_regression_check`.
* `tests/test_robustness.py` — 44/48 pass; the 4 failures are pre-existing
  (verified identical at `HEAD` via `git stash`) and tracked in task **245**.

---

## 10. Known limitations and open items

1. **Fast-track gate bypass (task 241).** `PipelineService.validate_gate`
   (`tasks_ai/pipeline.py`) short-circuits for `REVIEW`/`STAGING`/`DONE` when
   `git.is_merged(branch, "main")` is true. `GitService.is_merged`
   (`tasks_ai/git_service.py`) relies on `git merge-base --is-ancestor`, which
   reports a freshly-created worktree branch (zero commits beyond `main`) as
   merged, so the gate is bypassable for a task whose branch has no new commits.
   Verified empirically. Out of scope for the worktree implementation; tracked
   as task 241.
2. **Pre-existing lint (task 243)** and **pre-existing `test_robustness.py`
   failures (task 245)** — see §3 and §8.3.
3. **Worktree base is gitignored, not the individual entries.** Deleting a
   worktree via `git worktree remove` outside the tool leaves a stale manifest
   entry until `prune_worktrees`/`reconcile` run.
4. **`WorktreeManager.prune_worktrees` does not auto-run on every transition**;
   it is invoked by `commands/cleanup.py`. Operators should run
   `tasks cleanup` (or `reconcile`) periodically to reclaim stale paths.
5. **`is_merged` has no remote-free fast correctness.** With no remote it
   falls back to comparing the local branch against local `main`; a branch that
   is an ancestor of `main` (incl. "no new commits") is reported merged. This
   is the engine behind limitation 1.
