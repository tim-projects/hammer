import subprocess
def get_remote():
    res = subprocess.run(["git", "remote"], capture_output=True, text=True)
    remotes = res.stdout.split()
    if "origin" in remotes:
        return "origin"
    return remotes[0] if remotes else "origin"
