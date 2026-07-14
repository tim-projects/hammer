from tasks_ai.git_client import GitClient
from unittest.mock import MagicMock

context = MagicMock()
context.repo_root = "."
git = GitClient(context)
print(
    f"Is 282 merged: {git.is_merged('282-task-test-reconcile-unmerged-detect', 'main')}"
)
