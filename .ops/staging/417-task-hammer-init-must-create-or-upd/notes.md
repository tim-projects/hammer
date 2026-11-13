
## Live store assessment

Inspected 2,713 tracked files in `.tasks` plus all untracked and ignored paths.

Included as persistent task data:
- Markdown task sections and doctor reports
- JSON metadata and `worktrees.json`
- Task-directory activity and verification logs
- Patches, audits, audit hashes, and counter hash
- `config.yaml`, active `.task_counter`, and state `.gitkeep` files

Ignored as local/transient data:
- `.hammer-lock` and `.ops/`
- `.last_validation_hash`, legacy counter backups, and the legacy `task_counter`
- Standalone `/log/` debug output
- Python environments and caches
- Empty `tmp*` scratch files, `*.tmp`, `*.bak`, and `*.txt`

The live `.tasks/.gitignore` now uses the assessed template with `!*.md`. All 1,414 tracked Markdown files remain tracked, and a new Markdown file is addable by Git. Confirmed disposable files were removed from the store index without deleting their contents from disk.