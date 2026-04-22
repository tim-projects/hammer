with open("tests/test_tasks.py", "r") as f:
    lines = f.readlines()

new_lines = []
for line in lines:
    new_lines.append(line)
    if 'shutil.copy(os.path.join(self.base_dir, "repo.py"), self.repo_dir)' in line:
        new_lines.append(
            '        os.symlink(os.path.join(self.base_dir, "venv"), os.path.join(self.repo_dir, "venv"))\n'
        )
        new_lines.append(
            '        os.symlink(os.path.join(self.base_dir, "tasks_ai"), os.path.join(self.repo_dir, "tasks_ai"))\n'
        )
        new_lines.append('        tests_dir = os.path.join(self.repo_dir, "tests")\n')
        new_lines.append("        os.makedirs(tests_dir, exist_ok=True)\n")
        new_lines.append(
            '        with open(os.path.join(tests_dir, "test_dummy.py"), "w") as f:\n'
        )
        new_lines.append('            f.write("def test_dummy(): pass\\n")\n')
        new_lines.append(
            '        with open(os.path.join(self.repo_dir, "pyrightconfig.json"), "w") as f:\n'
        )
        new_lines.append('            json.dump({"exclude": ["tasks_ai"]}, f)\n')

with open("tests/test_tasks.py", "w") as f:
    f.writelines(new_lines)
