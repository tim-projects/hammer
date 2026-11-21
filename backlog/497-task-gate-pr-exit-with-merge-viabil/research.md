RESEARCH (497 - PR gates + approval):
- Verified: review machinery now lives in tasks_ai/review.py (covered_patches / load_reviews / write_reviews, imported by modify.py:153); the Reviewed flag + review records pattern is modify.py:136-174 - build --approve on exactly this (md5 per patch + timestamp; refuse when patch content changed), per index decision D5 (md5, not sha256; sha256 exists only in the composite audit hash, pipeline.py:242+).
- Freshness: WorktreeSyncHook (pipeline_hooks.py:406+) already merges origin/<default> into a worktree branch - reuse for <id>-PR preparation on PR entry.
- Conflict check: 'git merge-tree --write-tree <id>-PR provisioning' - in-core, no worktree/index, git 2.47.3 present; 100-agent safe.
- Validation freshness comes from TpBase (task 491) - sequence after it.
- Patch regeneration: ReviewDiffHook's generator in pipeline_hooks.py (patches into .tasks/review/<id>/patches/) - change only its comparison base.
- validate_gate approval check + --force must NOT flip Ap (record bypass only, like GuardRecordHook).
