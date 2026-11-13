1. Grep all 'add --all' sites in tasks_ai/ and classify: per-task vs whole-store sweep
2. Replace per-task sites with commit_task_paths (unlink, delete, doctor repairs, archive hook)
3. Wrap the two whole-store sweeps in store_lock with an explanatory comment
4. Add the two-task pending-edit tests per site plus the concurrent unlink+checkpoint test
5. Run ./hammer check all
6. Unlink, delete, doctor and archive still commit the whole shared store