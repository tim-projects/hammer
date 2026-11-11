class PipelineMergeConflict(Exception):
    """Raised when a git merge conflict occurs during a pipeline transition."""

    def __init__(self, branch, default):
        self.branch = branch
        self.default = default
        super().__init__(f"Merge conflict {branch} -> {default}.")
