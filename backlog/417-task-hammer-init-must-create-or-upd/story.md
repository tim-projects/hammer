As a project maintainer, I want `hammer tasks init` to create or refresh `.tasks/.gitignore` from a defined template so generated task storage consistently excludes local and transient files while retaining the intended documentation Markdown files.

The Markdown rule must be present in the template. The canonical template is the current `.tasks/.gitignore` content, including `*.md` plus the `!README.md` and `!AGENTS.md` exceptions.
