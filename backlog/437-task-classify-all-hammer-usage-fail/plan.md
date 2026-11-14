1. 1. Inventory every argparse and wrapper usage-failure path and record the current text, JSON shape, and exit behavior.
2. 2. Add one shared usage-status normalization path that preserves existing usage output and classifies failures as blockers.
3. 3. Apply the normalization to every Hammer tool entry point without changing successful help or version behavior.
4. 4. Add focused regressions for the full usage-failure contract and machine-readable output.
5. 5. Run focused tests and the complete validation suite.