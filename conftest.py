"""Deterministic `import tasks_ai` under pytest.

pytest prepends the test file's basedir (tests/) to sys.path. A stale tracked
tasks_ai snapshot used to live there and shadow the real package; keep the
project root at the front so every test imports the project's package without
per-file sys.path hacks.
"""

import os
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))

while ROOT in sys.path:
    sys.path.remove(ROOT)
sys.path.insert(0, ROOT)

# The four root-level scratch scripts are tracked but are not part of the suite:
# each one runs ad-hoc module-level code that crashes on import (test_is_merged.py
# calls git against a MagicMock cwd), which aborts collection for a bare `pytest`.
# Task 368 owns their removal; naming them here keeps collection clean until then.
collect_ignore = [
    "test_create_logic.py",
    "test_is_merged.py",
    "test_pairing_logic.py",
    "test_regex.py",
]
