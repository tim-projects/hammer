import os
import time


def wait_for_file(filepath, timeout=5):
    """Wait for a file to exist on the filesystem."""
    start_time = time.time()
    while not os.path.exists(filepath):
        if time.time() - start_time > timeout:
            return False
        time.sleep(0.1)
    return True
