#!/usr/bin/env python3
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tasks_ai.validator import Validator


def main():
    print("Validator imported")
    try:
        validator = Validator(".")
        results = validator.run_all(False)
        print(f"Results: {results}")
    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    main()
