#!/usr/bin/env python3
import os
import subprocess
import sys
import argparse
import tempfile
import re
import json
from datetime import datetime, timedelta
from pathlib import Path

# Constants
TASKS_DIR = "tasks"
LOGS_DIR = "logs"
TASKS_BRANCH = "tasks"
CURRENT_TASK_FILENAME = "current-task.md"

STATE_FOLDERS = {
    "BACKLOG": "backlog", "READY": "ready", "PROGRESSING": "progressing",
    "BLOCKED": "blocked", "TESTING": "testing", "REVIEW": "review",
    "STAGING": "staging", "LIVE": "live", "ARCHIVED": "archived"
}

ALLOWED_TRANSITIONS = {
    "BACKLOG": ["READY"],
    "READY": ["PROGRESSING", "BLOCKED"],
    "PROGRESSING": ["TESTING", "BLOCKED"],
    "TESTING": ["REVIEW", "BLOCKED"],
    "REVIEW": ["STAGING", "TESTING", "BLOCKED"],
    "STAGING": ["LIVE", "REVIEW", "BLOCKED"],
    "LIVE": ["ARCHIVED", "STAGING", "BLOCKED"],
    "BLOCKED": ["READY", "PROGRESSING", "TESTING", "REVIEW", "STAGING", "LIVE"],
}

KEY_MAP = {
    "Ti": "Title", "St": "State", "Cr": "Created",
    "Bl": "BlockedBy", "Pr": "Priority", "Ar": "ArchivedAt"
}

TASK_SCOPE = "## Scope\n- Requirements: \n- Success/Acceptance Criteria: \n"
ISSUE_SCOPE = "## Scope\n- Symptom: \n- Reproduction Steps: \n- Root Cause (if known): \n- Fix/Test Plan: \n"
DUMP_TEMPLATE = "---\nTask: {task_file}\n---\n## Notes\n- Progress: \n- Findings: \n- Mitigations: \n"

class Post:
    """Internal replacement for frontmatter.Post"""
    def __init__(self, content, **metadata):
        self.content = content
        self.metadata = metadata
    def __getitem__(self, key): return self.metadata.get(key)
    def __setitem__(self, key, value): self.metadata[key] = value
    def get(self, key, default=None): return self.metadata.get(key, default)

class FM:
    """Minimal YAML-like frontmatter parser for basic keys and lists."""
    @staticmethod
    def load(filepath):
        if not os.path.exists(filepath): return Post("", **{})
        with open(filepath, 'r', encoding='utf-8') as f:
            try: lines = f.readlines()
            except Exception: return Post("", **{})
        if not lines or lines[0].strip() != '---': return Post("".join(lines), **{})
        meta, content_start = {}, -1
        for i in range(1, len(lines)):
            line = lines[i].strip()
            if line == '---':
                content_start = i + 1
                break
            if ':' in line:
                k, v = [s.strip() for s in line.split(':', 1)]
                if v.startswith('[') and v.endswith(']'):
                    inner = v[1:-1].strip()
                    meta[k] = [item.strip().strip("'").strip('"') for item in inner.split(',')] if inner else []
                elif v.isdigit(): meta[k] = int(v)
                else: meta[k] = v.strip("'").strip('"')
        return Post("".join(lines[content_start:]) if content_start != -1 else "", **meta)

    @staticmethod
    def dump(post, f):
        f.write(b"---\n")
        for k, v in post.metadata.items():
            if isinstance(v, list): val = "[" + ", ".join(f'"{item}"' for item in v) + "]"
            else: val = v
            f.write(f"{k}: {val}\n".encode('utf-8'))
        f.write(b"---\n")
        content = post.content
        if content and not content.startswith('\n'): f.write(b"\n")
        f.write(content.encode('utf-8'))

class TasksCLI:
    def __init__(self, as_json=False):
        self.as_json = as_json
        self.output_messages = []
        self.root = self._get_git_root()
        self.tasks_path = os.path.join(self.root, TASKS_DIR)
        self.logs_path = os.path.join(self.tasks_path, LOGS_DIR)
        if os.path.exists(self.tasks_path):
            self._auto_archive()

    def _get_git_root(self):
        try:
            return subprocess.check_output(['git', 'rev-parse', '--show-toplevel'], 
                                         stderr=subprocess.DEVNULL).decode().strip()
        except subprocess.CalledProcessError:
            self.error("Not a git repository.")
            sys.exit(1)

    def _run_git(self, args, cwd=None):
        cwd = cwd or self.root
        return subprocess.run(['git'] + args, cwd=cwd, capture_output=True, text=True)

    def _parse_filename(self, filename):
        name_part = filename.rsplit('.', 1)[0]
        if '_' in name_part: return name_part.split('_', 1)
        return "task", name_part

    def _atomic_write(self, filepath, post_or_content):
        dir_name = os.path.dirname(filepath)
        os.makedirs(dir_name, exist_ok=True)
        fd, temp_path = tempfile.mkstemp(dir=dir_name, text=False)
        try:
            with os.fdopen(fd, 'wb') as f:
                if hasattr(post_or_content, 'metadata'):
                    FM.dump(post_or_content, f)
                else:
                    if isinstance(post_or_content, str): f.write(post_or_content.encode('utf-8'))
                    else: f.write(post_or_content)
            os.replace(temp_path, filepath)
        except Exception as e:
            if os.path.exists(temp_path): os.remove(temp_path)
            raise e

    def log(self, message):
        if self.as_json: self.output_messages.append(message)
        else: print(message)

    def error(self, message):
        if self.as_json:
            print(json.dumps({"success": False, "error": message, "messages": self.output_messages}))
            sys.exit(1)
        else:
            print(f"Error: {message}", file=sys.stderr)
            sys.exit(1)

    def finish(self, data=None):
        if self.as_json:
            print(json.dumps({"success": True, "messages": self.output_messages, "data": data}, indent=2))
        sys.exit(0)

    def _auto_archive(self):
        live_dir = os.path.join(self.tasks_path, STATE_FOLDERS["LIVE"])
        if not os.path.exists(live_dir): return
        now = datetime.now()
        for file in os.listdir(live_dir):
            if not file.endswith(".md"): continue
            log_path = os.path.join(self.logs_path, file)
            if os.path.exists(log_path):
                with open(log_path, 'r') as f: lines = f.readlines()
                live_date = None
                for line in reversed(lines):
                    if "->LIVE" in line:
                        match = re.search(r'- (\d{6} \d{2}:\d{2}):', line)
                        if match:
                            live_date = datetime.strptime(match.group(1), '%y%m%d %H:%M')
                            break
                if live_date and (now - live_date) > timedelta(days=7):
                    self.log(f"Auto-archiving: {file}")
                    self._move_logic(file, "ARCHIVED")

    def init(self):
        branches = self._run_git(['branch']).stdout
        if TASKS_BRANCH not in branches:
            self._run_git(['checkout', '--orphan', TASKS_BRANCH])
            self._run_git(['reset', '--hard'])
            self._run_git(['commit', '--allow-empty', '-m', 'Initial tasks commit'])
            self._run_git(['checkout', '-'])
        if not os.path.exists(self.tasks_path):
            self._run_git(['worktree', 'add', TASKS_DIR, TASKS_BRANCH])
        for folder in list(STATE_FOLDERS.values()) + [LOGS_DIR]:
            p = os.path.join(self.tasks_path, folder)
            if not os.path.exists(p):
                os.makedirs(p)
                Path(os.path.join(p, ".gitkeep")).touch()
                self._run_git(['add', os.path.join(folder, ".gitkeep")], cwd=self.tasks_path)
        st = self._run_git(['status', '--porcelain'], cwd=self.tasks_path)
        if st.stdout: self._run_git(['commit', '-m', 'Init tasks folders'], cwd=self.tasks_path)
        gitignore_path = os.path.join(self.root, ".gitignore")
        ignore_line = f"{TASKS_DIR}/"
        if os.path.exists(gitignore_path):
            with open(gitignore_path, 'r') as f: content = f.read()
            if ignore_line not in content:
                with open(gitignore_path, 'a') as f: f.write(f"\n{ignore_line}\n")
        else:
            with open(gitignore_path, 'w') as f: f.write(f"{ignore_line}\n")
        self.log("Tasks initialized.")
        self.finish()

    def _append_log(self, filename, entry):
        log_file = os.path.join(self.logs_path, filename)
        timestamp = datetime.now().strftime('%y%m%d %H:%M')
        with open(log_file, 'a') as f: f.write(f"- {timestamp}: {entry}\n")
        self._run_git(['add', os.path.join(LOGS_DIR, filename)], cwd=self.tasks_path)

    def create(self, title, task_type="task", priority=None):
        clean_title = "".join(c if c.isalnum() else "-" for c in title.lower()).strip("-")
        branch_name = clean_title[:30]; filename = f"{task_type}_{branch_name}.md"
        filepath = os.path.join(self.tasks_path, STATE_FOLDERS["BACKLOG"], filename)
        if any(os.path.exists(os.path.join(self.tasks_path, f, filename)) for f in STATE_FOLDERS.values()):
            self.error(f"Task {filename} exists.")
        if priority is None: priority = 1 if task_type == "issue" else 2
        post = Post(f"{title}\n\n## Desc\n{title}\n\n{TASK_SCOPE if task_type == 'task' else ISSUE_SCOPE}", 
            Ti=title, St="BACKLOG", Cr=datetime.now().strftime("%y%m%d %H:%M"), Bl=[], Pr=priority
        )
        try:
            self._atomic_write(filepath, post)
            self._append_log(filename, "Cr")
            self._run_git(['add', os.path.join(STATE_FOLDERS["BACKLOG"], filename), os.path.join(LOGS_DIR, filename)], cwd=self.tasks_path)
            self._run_git(['commit', '-m', f"Add {task_type}: {title}"], cwd=self.tasks_path)
            self.log(f"Created: {filename}")
            self.finish({"file": filename, "path": os.path.relpath(filepath, self.root)})
        except Exception as e: self.error(str(e))

    def find_task(self, filename):
        if not filename.endswith(".md"): filename += ".md"
        for state, folder in STATE_FOLDERS.items():
            filepath = os.path.join(self.tasks_path, folder, filename)
            if os.path.exists(filepath): return filepath, state
        return None, None

    def get_active_task(self, filename=None):
        if filename:
            filepath, _ = self.find_task(filename)
            if filepath: return filepath, FM.load(filepath)
            return None, None
        prog_dir = os.path.join(self.tasks_path, STATE_FOLDERS["PROGRESSING"])
        if os.path.exists(prog_dir):
            files = [f for f in os.listdir(prog_dir) if f.endswith(".md")]
            if files:
                filepath = os.path.join(prog_dir, files[0])
                return filepath, FM.load(filepath)
        dump_path = os.path.join(self.tasks_path, CURRENT_TASK_FILENAME)
        if os.path.exists(dump_path):
            try:
                dump = FM.load(dump_path)
                if dump.get('Task'): return self.get_active_task(dump.get('Task'))
            except Exception: pass
        return None, None

    def checkpoint(self, filename=None):
        filepath, post = self.get_active_task(filename)
        if not filepath: self.error("No active task found.")
        self.log(f"Checkpointing {os.path.basename(filepath)}...")
        if self._sync_task_content(filepath, post):
            self._atomic_write(filepath, post)
            self._run_git(['add', os.path.relpath(filepath, self.tasks_path)], cwd=self.tasks_path)
            self._run_git(['commit', '-m', f"Cp: {os.path.basename(filepath)}"], cwd=self.tasks_path)
            self.log("Done.")
            self.finish()
        else:
            self.log("No changes.")
            self.finish()

    def _sync_task_content(self, filepath, post, is_final=False):
        _, branch = self._parse_filename(os.path.basename(filepath))
        updated = False
        res = self._run_git(['log', branch, f'^{self._get_default_branch()}', '--oneline'])
        commits = res.stdout.strip() if res.returncode == 0 else ""
        if commits:
            header = "## Final Commits" if is_final else "## Commits"
            old_header = "## Commits" if is_final else "## Final Commits"
            if is_final and old_header in post.content:
                 post.content = re.sub(rf"{old_header}\n.*?(?=\n##|$)", "", post.content, flags=re.DOTALL).strip() + "\n"
            if header not in post.content: post.content = post.content.strip() + f"\n\n{header}\n"
            pattern = rf"{header}\n.*?(?=\n##|$)"
            if re.search(pattern, post.content, re.DOTALL):
                post.content = re.sub(pattern, f"{header}\n{commits}", post.content, flags=re.DOTALL)
            else: post.content = post.content.strip() + f"\n\n{header}\n{commits}\n"
            updated = True
        dump_path = os.path.join(self.tasks_path, CURRENT_TASK_FILENAME)
        if os.path.exists(dump_path):
            try:
                dump = FM.load(dump_path)
                if dump.get('Task') == os.path.basename(filepath):
                    dump_content = dump.content.strip()
                    if dump_content and "Progress:" in dump_content:
                        if "## Notes" not in post.content: post.content = post.content.strip() + f"\n\n## Notes\n"
                        pattern = r"## Notes\n.*?(?=\n##|$)"
                        if re.search(pattern, post.content, re.DOTALL):
                            post.content = re.sub(pattern, f"## Notes\n{dump_content}", post.content, flags=re.DOTALL)
                        else: post.content = post.content.strip() + f"\n\n## Notes\n{dump_content}\n"
                        updated = True
            except Exception: pass
        return updated

    def _get_default_branch(self):
        for b in ["main", "master"]:
            if self._run_git(['rev-parse', '--verify', b]).returncode == 0: return b
        return "main"

    def link(self, filename, blocked_by_filename):
        f1, _ = self.find_task(filename); f2, _ = self.find_task(blocked_by_filename)
        if not f1 or not f2: self.error("Task or blocker not found.")
        post = FM.load(f1); bl = post.get('Bl', []); b_name = os.path.basename(f2)
        if b_name not in bl:
            bl.append(b_name); post['Bl'] = bl; self._atomic_write(f1, post)
            self._run_git(['add', os.path.relpath(f1, self.tasks_path)], cwd=self.tasks_path)
            self._run_git(['commit', '-m', f"Lk {filename}->{b_name}"], cwd=self.tasks_path)
            self.log(f"Linked: {filename} blocked by {b_name}")
        self.finish()

    def move(self, filename, new_status):
        self._move_logic(filename, new_status)
        self.finish()

    def _move_logic(self, filename, new_status):
        new_status = new_status.upper()
        filepath, current_state = self.find_task(filename)
        if not filepath: self.error(f"Task {filename} not found.")
        if current_state == new_status: return
        if new_status not in ALLOWED_TRANSITIONS.get(current_state, []):
            self.error(f"Forbidden: {current_state}->{new_status}.")
        post = FM.load(filepath)
        if new_status == "PROGRESSING":
            for b in post.get('Bl', []):
                _, bs = self.find_task(b)
                if bs != "ARCHIVED": self.error(f"Blocked by {b} ({bs})")
            prog_dir = os.path.join(self.tasks_path, STATE_FOLDERS["PROGRESSING"])
            if os.path.exists(prog_dir) and [f for f in os.listdir(prog_dir) if f.endswith(".md")]:
                self.error("Busy with another task.")
        self.log(f"Checkpointing {os.path.basename(filepath)}...")
        self._sync_task_content(filepath, post, is_final=(new_status == "ARCHIVED"))
        if new_status == "ARCHIVED" and "## Final Commits" not in post.content:
            self.error("No commits found for archival.")
        post['St'] = new_status
        self._append_log(os.path.basename(filepath), f"{current_state}->{new_status}")
        new_filepath = os.path.join(self.tasks_path, STATE_FOLDERS[new_status], os.path.basename(filepath))
        try:
            self._atomic_write(new_filepath, post)
            self._run_git(['rm', os.path.relpath(filepath, self.tasks_path)], cwd=self.tasks_path)
            self._run_git(['add', os.path.relpath(new_filepath, self.tasks_path), os.path.join(LOGS_DIR, os.path.basename(filepath))], cwd=self.tasks_path)
            self._run_git(['commit', '-m', f"Mv {os.path.basename(filepath)}: {current_state}->{new_status}"], cwd=self.tasks_path)
            self.log(f"Moved: {current_state}->{new_status}")
            dump_path = os.path.join(self.tasks_path, CURRENT_TASK_FILENAME)
            if new_status == "PROGRESSING":
                self._atomic_write(dump_path, DUMP_TEMPLATE.format(task_file=os.path.basename(new_filepath)))
            if new_status == "ARCHIVED" and os.path.exists(dump_path):
                try:
                    d = FM.load(dump_path)
                    if d.get('Task') == os.path.basename(new_filepath): os.remove(dump_path)
                except Exception: pass
        except Exception as e: self.error(str(e))

    def current(self, filename=None):
        filepath, post = self.get_active_task(filename)
        if not filepath: self.error("No active task found.")
        tn = os.path.basename(filepath); tt, br = self._parse_filename(tn)
        data = {
            "file": os.path.relpath(filepath, self.root), "name": tn, "type": tt, "branch": br,
            "metadata": {KEY_MAP.get(k, k): v for k, v in post.metadata.items()},
            "log_file": os.path.relpath(os.path.join(self.logs_path, tn), self.root)
        }
        dp = os.path.join(self.tasks_path, CURRENT_TASK_FILENAME)
        if os.path.exists(dp):
            try:
                d = FM.load(dp)
                if d.get('Task') == tn: data["dump"] = {"file": os.path.relpath(dp, self.root), "content": d.content.strip()}
            except Exception: pass
        
        if not self.as_json:
            print(f"# TASK: {data['metadata']['Title']}\n- **File**: `{data['file']}`\n- **Type**: {data['type']} | **Branch**: `{data['branch']}`")
            for k, v in data['metadata'].items():
                if k != "Title": print(f"- **{k}**: {v}")
            print(f"- **Logs**: `{data['log_file']}`")
            if "dump" in data: print(f"\n## Active Progress (`{data['dump']['file']}`)\n{data['dump']['content']}")
        else: self.finish(data)

    def list(self, show_all=False):
        if not os.path.exists(self.tasks_path): self.error("Init required.")
        all_data = {}
        for state, folder in STATE_FOLDERS.items():
            if state == "ARCHIVED" and not show_all: continue
            fp = os.path.join(self.tasks_path, folder)
            if not os.path.exists(fp): continue
            files = [f for f in os.listdir(fp) if f.endswith(".md")]
            if not files: continue
            tasks = []
            for file in sorted(files):
                try:
                    with open(os.path.join(fp, file), 'r') as f: lines = f.readlines()
                    cs = False; summary = "No content"
                    for l in lines:
                        if l.strip() == "---":
                            if not cs: cs = True
                            else: cs = "CONTENT"
                        elif cs == "CONTENT" and l.strip():
                            summary = l.strip(); break
                    post = FM.load(os.path.join(fp, file))
                    tt, tb = self._parse_filename(file)
                    tasks.append({"p": post.get('Pr', 9), "file": file, "type": tt, "branch": tb, "summary": summary[:60], "blocked_by": post.get('Bl', [])})
                except Exception: pass
            tasks.sort(key=lambda x: (x['p'], x['file']))
            if tasks: all_data[state] = tasks
        
        if self.as_json: self.finish(all_data)
        else:
            for state, tasks in all_data.items():
                print(f"\n### {state}\n| P | Summary | Type | Branch | Blocked By |\n|---|---------|------|--------|------------|")
                for t in tasks:
                    bl = ", ".join(t['blocked_by']) if t['blocked_by'] else "-"
                    print(f"| {t['p']} | {t['summary']} | {t['type']} | `{t['branch']}` | {bl} |")
            self.finish()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        prog="tasks",
        description="Tasks AI: An agent-optimized task manager for Git repositories.",
        epilog="Agent Guidance: Use the global --json flag for all operations to receive structured, parseable data."
    )
    parser.add_argument("--json", action="store_true", help="Enable unbroken JSON output for AI agent integration.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("init", help="Initialize the .tasks worktree and orphan branch. Required first step.")
    list_p = subparsers.add_parser("list", help="List active tasks sorted by priority. ARCHIVED is hidden by default.")
    list_p.add_argument("--all", action="store_true", help="Include ARCHIVED tasks in the output.")
    cur_p = subparsers.add_parser("current", help="Show full metadata, file paths, and active progress for a task.")
    cur_p.add_argument("filename", nargs="?", help="Specific task filename (e.g. task_branch.md). Defaults to the task in PROGRESSING.")
    cp_p = subparsers.add_parser("checkpoint", help="Force-sync branch commits and current-task.md notes into the task file.")
    cp_p.add_argument("filename", nargs="?", help="Task to checkpoint. Defaults to the one in PROGRESSING.")
    lk_p = subparsers.add_parser("link", help="Establish a blocking dependency between tasks.")
    lk_p.add_argument("filename", help="The task being blocked.")
    lk_p.add_argument("blocked_by", help="The task causing the blockage.")
    cr_p = subparsers.add_parser("create", help="Create a new task or issue in BACKLOG with mandatory requirement sections.")
    cr_p.add_argument("title", help="Human-readable title of the task.")
    cr_p.add_argument("--type", default="task", choices=["task", "issue"], help="Item category. Issues default to Priority 1.")
    cr_p.add_argument("--priority", "-p", type=int, help="Override default priority (lower = higher priority).")
    mv_p = subparsers.add_parser("move", help="Transition a task to a new state. Enforces state machine and auto-syncs progress.")
    mv_p.add_argument("filename", help="Task filename to move.")
    mv_p.add_argument("status", help="Target status: BACKLOG, READY, PROGRESSING, TESTING, REVIEW, STAGING, LIVE, BLOCKED, ARCHIVED.")
    args = parser.parse_args()
    cli = TasksCLI(as_json=args.json)
    if args.command == "init": cli.init()
    elif args.command == "create": cli.create(args.title, args.type, args.priority)
    elif args.command == "move": cli.move(args.filename, args.status)
    elif args.command == "list": cli.list(show_all=args.all)
    elif args.command == "current": cli.current(args.filename)
    elif args.command == "checkpoint": cli.checkpoint(args.filename)
    elif args.command == "link": cli.link(args.filename, args.blocked_by)
