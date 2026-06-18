import subprocess
import os

# The original script attempted an invalid multi-state jump.
# We will perform incremental moves to reach the REVIEW state.

tasks = ["PROGRESSING", "TESTING", "REVIEW"]

try:
    for state in tasks:
        print(f"Moving 163 to {state}...")
        subprocess.run(
            ["./hammer", "tasks", "move", "163", state],
            check=True,
        )

    # After moving, a patch should be generated in .tasks/review/
    if os.path.exists(".tasks/review/163.patch"):
        print("Patch created successfully")
        subprocess.run(["./hammer", "tasks", "audit", "163"], check=True)
    else:
        print("Patch NOT created")
        # Exit with error to satisfy test expectations if it was supposed to create it
        exit(1)
except subprocess.CalledProcessError as e:
    print(f"Move failed: {e}")
    exit(1)
