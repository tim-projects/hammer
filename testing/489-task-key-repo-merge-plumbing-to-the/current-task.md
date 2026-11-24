---
Task: 489-task-key-repo-merge-plumbing-to-the
---

- Progress:
  - Switched the `repo.py` shared funnel from `testing -> staging -> default` to `provisioning -> default`.
  - Numeric task merges now use the `<id>-PR` stage ref, merge it into `provisioning`, then move the task to `PROVISIONING` so the stage-ref gate passes.
  - `check-merged` and `check-merged-testing` resolve task IDs and check ancestry from `provisioning`.
  - Missing `provisioning` branches bootstrap from `<remote>/<default>` with a local-default fallback.
  - `repo sync` advances `provisioning` into the default branch.
  - Added `provisioning` to the local and remote deletion guards; retained `testing` and `staging` as protected historical branches.
  - Added focused provisioning-funnel coverage and updated existing pipeline/deletion expectations.
- Findings:
  - Resolving the destination before branch creation blocked the first merge in a fresh repository; pipeline destinations are now resolved before `ensure_pipeline_branch` creates them.
  - `check-merged <id>` needed task-aware branch resolution rather than a literal local-ref lookup.
- Validation:
  - Focused suites: 34 passed.
  - `./hammer check all`: lint PASS, test PASS, typecheck PASS, format PASS.
- Mitigations:
  - Local-only repositories fall back to the local default branch when no remote default ref exists.
