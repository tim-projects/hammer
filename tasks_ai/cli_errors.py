class PipelineMergeConflict(Exception):
    """Raised when a git merge conflict occurs during a pipeline transition."""

    def __init__(self, branch, default):
        self.branch = branch
        self.default = default
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
