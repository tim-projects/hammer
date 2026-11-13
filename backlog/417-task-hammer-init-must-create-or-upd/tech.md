Update the production `hammer tasks init` implementation in `tasks_ai/cli.py` so initialization ensures `.tasks/.gitignore` exists and reflects the canonical template. The template must include:

```gitignore
tasks/
venv/

.tasks/
.tasks.bak/

__pycache__/
*.pyc
.pytest_cache/

*.md
!README.md
!AGENTS.md

*.txt

.hammer tasks/

*.bak

.hammer-lock
```

Initialization must be idempotent. Refresh stale or missing managed entries without duplicating rules, and preserve unrelated user-authored entries outside the managed template. Add focused regression coverage for a fresh initialization and repeated initialization.
