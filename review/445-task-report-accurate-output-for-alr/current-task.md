---
Task: 445-task-report-accurate-output-for-alr
---

- Progress: Implemented no-op DONE promotion detection and exact Hammer-voice output. Added focused text/JSON and negative-case tests. Focused suite: 7 passed. Related suites: 35 passed. ./hammer check all: lint, test, typecheck, and format all PASS.
- Findings: The no-op occurs when the task has recorded commits, its branch is already contained in the default branch, and the resolved staging/task source is also contained in the default branch. Merge outcome is now determined by comparing target commits before and after Git merge.
- Mitigations: The approved message is restricted to DONE no-op completions. Real merges, empty task branches, and resolved sources with additional work retain normal output and merge behavior.
