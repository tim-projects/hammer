## Plan
1. Grep the four hook strings in `tasks_ai/cli.py` install_hooks and every `main` literal in `tests/repo.py`; classify each (allow-list, merge guard, diff comparison, deletion guard, pipeline top)
2. Add default-branch resolution to the bash hook template — same semantics as `GitService.get_default_branch`: `git symbolic-ref --quiet refs/remotes/origin/HEAD` (strip `refs/remotes/origin/`), else first existing of main/master, else main as final fallback
3. Interpolate the resolved branch into all four hook strings (pre-commit allow-list, pre-merge guard, post-merge diff base, pre-receive protected set); keep the generated bash readable
4. Make `tests/repo.py` derive the pipeline's final branch from the same resolution via one shared helper instead of the `PIPELINE` literal `main`
5. Add `tests/test_hooks_default_branch.py`: install hooks into a master-named and a main-named temp repo; assert the generated scripts contain the resolved branch and that a direct commit on the default branch is allowed while a direct merge into it is blocked
6. Re-install the hooks in this repo (`tasks init` / `init_hooks`) so the local `.git/hooks` pick up the fix
7. Run `./hammer check all`
