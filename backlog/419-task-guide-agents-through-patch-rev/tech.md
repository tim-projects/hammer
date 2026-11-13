Update the Hammer CLI workflow guidance for expected review prerequisites.

Current behavior:
- `data/errors.json` renders `PROOF_MISSING` as `Verification proof missing.`
- `data/hints.json` hardcodes `/home/vscode/git/tasks-ai/.tasks/progressing/{task_id}/criteria.md`, even when the task is in REVIEW and `{task_id}` is only the numeric ID.
- `tasks_ai/cli.py` renders every registered failure through `cli.error()`, producing `Error:`.
- `tasks_ai/commands/modify.py` converts `PipelineError(PROOF_MISSING)` directly into `cli.error()`.
- `AGENTS.md` requires agents to stop on any Hammer error, so an expected workflow prerequisite incorrectly halts automation.

Implement an `action_required` output path for expected prerequisites. It must not weaken the gate: the command must still return a non-zero status and must not set `Rc` or permit promotion. Distinguish the result with JSON `status: action_required` and terminal text beginning with a clear `NEXT STEP` marker. Keep actual failures such as audit mismatch, integrity mismatch, and validation failure as normal errors.

For `PROOF_MISSING`, pass the real task context from `tasks_ai/pipeline.py` instead of constructing a hardcoded path. Include the actual `.tasks/review/<task-folder>/patches/` directory, proof path, and task ID.

The `PROOF_MISSING` guidance must require this sequence:
1. Display every patch with `cat` and capture `sha256sum` evidence.
2. Record the review with `hammer tasks modify <id> --reviewed` when not already recorded.
3. Generate the audit with `hammer tasks audit <id>` when needed.
4. Bind the proof with `hammer tasks verify <id> --proof "<review evidence including patch filenames and checksums>"`.
5. Pass the gate with `hammer tasks modify <id> --regression-check`.

Render the instruction in Hammer voice using WHAT, WHY, HOW, and CONSEQUENCE. Update `AGENTS.md` to distinguish expected `NEXT STEP` / JSON `status: action_required` output from actual errors while retaining the stop rule for genuine failures.

Add focused tests for the action-required JSON schema, terminal wording, dynamic patch path, `cat` and `sha256sum` instructions, unchanged non-zero status, unchanged blocked promotion, and unchanged treatment of genuine integrity failures.
