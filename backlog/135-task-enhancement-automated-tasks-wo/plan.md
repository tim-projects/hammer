1. Extend current save mechanism to use local 'tasks' branch in addition to remote
2. Add post-archive hook to call save automatically
3. Add 'hammer tasks restore' command (manual)
4. Test: archive a task → verify tasks branch updated
5. Test: delete .tasks → run restore → verify recovery
6. Update agent guidance with new workflow