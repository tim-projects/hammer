RESEARCH (477 - PR/PROVISIONING states):
- Verified 2026-11-09 on main 84f43bba: PIPELINE_STAGES (tasks_ai/constants.py:88-97) has no PR/PROVISIONING; STATE_FOLDERS and DEFAULT_ALLOWED_TRANSITIONS are the sibling structures in the same file; ALLOWED_TRANSITIONS is an alias of DEFAULT at :102.
- get_next_logical_state (git_service) derives order from PIPELINE_STAGES - inserting states changes no-arg move targets; verify after edit.
- Guard enumerates state folders from STATE_FOLDERS.values() (guard_engine.py:36, :293) and path-segment validation at :279 - adding folders requires guard to accept them (it derives from constants, so it follows automatically; test it).
- KEY_MAP needs 'Ap'. Decide folder names pr/ and provisioning/ up front: STATE_FOLDERS keys are also used by audit/integrity paths (pipeline.py:178-186 references review/ by name).
- No other consumer of PIPELINE_STAGES found besides move gates, guard, and list.
