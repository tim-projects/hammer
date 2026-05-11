import os
try:
    cols = os.get_terminal_size().columns
    print(f"Detected: {cols}")
except OSError:
    print("Fallback: 80")
