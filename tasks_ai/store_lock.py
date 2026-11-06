"""Serialize mutations of the shared .tasks store across agents.

The store is one git repo written by every worktree and every agent session.
Git protects only its own index, so two read-modify-write transactions racing
each other (id allocation, manifest rewrite, undo) lose data with no error.
flock is per-open-file and is released by the kernel when a holder dies, so a
crashed agent never leaves a stale lock behind.

Reentrancy: a transaction may call another committed store operation
(commit_task_paths is the choke point for most mutations). Nested acquisitions
of the same lock in one thread would deadlock, so a second request in the
same thread passes straight through.
"""

import fcntl
import os
import threading
from contextlib import contextmanager

_local = threading.local()

LOCK_NAME = ".hammer-lock"


@contextmanager
def store_lock(cli):
    """Hold the store-wide write lock for the duration of the block."""
    if getattr(_local, "depth", 0):
        _local.depth += 1
        try:
            yield
        finally:
            _local.depth -= 1
        return
    path = os.path.join(cli.tasks_path, LOCK_NAME)
    # No truncate and never unlink: another agent may be blocked on this
    # same inode right now.
    fd = os.open(path, os.O_CREAT | os.O_RDWR, 0o644)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        _local.depth = 1
        try:
            yield
        finally:
            _local.depth = 0
    finally:
        fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)
