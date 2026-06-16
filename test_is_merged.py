from tasks_ai.git_service import GitService
from unittest.mock import MagicMock

context = MagicMock()
context.repo_root = "."
git = GitService(context)
print(
    f"Is 282 merged: {git.is_merged('282-task-test-reconcile-unmerged-detect', 'main')}"
)
