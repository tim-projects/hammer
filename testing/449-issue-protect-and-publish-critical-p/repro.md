1. 1. In a repository initialized by hammer, attempt to delete the default branch, testing, or staging locally.
2. 2. Attempt the same deletions with hammer repo branch delete.
3. 3. Move a task through TESTING and STAGING and inspect the remote refs after each transition.
4. 4. Observe whether local branch deletion is allowed, whether hammer forwards deletion to Git, and whether testing and staging are pushed when the task crosses those gates.