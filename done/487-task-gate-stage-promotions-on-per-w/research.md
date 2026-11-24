RESEARCH (487 - per-worktree integration gates):
- Verified: validate_gate (pipeline.py:67); the integration block is the 'main_sync' gate at :146-154 (integration_target = staging or default) plus the fast-track at ~:84-93 (is_merged(branch, default) + commits evidence).
- New mapping needed: TESTING is_merged(Br,<id>-TESTING); STAGING is_merged(<id>-TESTING,<id>-STAGING); PR is_merged(<id>-STAGING,<id>-PR); PROVISIONING is_merged(<id>-PR,'provisioning').
- Error messages should name the exact missing ref and the remedy (the hints.json GUARD_* entries show the house wording style).
- get_enabled_gates (pipeline.py:27-37) composes which gates run per target state - add the new gate names there, not inline.
