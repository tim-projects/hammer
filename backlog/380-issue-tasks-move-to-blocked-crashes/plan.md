1. Reproduce: move a dev task to BLOCKED from PROGRESSING and from TESTING
2. Trace the KeyError to the failing lookup (STATE_FOLDERS vs allowed transitions)
3. Fix the root cause in shared move logic
4. Add tests for BLOCKED transitions and recovery