1. Wrap perform_move's body in store_lock (reentrant with the commit that follows)
2. Make find_task deterministic on duplicates: prefer the folder whose state matches metadata St
3. Make list dedupe by task id
4. Make the guard's state-duplicate check St-aware
5. Tests: constructed duplicate folders; reader-during-move with threads; check all
6. Move leaves the task in two state folders between write and delete