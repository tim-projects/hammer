1. Reproduce: pytest tests/test_tasks.py -k long_form_flags_accept_file_path and -k research_gate both fail
2. Find the error emitter used by TasksCLI.error and include the code in the error field
3. Run the two tests and confirm they pass on the original assertions
4. Run the full suite and confirm no new failures