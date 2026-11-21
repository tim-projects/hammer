1. 1. Extend constants (stages, folders, transitions for STAGING->PR, PR->PROVISIONING, PROVISIONING->{DONE,ARCHIVED,PR,REJECTED}, mirror into BLOCKED/DONE/REJECTED exit lists where STAGING appears)
2. 2. Verify get_next_logical_state lands on the right next stage
3. 3. Add tests for acceptance + forbidden skips