# Pipeline Hooks Audit

## Inventory of Hardcoded Transition Actions

| State/Transition | Timing | Action | Code Location (`move.py`) | Type |
| :--- | :--- | :--- | :--- | :--- |
| Any | Pre-Move | Pipeline Gate Validation | `move_logic` (start) | Enter |
| Any | Pre-Move | Git Merge (`git_merge_transition`) | `move_logic` | Enter |
| Any | Pre-Move | Archived Branch Integrity Check | `move_logic` | Enter |
| TESTING -> REVIEW | Pre-Move | Validate Tests Passed | `move_logic` | Enter |
| TESTING -> REVIEW | Pre-Move | Run Validation & Tests | `move_logic` | Enter |
| TESTING/PROGRESSING | Pre-Move | Run Validation & Tests | `move_logic` | Enter |
| TESTING -> (Any) | Pre-Move | Run Validation | `move_logic` | Enter |
| PROGRESSING -> TESTING | Pre-Move | Run Validation | `move_logic` | Enter |
| BACKLOG -> (Any) | Pre-Move | Content Sufficiency Check | `move_logic` | Enter |
| (Any) -> PROGRESSING | Pre-Move | Blocker Check | `move_logic` | Enter |
| (Any) -> PROGRESSING | Pre-Move | Content Sufficiency Check | `move_logic` | Enter |
| (Any) -> PROGRESSING | Pre-Move | Branch Integrity Check | `move_logic` | Enter |
| (Any) -> REVIEW/STAGING/DONE/ARCHIVED| Pre-Move | Origin Pushed Check | `move_logic` | Enter |
| **Move Executed** | **Execution** | `perform_move` | `move_logic` | - |
| (Any) -> TESTING | Post-Move | Git Promotion (`cmd_promote`) | `move_logic` | Exit |
| (Any) -> ARCHIVED | Post-Move | Commit + Push | `move_logic` | Exit |
| (Any) -> (Not ARCHIVED)| Post-Move | Commit | `move_logic` | Exit |
| (Any) -> PROGRESSING | Post-Move | Create `current-task.md` | `move_logic` | Exit |
| (Any) -> REVIEW | Post-Move | Generate Review Diff | `move_logic` | Exit |
