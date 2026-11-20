1. Inventory all hammer commands and flags; publish the full combination list (tasks, check, repo, guard, auto-detect aliases)
2. Move -j/--json parsing into the global argument layer, ahead of subcommand dispatch
3. Hoist -j/--json onto every subparser so any position works
4. Detect help (-h/--help) first and short-circuit to plain text; only apply the JSON directive when help is absent, so error and usage paths still emit valid JSON
5. Add tests over flag-order permutations, every -h/--help + -j combination, and the command matrix; run ./hammer check all