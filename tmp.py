with open('repo.py', 'r') as f:
    lines = f.readlines()

new_lines = []
for line in lines:
    if "if result.returncode != 0:" in line and "check_remote_exists" in "".join(new_lines[-5:]):
        new_lines.append(line.replace("if result.returncode != 0:", "print(f'DEBUG: result.returncode={result.returncode}, PRIMARY_REMOTE={PRIMARY_REMOTE}'); if result.returncode != 0:"))
    else:
        new_lines.append(line)
