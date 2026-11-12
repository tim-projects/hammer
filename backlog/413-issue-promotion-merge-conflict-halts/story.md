As a Hammer user promoting a task (`tasks move <id> TESTING|STAGING|DONE`), when the
task branch conflicts with the pipeline branch, I want the move to halt with a
structured MERGE_CONFLICT error and the repository left clean, so the pipeline
stops predictably instead of crashing with a traceback and an in-progress merge.
