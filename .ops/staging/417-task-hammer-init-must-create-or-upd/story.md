As a project maintainer, I want `hammer tasks init` to create or refresh `.tasks/.gitignore` from a defined template so generated task storage consistently excludes local and transient files while keeping all Markdown files visible to Git.

Markdown files must be exempt from ignore rules and tracked by Git. The canonical template includes the explicit `!*.md` rule; it must not contain a rule that ignores Markdown files.
