Update the Hammer CLI workflow guidance for expected review prerequisites. This task is blocked by tasks 390 and 392 and must build on their completed behavior.

Dependency contracts:

- Task 392 already provides audit-driven stale-patch self-healing. `tasks audit <id>` compares the patch set with the branch tip, regenerates the complete changed-file set when stale, and does not require a REVIEW state round-trip. The existing `patches_are_fresh` helper and full patch-set replacement in `tasks_ai/audit.py` are the baseline.
- Task 390 must complete the stronger contract before this task proceeds: every REVIEW entry regenerates every patch to the then-current branch HEAD, obsolete patch files are pruned, stale review receipts cannot satisfy the gate, and patch refresh is discoverable without manual deletion.

Current behavior:
- `data/errors.json` renders `PROOF_MISSING` as `Verification proof missing.`
- `data/hints.json` hardcodes `/home/vscode/git/tasks-ai/.tasks/progressing/{task_id}/criteria.md`, even when the task is in REVIEW and `{task_id}` is only the numeric ID.
- `tasks_ai/cli.py` renders every registered failure through `cli.error()`, producing `Error:`.
- `tasks_ai/commands/modify.py` converts `PipelineError(PROOF_MISSING)` directly into `cli.error()`.
- `AGENTS.md` requires agents to stop on any Hammer error, so an expected workflow prerequisite incorrectly halts automation.

Implement an `action_required` output path for expected prerequisites. It must not weaken the gate: the command must still return a non-zero status and must not set `Rc` or permit promotion. Distinguish the result with JSON `status: action_required` and terminal text beginning with a clear `NEXT STEP` marker. Keep actual failures such as audit mismatch, integrity mismatch, and validation failure as normal errors.

For `PROOF_MISSING`, pass the real task context from `tasks_ai/pipeline.py` instead of constructing a hardcoded path. Include the actual `.tasks/review/<task-folder>/patches/` directory, proof path, and task ID. Reuse the freshness/refresh behavior delivered by 390 and 392 rather than implementing a second patch generator.

After 390 and 392, the `PROOF_MISSING` guidance must require this sequence:
1. Refresh the patch set to the current branch tip with `./hammer tasks audit <id>`. This reuses task 392's audit self-healing and task 390's fresh-patch guarantees.
2. Display every refreshed patch with `cat` and capture `sha256sum` evidence.
3. Record the review with `./hammer tasks modify <id> --reviewed` when not already recorded. Task 390 must invalidate this receipt if the patch set changes again.
4. Bind the proof with `./hammer tasks verify <id> --proof "<review evidence including patch filenames and checksums>"`.
5. Pass the gate with `./hammer tasks modify <id> --regression-check`.

Render the instruction in Hammer voice using WHAT, WHY, HOW, and CONSEQUENCE. Update `AGENTS.md` to distinguish expected `NEXT STEP` / JSON `status: action_required` output from actual errors while retaining the stop rule for genuine failures.

Add focused tests for the action-required JSON schema, terminal wording, dynamic patch path, the audit-refresh-first sequence, `cat` and `sha256sum` instructions, unchanged non-zero status, unchanged blocked promotion, and unchanged treatment of genuine integrity failures. Integration coverage must verify that the guidance remains correct when task 392's audit refresh repairs stale patches and when task 390 invalidates a receipt after patch regeneration.
