1. Investigate hammer script and tasks.py init command implementation
2. Add pre-flight check for existing .tasks directory with tasks
3. Print error message and exit if .tasks exists and is non-empty
4. Update help text to document init is only for fresh setup or with --force flag (optional)
5. Consider adding --force flag if user really wants to reset (with confirmation)