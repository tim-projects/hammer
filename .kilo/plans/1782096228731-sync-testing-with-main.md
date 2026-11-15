# Plan: Sync Testing Branch with Main Branch Architecture

## Problem Summary
The `testing` branch is on an outdated architecture that uses `git_client.py` (200 lines). The `main` branch has a newer architecture with `git_service.py` (338 lines) that includes the REJECTED transition fix. Merging task 305 into testing causes conflicts because testing lacks the file rename and new features.

## Architecture Differences

| Component | Testing (old) | Main (new) |
|-----------|---------------|------------|
| Git service | `git_client.py` (200 lines) | `git_service.py` (338 lines, renamed) |
| Validation | `validation.py` only | `validation.py` + `validator.py` (new) |
| Pipeline | `pipeline.py` + `pipeline_hooks.py` | Refactored versions |
| Libs | None | `libs/file_utils.py`, `libs/list_layout.py`, `libs/path_utils.py` |

## Key Changes in Main (since testing diverged)

1. **git_service.py** - Renamed from `git_client.py`, added:
   - `merge_branches()` method for robust branch merging
   - `promote_task()` method for pipeline promotions
   - `demote_task()` method with branch existence check (the 305 fix)
   - `sync_pipeline()` method

2. **validator.py** - New file with:
   - Timeout support for long-running tools
   - `/bin/true` utility for validation bypass
   - Nested config handling

3. **check.py** - New 557-line validation orchestrator

## Action Plan

### Phase 1: Prepare Testing Branch
1. Stash any uncommitted changes on testing
2. Create backup of current testing state

### Phase 2: Merge Main into Testing
1. Run `git checkout testing && git merge main`
2. Resolve merge conflicts in these key files:
   - `tasks_ai/git_client.py` → Will become `tasks_ai/git_service.py`
   - `tasks_ai/pipeline.py`
   - `tasks_ai/pipeline_hooks.py`
   - `tasks_ai/validation.py`
   - `tasks_ai/cli.py`
   - `tasks_ai/commands/move.py`

### Phase 3: Conflict Resolution Strategy
For each conflicted file:
1. Read both versions side-by-side
2. Ensure all functions from both branches are preserved
3. Keep testing-specific features, add main-specific improvements
4. Verify Python syntax and type hints pass

### Phase 4: Verification
1. Run `./hammer check all` to validate code quality
2. Run unit tests: `pytest tests/`
3. Test the REJECTED transition with missing branch case
4. Test all pipeline transitions (BACKLOG→READY→PROGRESSING→TESTING→REVIEW→STAGING→DONE)

### Phase 5: Complete Task 305
1. Once testing is updated, retry `./hammer tasks -j move 305 TESTING`
2. The merge should succeed without conflicts
3. Then move to REVIEW and complete the original task

## Risk Assessment

**High Risk:**
- `git_client.py` → `git_service.py` rename creates significant conflict
- Multiple architecture changes across 39 files
- Testing may have features not in main that could be lost

**Mitigation:**
- Review each conflict carefully
- Test all transitions after merge
- Keep stash backup for rollback

## Validation Commands
```bash
# After merge
./hammer check lint --fix
./hammer check typecheck  
./hammer check test
# Test REJECTED transition
./hammer tasks -j move <id> REJECTED
```