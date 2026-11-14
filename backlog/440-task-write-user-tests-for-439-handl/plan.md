1. 1. Add a shared platform-safe `SIGPIPE` configuration helper and call it from every Hammer tool entry point.
2. 2. Add a subprocess regression with oversized output and an early-closing stdout consumer.
3. 3. Verify the regression detects the current traceback and passes without one after the fix.
4. 4. Run focused CLI tests and the complete validation suite.