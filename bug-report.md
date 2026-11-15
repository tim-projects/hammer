# hammer Bug Report

## Summary

Task creation with required flags (`--story`, `--tech`, `--criteria`, `--plan`, `--repro`) fails to persist content to the task file. The task directory is created with only a minimal `meta.json` containing only `{"Id": 36}`, causing the task to be stuck in BACKLOG despite having provided all required fields.

## Reproduction Steps

1. Run `hammer create "Investigate Google login CSP errors" --type issue --story "..." --tech "..." --repro "..." --criteria "..." --plan "..."`
2. Verify the command reports success: `Created: [36] issue | Investigate Google login CSP errors`
3. Run `hammer move 36-issue-investigate-google-login-csp-e PROGRESSING`
4. Observe error: `Task lacks required content to leave BACKLOG. Missing or incomplete: story, tech, criteria, plan, repro`
5. List contents of `.tasks/backlog/36-issue-investigate-google-login-csp-e/`: only `meta.json` exists

## Expected Behavior

Task should move to PROGRESSING state since all required fields were provided during creation.

## Actual Behavior

Task creation reports success but content is not persisted. Task remains stuck in BACKLOG.

## Workaround

Manually create the required markdown files in the task directory:

- `story.md`
- `tech.md`
- `criteria.md`
- `plan.md`
- `repro.md`

After manually creating these files, `hammer move` works correctly.

## Environment

- hammer version: unknown (current)
- Git-backed task lifecycle manager
