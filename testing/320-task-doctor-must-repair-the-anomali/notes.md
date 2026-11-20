
- Progress:
  - Implemented doctor reporting through GuardEngine so guard codes, task IDs, details, and hints are surfaced from the single source of truth.
  - Kept safe repairs limited to metadata Id/Br/St, task directory/state placement, and stale task counter.
  - Made all structural guard anomalies report-only, including duplicate IDs/folders, branch drift, remote divergence, and worktree anomalies.
  - Removed doctor writes for read-only mode so running doctor no longer creates bug-report files.
  - Repointed GUARD_* hints and guard fix plans away from doctor --fix toward fresh-create/mount workflows.
  - Added user tests for guard reporting, report-only --fix behavior, and read-only doctor behavior; updated superseded worktree repair expectations.
  - Validation: focused tests passed (7 doctor tests, 18 worktree ownership tests, 3 new guard anomaly tests); ./hammer check all passed lint/test/typecheck after formatting correction; ./hammer check format passed.
  - Commit: 834fcd85 Doctor reports structural guard anomalies safely