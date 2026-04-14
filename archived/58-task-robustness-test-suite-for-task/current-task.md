---
---

# Robustness test plan: 50 scenarios

1. Create task, invalid status move.
2. Create task, valid move to READY, PROGRESSING, TESTING, REVIEW, STAGING, LIVE.
3. Link task, circular dependency attempt.
4. Move to TESTING, then revert to PROGRESSING.
5. Move to STAGING, then move back to PROGRESSING.
6. Create task with short title.
7. Attempt to delete task in LIVE status.
8. Reconcile with non-merged branches.
9. Link non-existent tasks.
10. Attempt multiple checkpoint operations.
11. Run tasks operations while in detached HEAD state.
12. Attempt to move task to illegal state (e.g. READY -> LIVE).
13. Link task to itself.
14. Move task to REJECTED from STAGING.
15. Create issue with same name as existing task.
16. Move task to ARCHIVED without being merged.
17. Attempt to modify task that is ARCHIVED.
18. Move multiple tasks via comma-separated status and check if all succeed.
19. Verify `tasks doctor` detects data inconsistency.
20. Check if `tasks undo` works after a state transition.
21. Run `tasks cleanup` on a task that has been merged.
22. Test `tasks list` with JSON filtering.
23. Run workflow operations with invalid task IDs.
24. Verify file permissions/locked states during operations.
25. Test task creation with extreme character counts in story/tech fields.
26. Attempt to link an ARCHIVED task to a new task.
27. Run `tasks upgrade` when no changes are pending.
28. Attempt move task operation on a task that was just deleted.
29. Verify task branch deletion after `tasks cleanup`.
30. Test concurrent `tasks move` operations on the same task.
31. Check task status update after a failed command (e.g., git error).
32. Run `tasks list` in a non-task git repository.
33. Verify `tasks.py` handles non-utf-8 characters in titles/notes.
34. Attempt to create a task with duplicate numeric ID (simulated).
35. Verify `tasks show` output for missing fields.
36. Test `tasks modify` with empty values.
37. Validate task state transition logic when blockers exist.
38. Run `tasks run` with an invalid command.
39. Check `tasks doctor` behavior when `.tasks` folder is corrupted.
40. Verify task branch naming conventions with special characters.
41. Test task movement while git index is locked.
42. Attempt to create a task in a read-only filesystem.
43. Validate `tasks.py` environment variable overrides (e.g., task dir).
44. Run workflow operations with partial task titles (matching).
45. Check if `tasks move` accepts invalid state names.
46. Verify task history log integrity after multiple moves.
47. Test `tasks cleanup` dry-run vs actual execution.
48. Ensure `tasks undo` handles multiple sequential operations correctly.
49. Test task creation with excessively long plan/criteria lists.
50. Run `tasks init` in an already initialized repository.
