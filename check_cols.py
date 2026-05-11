import os
import sys
# Simulate what hammer does
def get_terminal_width():
    try:
        return os.get_terminal_size().columns
    except OSError:
        return 80
print(get_terminal_width())
