RESEARCH (489 - repo plumbing to provisioning):
- Verified current repo.py structure (post-454): pipeline() :77 returns ['testing','staging',default] (shared); cmd_merge_task_worktree :292 (new, worktree-local); cmd_merge :342; check_merged_to_testing :270; ensure_pipeline_branch :525.
- Changes: pipeline() -> ['provisioning', default]; cmd_merge pipeline->status map -> provisioning; check-merged-testing -> provisioning; ensure_pipeline_branch creates provisioning off origin/<default>.
- Branch-protection: deletion guard lives in the pre-receive/delete hook template written in cli.py:631 (install_hooks) - add 'provisioning' next to the default branch; keep testing/staging undeletable as history.
- resolve_branch (:411-423) maps a leading numeric id to the task folder name - stage refs derive from Id, not from that path; no collision expected but test.
