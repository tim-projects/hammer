from .task_id_allocator import allocate_task_id


class TaskCounterProtector:
    """Compatibility entry point until task 495 retires the counter module."""

    def get_next_id(self, cli, count=1):
        return allocate_task_id(cli, count)
