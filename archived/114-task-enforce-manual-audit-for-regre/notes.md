


- Progress: Initiated research into `repo.py` promotion logic and `Rc` flag validation.
- Findings: `repo.py` validates `Rc` during `cmd_promote` when in `REVIEW` state.
- Mitigations: Implementing an Agent-based audit protocol where `audit.json` must exist and match `diff.patch` hash before `Rc` flag is considered valid.
- Plan:
  1. Research `repo.py` promotion logic.
  2. Implement 'audit' agent that reads `.tasks/review/<task_id>/diff.patch' and generates `audit.json` with diff hash and summary.
  3. Update `repo.py` promotion logic to require `audit.json` presence and valid hash.
  4. Restrict `tasks modify --regression-check` if `audit.json` is missing.