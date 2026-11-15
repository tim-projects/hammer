1. Add a review command that streams a patch and records a receipt (file, md5, sha256, bytes, ts, seq, prev_hash)
2. Replace the atime check in modify --reviewed with receipt coverage over PatchFiles
3. Bind the receipt chain into .audit_hash and verify_audit
4. Invalidate receipts when PatchGenTime or patch md5 changes
5. Test: read via command passes, grep-only read fails, partial coverage fails, tampered receipts fail