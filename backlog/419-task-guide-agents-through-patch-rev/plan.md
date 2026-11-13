1. 1. Add an action-required JSON/terminal renderer without changing the failure exit status.
2. 2. Route the expected `PROOF_MISSING` workflow prerequisite through that renderer.
3. 3. Pass dynamic review, patch, proof, and task context from the pipeline.
4. 4. Replace the `PROOF_MISSING` registry text with Hammer-voice WHAT/WHY/HOW/CONSEQUENCE guidance.
5. 5. Distinguish expected action-required output from genuine failures in `AGENTS.md`.
6. 6. Add and run focused regression tests, then run the project validation suite.