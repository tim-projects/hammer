1. 1. Add a REJECTED guard to ProgressUpdateHook before progress-file checks.
2. 2. Add a regression test proving rejection succeeds without progress files.
3. 3. Run the focused and full relevant validation checks.
4. 4. Review the diff, run the regression check, and promote the task through the pipeline.