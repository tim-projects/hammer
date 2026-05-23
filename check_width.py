import os
def get_terminal_width():
    try:
        return os.get_terminal_size().columns
    except OSError:
        return 80
print(f"term_width = {get_terminal_width()}")
