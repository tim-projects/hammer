Research findings:

- `unref` is a standalone executable published on PyPI (`unref` 0.2.2 was the latest version on 2025-03-08) with documentation at https://unref.readthedocs.io/en/latest/ and source at https://github.com/Apakottur/unref.
- `unref [paths]` checks the given files/directories, or the project root; it exits non-zero when it finds issues.
- `unref` complements Ruff rather than replacing it: `unref` reports unreferenced functions, classes, methods, module variables, attributes, and invalid ignore comments; unused imports and local variables remain Ruff's responsibility.
- Project configuration uses `[tool.unref]` in the closest `pyproject.toml`. The CLI supports `--config`, `--python`, `--output-format`, `--show-transitive`, `--jobs`, and `--version`.
- Current Hammer integration points are `tasks_ai/validator.py` (lint command registry and check execution), the legacy `check.py` command registry, `tasks_ai/commands/config.py` / `tasks_ai/cli.py` configuration handling, `tasks_ai/validation.py` tool detection, and their tests under `tests/`.
- Preserve the existing scalar `repo.lint` contract and Ruff behavior. Add the smallest opt-in companion configuration needed to select `unref`; an absent companion setting must not look for, install, or run `unref`.
