RESEARCH (499 - prod-ready merge):
- Verified: no temp-worktree or check.py run exists on the DONE transition (nothing in pipeline_hooks.py matches 'worktree add'+'check'); the DONE merge itself goes through merge_branches (git_service.py:385) - so the check must wrap or precede that call, and inherit the task-483 lock.
- Pattern: create a linked worktree (git worktree add) at origin/<default>, merge provisioning, run check.py all there; green -> real merge+push; red -> abort with main untouched, remove the worktree in both paths (finally).
- Hook registration: enter-hooks registry in cli.py (~:60-106) - add ProvisioningProdReadyHook there alongside the others.
- Dev-mode safety: the check runs in a temp worktree of the context repo root (dev-aware).
