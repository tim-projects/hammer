#!/usr/bin/env python3
import os
import subprocess
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tasks_ai.validator import Validator


def main():
    print("Validator imported")
    try:
        # Resolve the project root (a worktree counts) so the tools run against the right tree
        try:
            root = subprocess.check_output(
                ["git", "rev-parse", "--show-toplevel"], text=True
            ).strip()
        except Exception:  # noqa: BLE001
            root = "."
        validator = Validator(root)
        results = validator.run_all(False)
        print(f"Results: {results}")
    except Exception as e:  # noqa: BLE001
        print(f"Error: {e}")


if __name__ == "__main__":
    main()
