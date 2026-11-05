1. 1. Mirror tasks_ai/commands/link.py into tasks_ai/commands/unlink.py with inverse logic for the 'Bl' list
2. 2. Add TasksCLI.unlink delegation method next to link in tasks_ai/cli.py
3. 3. Register 'unlink' subparser and dispatch in ./tasks.py (place next to 'link')
4. 4. Verify help text and error catalog entries (check tasks_ai/messages or error catalog for LINK_* codes)
5. 5. Write user tests under tests/ covering link/unlink roundtrip and error cases
6. 6. Run ./hammer check all and resolve any lint/typecheck/test failures