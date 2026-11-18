1. 1. Review the validator/configuration call paths and select the smallest backward-compatible opt-in setting for a secondary Python lint check.
2. 2. Register and execute `unref` in the active validator and any still-supported legacy check path, preserving Ruff and `--fix` behavior.
3. 3. Update configuration commands, detection/help, and user documentation for the optional companion check and installation.
4. 4. Add focused regression tests for opt-out, enabled success/failure, missing executable, and Ruff autofix behavior.
5. 5. Run focused tests and the project validation checks, then record any pre-existing failures separately.