import re
with open('tasks_ai/cli.py', 'r') as f:
    content = f.read()

# Fix the main if-else block
content = re.sub(r' +if dev:', '        if dev:', content)
content = re.sub(r' +self.tasks_dir = "/tmp/.tasks"', '            self.tasks_dir = "/tmp/.tasks"', content)
content = re.sub(r' +if not os.path.exists\(self.tasks_dir\):', '            if not os.path.exists(self.tasks_dir):', content)
content = re.sub(r' +os.makedirs\(self.tasks_dir, exist_ok=True\)', '                os.makedirs(self.tasks_dir, exist_ok=True)', content)
content = re.sub(r' +else:', '        else:', content)

with open('tasks_ai/cli.py', 'w') as f:
    f.write(content)
