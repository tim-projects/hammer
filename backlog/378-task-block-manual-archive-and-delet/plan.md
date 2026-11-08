1. Add the automatic-only message entries and block user ARCHIVED targets in commands/move.py run()
2. Reroute AutoArchiveHook to _move_logic(force=True, yes=True)
3. Extend the _auto_archive sweep to delete aged ARCHIVED and REJECTED records via commit_task_paths
4. Remove delete.py's confirm/hard-delete step, keep the reject move
5. Hoist the grace constant; update AGENTS.md archiving section and help_text guidance
6. Add tests; run ./hammer check all