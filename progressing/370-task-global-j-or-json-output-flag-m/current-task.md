---
Task: 370-task-global-j-or-json-output-flag-m
---

- Progress: Implemented wrapper-level JSON normalization: -j/--json is removed from arbitrary positions and passed canonically to the selected tool. Added JSON output handling for check and guard, preserved help precedence, documented the tool/command matrix in docs/JSON_FLAG_MATRIX.md, and added tests/test_global_json_flag.py. Validation: ./hammer check all passes.
- Findings: 
- Mitigations: 
