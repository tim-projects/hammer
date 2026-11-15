# Bug Report: Broken Task Creation and Audit Regression

## Summary
The `tasks create` command is currently non-functional due to a `NameError: name 'TaskCounterProtector' is not defined`. Additionally, existing tasks (specifically task 184) are failing cryptographic audit integrity checks, preventing pipeline progression.

## Issue 1: Missing `TaskCounterProtector` Class
### Description
The `TasksCLI._get_next_id` method attempts to instantiate `TaskCounterProtector`, but this class is not defined anywhere in the current `main` branch. This blocks all task creation.

### Reproduction Steps
1. Run `./hammer tasks create "Test Task"`
2. Observe the following error:
   ```
   Traceback (most recent call last):
     ...
     File "/home/vscode/git/tasks-ai/tasks_ai/cli.py", line 979, in _get_next_id
       protector = TaskCounterProtector(self.tasks_path, self)
                   ^^^^^^^^^^^^^^^^^^^^
   NameError: name 'TaskCounterProtector' is not defined
   ```

---

## Issue 2: Cryptographic Audit Failure
### Description
Task 184 (`Test recovery from scratch`) fails the audit integrity check, blocking `tasks move` to `DONE` and preventing the merge of its branch into `main`.

### Reproduction Steps
1. Run `./hammer tasks audit 184`
2. Run `./hammer tasks move 184 DONE`
3. Observe the error:
   ```
   Error: Task '184' failed cryptographic audit integrity check. | HINT: The criteria or proof has changed since the last audit. Re-run 'tasks audit' and 'tasks verify'.
   ```

---

## Environment Information
- **Branch**: `main`
- **Last Successful Commit**: 39ad4da (estimated from git status/logs)
- **Current State**: Pipeline blocked; critical functionality broken.
