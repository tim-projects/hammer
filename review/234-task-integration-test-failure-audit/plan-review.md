Plan: Structured Patch Review (MD5-based, lightweight)

Objective: Require agents to actually read patch contents before marking a review complete, preventing the boolean `--reviewed` attestation from being gamed by simply touching a patch file.

1. ReviewDiffHook (on entering REVIEW)
   - Generate per-patch MD5 content hash for each generated patch file
   - Store in task metadata PatchFiles as [{file, patch_path, md5_hash}]
   - MD5 is used (already established in tasks_ai/audit.py:116 generate_audit and :135 verify_audit)

2. Replace boolean --reviewed with structured review entries
   - New metadata field PatchReviews: [{file, decision, findings, md5_hash, reviewed_at}]
   - decision: approved / rejected / changes_requested
   - findings: non-empty substantive notes on regressions/mistakes/risks
   - md5_hash: MD5 of the patch file content at review time (forces reading content)
   - reviewed_at: timestamp

3. Gate: modify --reviewed
   - Rejects if any patch in PatchFiles lacks a matching PatchReviews entry
   - Rejects if findings is empty/trivial (min length check)
   - Rejects if provided md5_hash does not match the patch file's current MD5
   - On success, sets task.metadata['Reviewed'] = True and stores PatchReviews

4. Gate: regression-check
   - Validates all patches have reviews matching current content MD5 hashes
   - Patches modified after review invalidate their review entries

5. Gate: audit (at STAGING/DONE)
   - Verifies review hashes still match patch files
   - Ensures no patch was silently altered after review

6. Skip review when codebase unchanged
   - Reuse existing git HEAD hash check in check.py run_all (.last_validation_hash)
   - If HEAD hash equals stored hash, skip patch review gating entirely

7. Verification
   - Re-run tests/test_audit_verify_integration.py to confirm gating works
