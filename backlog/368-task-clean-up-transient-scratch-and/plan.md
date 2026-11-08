1. Commit or stash the currently modified files so the cleanup commits stay reviewable
2. Group 1: print the 23 tracked paths with git ls-files, pause, get explicit user approval, then git rm and commit
3. Group 2: print the 8 tracked paths plus git status for error_report.json, pause, get explicit user approval, then git rm (with -f where needed) and commit
4. Group 3: print the 5 tracked paths, pause, get explicit user approval, then git rm and commit
5. Group 4: print the 31 untracked paths with byte sizes, pause, get explicit user approval, then rm
6. Group 5: print the 12 .kilo/ entries with byte sizes, pause, get explicit user approval, then rm -rf .kilo
7. Group 6: print the 30 untracked paths with byte sizes, pause, get explicit user approval, then rm
8. Run ./hammer check all and review the REVIEW diff for regressions before promotion