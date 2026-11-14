1. 1. Configure a validation check that exits non-zero with lint output on stdout.
2. 2. Attempt a promotion transition that runs validation.
3. 3. Before the fix, Hammer reports only `Pipeline validation failed` and `Tool execution failed`, hiding the lint details.