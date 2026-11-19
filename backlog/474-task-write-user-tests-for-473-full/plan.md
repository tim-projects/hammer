1. 1. Reproduce each in full-suite context; instrument to find the leaking state (env vars, cwd,
2.    leftover /tmp dirs, in-flight dev repos).
3. 2. Isolate per test (fresh dev store per test, deterministic ids) or fix the underlying race
4.    for the store-writes case (scoped add+commit under the store lock).
5. 3. Verify: full suite x2 identical; the three tests green both standalone and in-suite.