1. 1. Use a scratch repo (or `--dev`) with default branch `main`.
2. 2. Create two task branches that edit the same line of the same file.
3. 3. Promote task A to DONE (merges A into main successfully).
4. 4. Run `./hammer tasks move <id-of-B> DONE`.
5. 5. Observed: RuntimeError traceback from merge_branches; `git status` in the
6.    main repo shows "You have unmerged paths" / "All conflicts fixed but you are
7.    still merging"; MERGE_CONFLICT message and resolution steps never appear.
8. 6. Any subsequent `./hammer tasks move ...` on that repo fails on the same
9.    in-progress merge until a manual `git merge --abort`.