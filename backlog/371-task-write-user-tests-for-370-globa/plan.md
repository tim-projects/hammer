1. 1. Inventory all hammer commands and flags; publish the full combination list (tasks, check, repo, guard, auto-detect aliases)
2. 2. Move -j/--json parsing into the global argument layer, ahead of subcommand dispatch
3. 3. Hoist -j/--json onto every subparser so any position works
4. 4. Force JSON output unconditionally on error and usage paths too
5. 5. Add tests over flag-order permutations and the command matrix; run ./hammer check all