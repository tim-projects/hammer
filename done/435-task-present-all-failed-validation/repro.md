1. 1. Run `hammer check all` with a failing test, typecheck, or format check.
2. 2. Observe inconsistent native wording such as `FAILED`, `errors`, or `would be reformatted`.
3. 3. Observe that the whole result set is printed as one long Python repr, which terminal adapters can truncate in the middle.