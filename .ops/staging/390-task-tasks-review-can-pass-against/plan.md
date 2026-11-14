1. Reproduce: mutate a file on a task branch, re-enter REVIEW, inspect patch artifacts
2. Trace why ReviewDiffHook/generate_file_patches skipped the rewrite (conditional generation, diff base after sync merge)
3. Make generation unconditional on REVIEW entry and prune patches outside the changed set
4. Detect stale receipts: compare patch content against a fresh generation or branch-derived hash at finalize and regression-check
5. Add tests: content change after review invalidates receipts; pruned stale patches; forced refresh path
6. Run the full review suites and check all