1. 1. Define the canonical ensure-and-sync behavior in WorktreeSyncHook.
2. 2. Move mount onto the hook and delete duplicate mount synchronization logic.
3. 3. Resolve local main first and add remote divergence reporting.
4. 4. Add safe conflict detection and actionable blocker output.
5. 5. Add parity tests for mount and READY to PROGRESSING.