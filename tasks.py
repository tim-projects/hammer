import os
import subprocess
import sys
import argparse
import tempfile
from datetime import datetime
from pathlib import Path
import frontmatter

# Constants
TASKS_DIR = ".tasks"
TASKS_BRANCH = "tasks"

class TasksCLI:
    def __init__(self):
        self.root = self._get_git_root()
        self.tasks_path = os.path.join(self.root, TASKS_DIR)

    def _get_git_root(self):
        try:
            return subprocess.check_output(['git', 'rev-parse', '--show-toplevel'], 
                                         stderr=subprocess.DEVNULL).decode().strip()
        except subprocess.CalledProcessError:
            print("Error: Not a git repository.")
            sys.exit(1)

    def _run_git(self, args, cwd=None):
        cwd = cwd or self.root
        return subprocess.run(['git'] + args, cwd=cwd, capture_output=True, text=True)

    def _atomic_write(self, filepath, post):
        """Ensures the file is fully written before replacing the original."""
        dir_name = os.path.dirname(filepath)
        fd, temp_path = tempfile.mkstemp(dir=dir_name, text=True)
        try:
            with os.fdopen(fd, 'wb') as f:
                frontmatter.dump(post, f)
            os.replace(temp_path, filepath)
        except Exception as e:
            if os.path.exists(temp_path):
                os.remove(temp_path)
            raise e

    def init(self):
        """Initializes the tasks worktree and branch."""
        print(f"Checking for '{TASKS_BRANCH}' branch...")
        
        # Check if branch exists
        branches = self._run_git(['branch']).stdout
        if TASKS_BRANCH not in branches:
            print(f"Creating orphan branch: {TASKS_BRANCH}")
            # Create a clean branch with no history
            self._run_git(['checkout', '--orphan', TASKS_BRANCH])
            self._run_git(['reset', '--hard'])
            self._run_git(['commit', '--allow-empty', '-m', 'Initial tasks commit'])
            self._run_git(['checkout', '-']) # Return to previous branch

        # Add Worktree
        if not os.path.exists(self.tasks_path):
            print(f"Adding worktree at {TASKS_DIR}...")
            res = self._run_git(['worktree', 'add', TASKS_DIR, TASKS_BRANCH])
            if res.returncode != 0:
                print(f"Error adding worktree: {res.stderr}")
        else:
            print(f"Worktree already exists at {TASKS_DIR}")

    def create(self, title, task_type="task"):
        """Creates a new markdown task file with frontmatter."""
        # Sanitize title for filename
        clean_title = "".join(c if c.isalnum() else "-" for c in title.lower()).strip("-")
        filename = f"{task_type}_{clean_title[:30]}.md"
        filepath = os.path.join(self.tasks_path, filename)

        if os.path.exists(filepath):
            print(f"Error: Task file {filename} already exists.")
            return

        post = frontmatter.Post("", 
            Type=task_type,
            Title=title,
            Branch=clean_title[:30],
            Status="BACKLOG",
            Created=datetime.now().strftime("%Y-%m-%d %H:%M")
        )
        post.content = f"\n## Description\n{title}\n\n## Progress Logs\n- Created {post['Created']}\n"

        try:
            self._atomic_write(filepath, post)
            self._commit_task(filename, f"Add {task_type}: {title}")
            print(f"Successfully created: {filename}")
        except Exception as e:
            print(f"Failed to create task: {e}")

    def move(self, filename, new_status):
        """Updates task status, appends log, and commits."""
        filepath = os.path.join(self.tasks_path, filename)
        if not os.path.exists(filepath):
            # Fallback check for partial matches if user didn't type .md
            if not filename.endswith(".md"):
                filepath += ".md"
                filename += ".md"

        if not os.path.exists(filepath):
            print(f"Error: {filename} not found in {TASKS_DIR}/")
            return

        # Load and update
        post = frontmatter.load(filepath)
        old_status = post.get('Status', 'UNKNOWN')
        new_status = new_status.upper()
        
        post['Status'] = new_status
        log_entry = f"- {datetime.now().strftime('%Y-%m-%d %H:%M')}: {old_status} -> {new_status}"
        post.content += f"{log_entry}\n"

        try:
            self._atomic_write(filepath, post)
            res = self._commit_task(filename, f"Task {filename}: {old_status} -> {new_status}")
            
            if res.returncode == 0:
                print(f"Moved {filename}: {old_status} -> {new_status}")
            else:
                print(f"File updated but Git commit failed. Rolling back file...")
                self._run_git(['checkout', '--', filename], cwd=self.tasks_path)
        except Exception as e:
            print(f"Critical error during move: {e}")

    def list(self):
        """Displays all tasks organized by status."""
        if not os.path.exists(self.tasks_path):
            print("Tasks directory not found. Run 'init' first.")
            return

        files = [f for f in os.listdir(self.tasks_path) if f.endswith(".md")]
        if not files:
            print("No tasks found.")
            return

        print(f"{'STATUS':<15} | {'FILENAME':<30} | {'TITLE'}")
        print("-" * 70)
        for file in sorted(files):
            try:
                post = frontmatter.load(os.path.join(self.tasks_path, file))
                status = post.get('Status', 'N/A')
                title = post.get('Title', 'No Title')
                print(f"{status:<15} | {file:<30} | {title}")
            except Exception:
                continue

    def _commit_task(self, filename, message):
        """Stages and commits changes in the worktree."""
        self._run_git(['add', filename], cwd=self.tasks_path)
        return self._run_git(['commit', '-m', message], cwd=self.tasks_path)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Tasks CLI - Git Worktree Task Manager")
    subparsers = parser.add_subparsers(dest="command")

    # Command: init
    subparsers.add_parser("init", help="Initialize the .tasks worktree")

    # Command: list
    subparsers.add_parser("list", help="List all current tasks")
    
    # Command: create <title> [--type task|issue]
    create_parser = subparsers.add_parser("create", help="Create a new task")
    create_parser.add_argument("title", help="Human-readable title")
    create_parser.add_argument("--type", default="task", choices=["task", "issue"])

    # Command: move <filename> <status>
    move_parser = subparsers.add_parser("move", help="Update task status")
    move_parser.add_argument("filename", help="The .md filename")
    move_parser.add_argument("status", help="New status (e.g. PROGRESSING, TESTING)")

    args = parser.parse_args()
    cli = TasksCLI()

    if args.command == "init":
        cli.init()
    elif args.command == "create":
        cli.create(args.title, args.type)
    elif args.command == "move":
        cli.move(args.filename, args.status)
    elif args.command == "list":
        cli.list()
    else:
        parser.print_help()
