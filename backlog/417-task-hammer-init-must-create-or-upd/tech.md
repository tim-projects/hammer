Update the production `hammer tasks init` implementation in `tasks_ai/cli.py` so initialization ensures `.tasks/.gitignore` exists and reflects the canonical template. The template must include:

```gitignore
tasks/
venv/

.tasks/
.tasks.bak/

__pycache__/
*.pyc
.pytest_cache/

!*.md

*.txt

.hammer tasks/

*.bak

.hammer-lock
```

The `!*.md` rule exempts all Markdown files from Git ignore processing. Do not include `*.md` or narrow exceptions such as `!README.md` and `!AGENTS.md`; every Markdown file in the task store must remain eligible for Git tracking.

Initialization must be idempotent. Refresh stale or missing managed entries without duplicating rules, and preserve unrelated user-authored entries outside the managed template. Add focused regression coverage for a fresh initialization, repeated initialization, and Git tracking of a Markdown file.
