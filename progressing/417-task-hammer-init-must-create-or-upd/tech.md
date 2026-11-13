Update the production `hammer tasks init` implementation in `tasks_ai/cli.py` so initialization ensures `.tasks/.gitignore` exists and reflects the canonical template. The template must include:

```gitignore
# Runtime locks and transient staging
/.hammer-lock
/.ops/

# Local validation, logs, and legacy counter caches
/.last_validation_hash
/log/
/.task_counter.backup
/.task_counter.backup.hash
/task_counter

# Python environments and caches
/.venv/
/venv/
__pycache__/
*.py[cod]
.pytest_cache/

# Local scratch and backups
tmp*
*.tmp
*.bak
*.txt

# Task records are persistent data and must be tracked by Git
!*.md
```

The live `.tasks` store contains persistent task records in Markdown and JSON, activity and verification logs inside task directories, patches, audits, hashes, configuration, the active counter and counter hash, the worktree manifest, and doctor reports. None of those file classes may be excluded by the template. Markdown files must be explicitly exempt and tracked by Git; the template must not contain `*.md` or narrow exceptions such as `!README.md` and `!AGENTS.md`.

Initialization must be idempotent. Refresh stale or missing managed entries without duplicating rules, and preserve unrelated user-authored entries outside the managed template. Add focused regression coverage for a fresh initialization, repeated initialization, and Git tracking of a Markdown file.
