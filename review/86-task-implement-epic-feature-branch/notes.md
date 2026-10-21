
# EPIC/FEATURE BRANCH WORKFLOW - Design Notes

## Problem
We need hierarchical feature branches (epics/parent tasks) where:
- Child tasks merge into the parent branch
- Parent waits in a holding state until all children are merged
- Then continues through normal gates (testing→staging→main)

## Proposed Solution

### New State: EPIC
- Parent task sits in EPIC state while waiting for children
- Blocked from normal gates (can't enter TESTING directly)
- Unblocks when all children merged/rejected

### Parent-Child Linking
- New metadata field: `Pt` (Parent task id)
- When creating child task: `--parent ` flag sets Pt
- Child task knows its parent branch

### Child Task Workflow
1. Child develops in PROGRESSING normally
2. Moves to TESTING → REVIEW 
3. After `--regression-check`, auto-merges to parent branch
4. Then moves to DONE (parent receives actual merge)
5. REJECTED child is auto-removed from parent's requirements

### Parent in EPIC State
- Shows children status in `tasks show ` output
- Auto-detects when all children merged/rejected
- Prompts user to move from EPIC → PROGRESSING

### Key Implementation Points
1. Add EPIC to ALLOWED_TRANSITIONS
2. Add `Pt` to KEY_MAP for parent linking
3. repo.py merge: detect parent branch, merge to parent not testing/staging
4. move command: EPIC blocks TESTING/STAGING/REVIEW transitions
5. Auto-check children merged when in EPIC state
6. Handle child REJECTION to clear parent requirements

### Differences from Normal Pipeline
- Child doesn't use testing/staging branches
- Validation runs locally against parent branch (merge target)
- "Children reviewed" tracked in parent metadata, not branch-based
- Parent can exit EPIC only when all children in DONE/REJECTED states