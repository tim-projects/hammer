
repo_file = "tests/test_tasks.py"
with open(repo_file, "r") as f:
    lines = f.readlines()

new_lines = []
for line in lines:
    new_lines.append(line)
    if "self.script_path = os.path.join(self.base_dir, \"tasks.py\")" in line:
        new_lines.append("        shutil.copy(os.path.join(self.base_dir, \"check.py\"), self.repo_dir)\n")
        new_lines.append("        shutil.copy(os.path.join(self.base_dir, \"repo.py\"), self.repo_dir)\n")
        new_lines.append("        os.symlink(os.path.join(self.base_dir, \"venv\"), os.path.join(self.repo_dir, \"venv\"))\n")
        new_lines.append("        os.symlink(os.path.join(self.base_dir, \"tasks_ai\"), os.path.join(self.repo_dir, \"tasks_ai\"))\n")

with open(repo_file, "w") as f:
    f.writelines(new_lines)
