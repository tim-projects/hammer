
## Implementation

- Added a platform-safe `configure_sigpipe()` helper in `tasks_ai/cli_io.py` that restores `SIG_DFL` only when `SIGPIPE` exists.
- Wired the helper into the `tasks`, `check`, `repo`, and `guard` process entry points without changing import-time signal state.
- Kept the internal standalone `check.py` dependency-free; `./hammer check` uses `tasks_ai/check_wrapper.py`.
- Added a subprocess regression with 256 KiB of task output that closes stdout early and requires termination by `SIGPIPE` with no traceback.
- Made both SIGPIPE regressions skip cleanly on platforms where `SIGPIPE` is unavailable.

## Verification

- Focused SIGPIPE regressions: 2 passed.
- SIGPIPE, usage, help, CLI robustness, and error-reporting suites: 15 passed, 285 subtests passed.
- Full `./hammer check all`: lint, test, typecheck, and format all passed before and after the portability guard.