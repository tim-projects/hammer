Inventory completed across the current implementation:

1. Parser-generated stalls
- `tasks_ai/cli_io.py:14-28`: `BlockerArgumentParser` emits `: blocker:` and `HAMMER SAY NO! FIX!` for invalid usage. `check_wrapper.py`, `repo.py`, and `guard.py` import and use this parser.
- `tests/test_usage_blockers.py` asserts the old blocker wording and must be renamed/updated to next-step semantics.

2. Validation/check stalls
- `tasks_ai/validator.py:8-24`: failed checks default to `status: blocker` and render `CHECK <tool>: BLOCKER`.
- `tasks_ai/validator.py:27-47`: Ruff findings render as `BLOCKER <code> ...`; these lint codes are tool finding codes, not Hammer error codes.
- `tasks_ai/validator.py:276-280,319`: failed checks use `status: blocker`.
- `tasks_ai/check_wrapper.py:93-108`: validation exceptions use `status: blocker`.
- `tasks_ai/validation.py:176-207`: validation failures emit `BLOCKER <tool>` messages and use `PIPELINE_VALIDATION_FAILED` as an error-code path.
- `check.py:257-514`: check results use `status: blocker` and print `BLOCKER: ...`.
- `tests/test_validation_blockers.py` and `tests/test_check_worktree.py` pin the old status and wording.

3. Pipeline/workflow prerequisites
- `tasks_ai/cli_io.py:61-79`: the existing `action_required` response already has `status: action_required` and terminal `NEXT STEP:` wording. Replace this status/name with `next_step`; do not keep two competing next-step statuses.
- `tasks_ai/cli.py:251-254`: `CLI.action_required` delegates to the response helper and should become the `next_step` path.
- `tasks_ai/cli.py:355-364`: only `PROOF_MISSING` currently becomes action-required; other gate failures become errors and need classification by whether remediation is a required next step.
- `tasks_ai/pipeline_hooks.py`: existing `action_required` sites for worktree/review/regression prerequisites and `cli.error` sites for prerequisite gates such as missing research, incomplete linked blockers, missing worktrees, missing tests-passed, missing patches, missing proofs, stale audits, and missing summaries should be audited. A dependency relationship may still be called a blocker in task/domain language, but its command output must use next-step semantics when it describes an expected prerequisite.
- `tasks_ai/commands/{audit,review,verify,modify,mount,delete,show,list,create,checkpoint}.py` contain prerequisite errors with actionable hints. Convert only prerequisite/stall responses; retain genuine errors such as corrupt data, invalid paths, missing referenced content, impossible state, and failed operations as errors.

4. Message store and error-code boundary
- `data/errors.json` and `data/hints.json` are keyed by Hammer error codes. A next-step response must not be exposed as an error code. Prefer a separate next-step message store or an explicit action-required registry so genuine error codes remain exclusively associated with genuine errors.
- `tasks_ai/messages.py` currently resolves both error and hint text from the same code.
- `tasks_ai/cli_io.py` currently renders action-required JSON with an `error` field. The next-step JSON schema should use a non-error payload field (for example `next_step` or `message`) and omit `error` entirely.
- Current JSON `error` responses render a human message and do not expose a separate error-code field, contrary to the desired stop-on-error-code boundary. The implementation must expose a stable genuine error code field (for example `error_code`) while preserving the human-readable `error` field.

5. Output vocabulary
- Replace output-facing `blocker` status/wording with `next_step` only where the output describes an actionable stall. Keep `blocker` where it names a task dependency relation or state/domain concept (for example linked blockers and BLOCKED task state).
- Do not rename Ruff finding codes: `F401` and similar are tool diagnostics, not Hammer error codes.

Implementation guidance:
- Introduce one next-step response helper and one genuine error-code envelope rather than duplicating formatting.
- Keep exit non-zero for next-step responses because the gate remains blocked.
- Update `AGENTS.md` to stop only for genuine errors with an error code and to continue for terminal `NEXT STEP:` or JSON `status: next_step`.
- Update all affected tests, fixtures, help text, and documentation in the same change.
