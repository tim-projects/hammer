1. Move ResearchGateHook registration and target-state condition from READY -> PROGRESSING to BACKLOG -> READY
2. Update the RESEARCH_REQUIRED hint and AGENTS.md pipeline guidance for the new gate
3. Update existing tests and add coverage for BACKLOG -> READY blocking and READY -> PROGRESSING behavior
4. Run check all and review the diff