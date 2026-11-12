"""One naming rule for task id, branch, folder and worktree directory.

create.py and doctor.py each used to derive a task name from its title with their
own copy of the 30-character slug cut. They now share derive_task_id(), and the
doctor additionally checks the registered worktree path against
<worktrees_base>/<branch> via worktree_path_matches().
"""

import unittest

from tasks_ai.utils import derive_task_id, worktree_path_matches


class TestDeriveTaskId(unittest.TestCase):
    def test_long_title_is_cut_at_the_same_place_it_always_was(self):
        self.assertEqual(
            derive_task_id(
                344,
                "task",
                "Pipeline should auto-push branches instead of demanding manual push",
            ),
            "344-task-pipeline-should-auto-push-bran",
        )

    def test_punctuation_and_case_collapse_to_one_dash_each(self):
        self.assertEqual(
            derive_task_id(9, "task", "Fix a things: odd/symbols & spaces!!"),
            "9-task-fix-a-things-odd-symbols-space",
        )

    def test_title_shorter_than_the_cap_is_kept_whole(self):
        self.assertEqual(derive_task_id(1, "issue", "ab"), "1-issue-ab")

    def test_title_with_no_usable_characters_falls_back_to_task(self):
        self.assertEqual(derive_task_id(7, "task", "!!!"), "7-task-task")


class TestWorktreePathMatches(unittest.TestCase):
    BASE = "/repo/.task-worktrees"
    BRANCH = "348-issue-task-branch-and-directory-name"

    def test_matching_worktree_path(self):
        self.assertTrue(
            worktree_path_matches(self.BASE + "/" + self.BRANCH, self.BASE, self.BRANCH)
        )

    def test_mismatched_worktree_path_is_caught(self):
        self.assertFalse(
            worktree_path_matches(
                self.BASE + "/" + self.BRANCH + "x", self.BASE, self.BRANCH
            )
        )

    def test_path_outside_the_base_is_caught(self):
        self.assertFalse(
            worktree_path_matches("/elsewhere/" + self.BRANCH, self.BASE, self.BRANCH)
        )
