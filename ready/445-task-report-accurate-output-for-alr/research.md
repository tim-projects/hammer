Research findings:

1. The misleading output is assembled across three places:
   - `tasks_ai/pipeline.py:90-92` logs the fast-track DEBUG line. This must not be user-visible in the approved scenario.
   - `tasks_ai/git_service.py:510-519` logs the missing-`staging` fallback and the generic `Performing pipeline promotion` line. These must not be user-visible when the resolved operation is a no-op.
   - `tasks_ai/git_service.py:334` logs `Merging ...`, and `tasks_ai/git_service.py:86-87` logs `Git: Merged ...` for every successful merge command. Neither is accurate when Git creates no merge commit.

2. `tasks_ai/pipeline.py:76-93` fast-tracks REVIEW/STAGING/DONE promotions when the task branch is an ancestor of the default branch and the task record contains commits. It currently skips validation gates but does not itself skip or perform the merge.

3. `tasks_ai/git_service.py:489-527` selects `staging` as the DONE merge source. If local `staging` is absent, it falls back to the task branch. The approved scenario therefore requires resolving the actual source first, then proving that source is already contained in the target.

4. The approved line must require all of these facts:
   - the target is DONE;
   - the task branch is already contained in the default branch;
   - the task record contains commits, so an empty branch cannot trigger the fast path;
   - the resolved merge source is already contained in the target;
   - the merge attempt creates no target commit.

5. Recommended control flow:
   - Add a narrowly scoped result from `merge_branches` that distinguishes `created_commit` from `already_up_to_date` by comparing the target commit before and after the merge. Do not infer this from Git's exit code, because `Already up to date` also exits zero.
   - Keep merge logging inside `merge_branches`, where source, target, and pre/post commit IDs are known. The generic logger in `_handle_command_logging` must not claim `Git: Merged` for a no-op.
   - In `promote_task`, resolve the fallback source before emitting fallback/promotion messages, or buffer/scope those messages until the operation outcome is known.
   - For the approved no-op case, suppress the fast-track DEBUG line, missing-`staging` fallback line, `Performing pipeline promotion` line, `Merging ...` line, and `Git: Merged ...` line, then emit exactly:
     `WORK ALREADY ON MAIN. NO MERGE NEEDED. CHECKS SKIPPED. TASK COMPLETE. HAMMER POUND ON.`
   - If the resolved source contains additional work, perform and report the real merge with the existing merge-oriented wording instead of the approved line.

6. Preserve existing behavior for ordinary merges, non-DONE transitions, empty task branches, and real DONE merges that create a commit. The same logger feeds text and JSON message output, so verify both modes.

7. Focused tests should assert the exact approved line, assert absence of every misleading line listed above, and cover negative cases for a real merge, an empty branch, and a resolved source with additional commits.
