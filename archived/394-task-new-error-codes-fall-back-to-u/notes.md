
- Progress: Registry entries added for RESEARCH_REQUIRED, CONTENT_FILE_NOT_FOUND, PARENT_NOT_FOUND (+TASK_METADATA_CORRUPTED hint); dead hint kwarg dropped; regression test added.
- Findings: cli.error(code) only renders data/errors.json + data/hints.json; an inline hint= kwarg reaches format_map and never displays. Submitted block error during 394's own promotion surfaced the bug first-hand.
- Debt: audit scanned single-line cli.error("CODE" patterns only; codes built dynamically (f-strings/vars) are not covered by the new test.
- Blockers: none.