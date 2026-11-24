class PipelineMergeConflict(Exception):
    """Raised when a git merge conflict occurs during a pipeline transition."""

    def __init__(self, branch, default, paths=None):
        self.branch = branch
        self.default = default
        self.paths = paths or []
        super().__init__(f"Merge conflict {branch} -> {default}.")


class PipelineBranchMissing(Exception):
    """Raised when a required pipeline branch cannot be restored."""

    def __init__(self, branch):
        self.branch = branch
        super().__init__(f"Required pipeline branch '{branch}' is missing.")


class PipelinePushError(Exception):
    """Raised when a pipeline branch cannot be published."""

    def __init__(self, branch, stderr):
        self.branch = branch
        self.stderr = stderr
        super().__init__(f"Failed to push pipeline branch '{branch}'.")


class PipelineGuardRejected(Exception):
    """Raised when the guard rejects a merge source branch."""

    def __init__(self, branch, code, task_id, detail):
        self.branch = branch
        self.code = code
        self.task_id = task_id
        self.detail = detail
        super().__init__(f"Guard rejected merge source '{branch}': {detail}")
