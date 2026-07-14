import subprocess
import os

# Create a patch for the task
# Use repo.py directly if needed, but for now let's try tasks audit
# Wait, audit requires a patch to exist.
# The previous list showed .patch files in .tasks/review/
# So first I need to move the task to REVIEW so that a patch is generated.

subprocess.run(
    ["python3", "tasks.py", "move", "163", "READY,PROGRESSING,TESTING,REVIEW"],
    check=True,
)
# This will generate a patch in .tasks/review/
# Let's check if it exists
if os.path.exists(".tasks/review/163.patch"):
    print("Patch created successfully")
    subprocess.run(["python3", "tasks.py", "audit", "163"], check=True)
else:
    print("Patch NOT created")
