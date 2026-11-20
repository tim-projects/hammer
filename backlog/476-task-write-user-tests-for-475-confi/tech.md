Research findings:

- `unref` 0.3.2 is installed in the project's ignored `venv` at `venv/bin/unref`; Hammer's validator resolves tools from `venv/bin` when they are not on PATH.
- Hammer shared config now contains `repo.lint_secondary: unref`.
- A fresh scan reported 45 pre-existing candidates across active CLI code, legacy helpers, and test fixtures. Static analysis cannot infer several dynamic dispatch and test helper usages.
- `unref` supports path-scoped `[[tool.unref.overrides]]` with `used-names`. A tested temporary baseline suppresses only the 45 existing symbol names in their specific files and leaves the scan green without globally masking names or excluding whole source trees.
- The baseline belongs in the tracked `pyproject.toml`; the executable remains an environment setup, not a mandatory runtime dependency of the Hammer package.
