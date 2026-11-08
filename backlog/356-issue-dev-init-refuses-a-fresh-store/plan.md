1. Reproduce on a fresh temp store; capture the exact check that fires
2. Change the dev init check from directory existence to store initialization (.git present or task data), mirroring the non-dev branch
3. Ensure the refused path leaves no half-store (clean empty dir or complete the init)
4. Add tests: fresh init succeeds and is a git repo; existing store refuses without --force; dev create commits
5. Run ./hammer check all
6. Dev init refuses a fresh store because the CLI pre-creates the directory