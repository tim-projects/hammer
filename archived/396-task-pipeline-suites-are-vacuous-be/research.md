Research pass for task 396.

Codebase reading:
- tests/test_tasks.py: 9 failing tests (test_auto_archival, test_full_lifecycle, test_long_form_flags_accept_file_path, test_regression_check_flag_sets_rc_metadata, test_regression_workflow_move_back_to_progressing, test_research_gate_requires_recorded_research, test_review_diff_generated, test_review_to_staging_requires_regression_check, test_testing_gate_blocks_when_no_new_changes). All fail with "Research pass not recorded" from helper moves to PROGRESSING that do not record --research first. The research gate (tasks_ai/pipeline_hooks.py ResearchGateHook, registered on READY exit in tasks_ai/cli.py:63) demands Rr metadata before PROGRESSING; unchecked self.run_cmd(["move", ...,"PROGRESSING"]) results are ignored, so tasks stick in READY and every downstream gate assertion passes or fails vacuously.
- tests/test_robustness.py: 9 failures, same cause. tests/test_all_transitions.py: 1 failure (test_transitions), same cause.
- Verified by running the other check.py-ignored suites: test_robustness_bugfix.py, test_artifact_healing.py, test_audit_verify.py, test_audit_verify_integration.py, test_cli_endpoints.py, test_tasks_modular.py all PASS already.
- check.py:400-421 hardcodes an ignore list of 8 test files with the comment "known-failing tests that have pre-existing issues". Files that pass must be un-ignored; files still failing must be fixed then un-ignored (not left ignored).

Online search: none needed; gate behavior fully determined by repo code.

Plan follows the task criteria: fix helper moves in test_tasks.py, test_robustness.py, test_all_transitions.py to record research before PROGRESSING; re-run; decide per check.py ignore entry; keep check all green without ignores.
