lines = open("repo.py", "r").readlines()
new_lines = []
skip = False
for i, line in enumerate(lines):
    if "def check_remote_exists():" in line:
        new_lines.append(line)
        new_lines.append(
            '    result = run(["git", "remote", "get-url", PRIMARY_REMOTE], check=False, capture=True)\n'
        )
        new_lines.append("    if result.returncode != 0:\n")
        skip = True
        continue
    if skip and (
        'if FLAGS["yes"]:' in line or 'warn(f"No' in line or "return False" in line
    ):
        new_lines.append(line)
    elif skip and ("    return True" in line or "def" in line):
        skip = False
        new_lines.append(line)
    elif not skip:
        new_lines.append(line)

with open("repo.py", "w") as f:
    f.writelines(new_lines)
