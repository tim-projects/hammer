As the pipeline operator driving the redesign at scale (~100 concurrent task
worktrees), I hand work into the shared funnel from the task's own worktree:

    cd .task-worktrees/<task-branch>
    ./hammer repo merge <id> provisioning -y

Today that command crashes before any lock is taken: `merge_lock`
(`tasks_ai/utils.py:43-44`) builds its lock path from the caller-supplied repo
root, which from a linked worktree is the worktree top-level whose `.git` is a
plain *file* pointing at `.git/worktrees/<name>`. `os.makedirs(...,
exist_ok=True)` then raises `FileExistsError` and the merge never runs. Even
where a `.git` directory exists, per-worktree paths would hand every worktree
its own lock file, silently dropping the cross-worktree serialization that
task 483 introduced. I want the shared merge lock to resolve the repository's
common git dir so funnel merges work, and serialize identically, no matter
which worktree invokes them.