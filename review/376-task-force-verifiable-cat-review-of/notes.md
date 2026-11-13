# 376 — implemented, verified

## What shipped (this branch)
- tasks_ai/commands/review.py: `tasks review <id> [file]` — exposes ONE patch in full
  (raw in text mode, data.content under -j) and appends a receipt {file, patch, md5,
  sha256, bytes, ts, seq, prev_hash} to reviews.json; commits it via commit_task_paths.
  A bare run opens the next unread patch and reports remaining; re-running after all
  are read reports finalize and keeps the existing summary.
- tasks.py: `review` subparser + dispatch; `--reviewed` now takes the summary as its
  value (nargs="?", const=True) — bare flag + patches => REVIEW_SUMMARY_REQUIRED.
- hammer: "review": "tasks" in COMMAND_TO_TOOL. tasks_ai/cli.py: review() delegation.
- tasks_ai/commands/modify.py: the atime gate is GONE. Finalize requires every
  patch in PatchFiles to carry a current-md5 receipt (REVIEW_INCOMPLETE names the
  unread files) and a >=40 char summary, both stored in reviews.json; empty-diff
  tasks still auto-pass. --regression-check additionally requires the stored summary.
- tasks_ai/pipeline.py: update_audit_hash + check_audit_integrity hash reviews.json
  (criteria, proof, reviews, audit — same order both sides). Binding is live on the
  real path: verify hashes it, --regression-check re-checks before setting Rc.
- tasks_ai/pipeline_hooks.py REVIEW-entry hint rewritten to the per-file then
  summary flow; data/errors.json + data/hints.json gained NO_PATCHES /
  PATCH_NOT_IN_TASK / REVIEW_* codes and a rewritten REGRESSION_CHECK_NOT_PASSED hint.
- docs/spec-worktrees.md §3.4 workflow updated.

## Canonical order (discovered while testing — enforce this)
review each patch -> modify --reviewed "<summary>" -> audit -> verify --proof ->
modify --regression-check. Finalize must precede audit/verify because the audit hash
covers reviews.json; finalizing after verify leaves the hash stale.

## Verification
- tests/test_audit_verify_integration.py: 14 passed (6 new tests: single-patch receipt,
  coverage refusal naming the unread patch, incidental-open rejection, summary
  required/too-short, repeat-run keeps summary, tampered reviews.json -> integrity fail).
- tests/test_tasks.py 7 passed; tests/test_worktree_system.py 4 passed (helpers
  updated to the new flow).
- ruff: zero new findings vs main (19 pre-existing remain, untouched).
- Manual --dev: review outside REVIEW -> REVIEW_STATE_REQUIRED; unknown task handled.

## Debt / notes
- Pre-existing `tasks move BLOCKED` KeyError filed separately as issue 380.
- Post-gate tampering is still out of scope of the existing design (same as
  criteria/proof/audit): Rc==PASSED skips re-verification; binding protects the
  transition into Rc, which is where the gate lives.
