Research findings:

1. Usage failures in `tasks.py`, `tasks_ai/check_wrapper.py`, `repo.py`, and `guard.py` all use `argparse.ArgumentParser`. Its default `error()` method writes the tool-specific usage block followed by `<prog>: error: <detail>` and exits 2.
2. Parser-created subcommands inherit the parent parser class, so one shared `ArgumentParser` subclass can change the status token for every nested option, missing argument, invalid choice, and invalid value path.
3. Successful help paths do not call `error()` and remain successful. Bare tool invocations print help and exit 1 without an `error:` status token.
4. The top-level `hammer` wrapper has no argparse parser; its unknown-command path is not an argparse usage output.
5. The root `check.py` is an internal standalone script that is copied without the `tasks_ai` package. It is not the `./hammer check` entry point; `tasks_ai/check_wrapper.py` is. The standalone script must remain dependency-free.
6. The smallest complete change is a shared parser class that preserves argparse's usage text, detail message, stream, and exit code while replacing only the `error:` status token with `blocker:`. No new prose or JSON envelope is needed for this task.
7. Existing help coverage in `tests/test_help_coverage.py` protects successful help and bare invocation behavior. New focused regressions exercise invalid usage across all four Hammer tools and nested subcommands.
