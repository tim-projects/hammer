380c39c Remove duplicate test files, use tests/ folder
cf0e7ad fix: resolve merge conflicts in test files, copy tasks.py to tests/
1bec26c Merge testing into 88 (keep our version)
949d5f5 fix: resolve infinite loop in move and fix JSON output for tests
63709fa test
9456294 test
fb45d0e fix2
b0beac1 fix
231b306 change
8ca1cfb fix
3385c71 fix
48295a4 test
be8093a test
e76387d cleanup
bb84828 test
a73882e Fix move recursion and check.py config handling
534a200 Fix test infrastructure and TESTING gate logic
9f46899 Enable robust tests: 54 passed, 10 failing remain
eebba50 Tests use hammer wrapper
06a8bc1 Use hammer wrapper for all commands
c9b5728 Enable all tests and fix merge gates
1dbca2b Fix test JSON parsing and diff check
360f51e Add skip_push to CLI and update test config
cf8f152 Add repo.skip_push config to disable remote operations
b614ef9 Add remote config and test environment setup
625eaa0 Fix test environment: config lookup, dev mode, tool path, test bypass
613dbcd Add --dev flag propagation through CLI for test isolation
e7182be Finalize modularization and test environment hardening
ee3a8fa Add feature
5732b31 Partial changes
1294115 Task 90: Finalizing tool auto-detection and test setup
505fa67 Final cleanup of task implementation
ab77310 Fix: Recursive pipeline branch creation and bypass validation in test environment
05c388a Fix: Recursive pipeline branch creation in repo.py
fb56a8d Fix: Replace hardcoded 'origin' with dynamic remote detection
2645e0a WIP: Auto-commit testing
d93adb5 merge: 84-task-fix-pre-existing-regression-te into testing
3d5f0b7 chore: progress on task 84
f18b63b Merge branch '84-task-fix-pre-existing-regression-te' into testing
24ae1e2 feat: Handle missing origin remote with -y for local-only mode
4acf7dc Merge: Resolve conflict using task branch version
3beefed fix: Prevent recursive promotion and fix -y flag handling
0aefc87 WIP: Auto-commit testing
31eaf73 WIP: Auto-commit testing
9ff7f7d Merge: Use incoming changes for cli.py
c9730d8 fix: Prevent recursive promotion and add skip_gate option
218d0ea WIP: Auto-commit testing
fce5b8f WIP: Auto-commit testing
9fd7ca9 WIP: Auto-commit testing
65557be WIP: Auto-commit testing
d9f49d8 WIP: Auto-commit testing
5f04586 merge: 84-task-fix-pre-existing-regression-te into testing
85a5a8f Final fix for tests
1ea86ed merge: 84-task-fix-pre-existing-regression-te into testing
40a7556 Additional work for test fixes
5ca8bb0 fix: Add -y flag propagation and stop recursive promotion
6ee0cd3 Apply fix for pre-existing test failures
af28e0b Merge: Complete task 84 fix with main
137e370 cleanup and add updated icon
d228d42 Update tagline: WEAK LLM SUBMIT, STRONG TEAM SHIP
293b381 Update state machine: LIVE→DONE, add STAGING gate
87fc42b Move test files to tests/ folder with corrected paths
8706049 Use ✅/❌ icons consistently; update AGENTS.md directive
49d47a9 Update README to use hammer wrapper commands
87e284c Update install.sh to include hammer wrapper
48670ab Add hammer wrapper script
e5322d9 Improve README intro text readability
93a7dc3 Fix README formatting - move image below title
bf5d8a9 Restore Hammer text with checkmarks
f9e3e5e Hammer voice: rewrite tool outputs with dominant theme
d2f6582 Sync: pipeline branch fix from main
0077924 WIP: Auto-commit before promote to 80-task-fix-promote-tool-workflow-gate
b3bcc07 WIP: Auto-commit before promote to 80-task-fix-promote-tool-workflow-gate