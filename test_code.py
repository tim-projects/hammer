import os
import shutil
def get_terminal_width():
    return shutil.get_terminal_size(fallback=(80, 24)).columns
print(get_terminal_width())
