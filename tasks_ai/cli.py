# tasks_ai/cli.py
import os
import subprocess
import sys
import tempfile
import re
import textwrap
import json
import shutil
import random
import string
import fcntl
from typing import cast
from datetime import datetime, timedelta
from pathlib import Path

from .constants import (
    TASKS_DIR,
    TASKS_BRANCH,
    CURRENT_TASK_FILENAME,
    STATE_FOLDERS,
    ALLOWED_TRANSITIONS,
    KEY_MAP,
)
from .models import Task
from .file_manager import FM


def get_terminal_width():
    try:
        return os.get_terminal_size().columns
    except OSError:
        return 80


class TasksCLI:
    def __init__(self, as_json=False, command=None, quiet=False, dev=False):
        self.as_json = as_json
        self.quiet = quiet
        self.dev = dev
        self.output_messages = []
        self.root = self._get_git_root()

        # Determine tasks directory
        self.tasks_dir = TASKS_DIR
        if dev:
            self.tasks_dir = "/tmp/.tasks"
            if not os.path.exists(self.tasks_dir):
                os.makedirs(self.tasks_dir, exist_ok=True)
        else:
            # Check pyproject.toml for override first
            pyproject_path = os.path.join(self.root, "pyproject.toml")
            if os.path.exists(pyproject_path):
                try:
                    import toml

                    with open(pyproject_path, "r") as f:
                        pyproject_data = toml.load(f)
                        self.tasks_dir = (
                            pyproject_data.get("tool", {})
                            .get("tasks_ai", {})
                            .get("tasks_dir", self.tasks_dir)
                        )
                except ImportError:
                    pass
                except Exception:
                    pass

        if os.path.isabs(self.tasks_dir):
            self.tasks_path = self.tasks_dir
        else:
            self.tasks_path = os.path.join(self.root, self.tasks_dir)

        # Now that self.tasks_path is set, we can check .tasks/config.yaml if not in dev mode
        if not dev:
            cfg = self._get_config()
            if cfg and isinstance(cfg, dict) and "tasks_dir" in cfg:
                td = cfg["tasks_dir"]
                if td:
                    self.tasks_dir = str(td)
                    if os.path.isabs(self.tasks_dir):
                        self.tasks_path = self.tasks_dir
                    else:
                        self.tasks_path = os.path.join(self.root, self.tasks_dir)
        self.logs_path = os.path.join(self.tasks_path, "logs")
        if os.path.exists(self.tasks_path):
            self._auto_archive()
            if command and command != "delete":
                self._clear_delete_marks()

    def _clear_delete_marks(self):
        updated = False
        for state, folder in STATE_FOLDERS.items():
            dir_path = os.path.join(self.tasks_path, folder)
            if not os.path.exists(dir_path):
                continue
            for item in os.listdir(dir_path):
                if item == ".gitkeep":
                    continue
                path = os.path.join(dir_path, item)
                task = FM.load(path)
                if task and task.metadata and "DeleteCode" in task.metadata:
                    del task.metadata["DeleteCode"]
                    self._atomic_write(path, task)
                    updated = True
        if updated:
            self._run_git(["add", "--all"], cwd=self.tasks_path)
            self._run_git(
                ["commit", "--allow-empty", "-m", "Clear delete marks"],
                cwd=self.tasks_path,
            )

    def _get_git_root(self):
        try:
            return (
                subprocess.check_output(
                    ["git", "rev-parse", "--show-toplevel"], stderr=subprocess.DEVNULL
                )
                .decode()
                .strip()
            )
        except subprocess.CalledProcessError:
            self.error("Not a git repository.")
            sys.exit(1)

    def _run_git(self, args, cwd=None):
        cwd = cwd or self.root
        result = subprocess.run(["git"] + args, cwd=cwd, capture_output=True, text=True)

        # If in dev mode and command fails in tasks_path, it might not be a git repo
        if result.returncode != 0 and self.dev and cwd == self.tasks_path:
            return result

        if result.returncode == 0:
            cmd = args[0]
            if cmd == "checkout":
                branch = args[-1]
                if "-b" in args:
                    self.log(f"Git: Created and switched to branch '{branch}'")
                else:
                    self.log(f"Git: Switched to branch '{branch}'")
            elif cmd == "commit":
                msg = ""
                if "-m" in args:
                    idx = args.index("-m")
                    msg = f": {args[idx + 1]}"
                self.log(f"Git: Committed changes{msg}")
            elif cmd == "add":
                self.log("Git: Staged changes")
            elif cmd == "push":
                remote = args[1] if len(args) > 1 else ""
                branch = args[2] if len(args) > 2 else ""
                self.log(f"Git: Pushed {branch} to {remote}")
            elif cmd == "branch" and ("-d" in args or "-D" in args):
                branch = args[-1]
                self.log(f"Git: Deleted branch '{branch}'")
            elif cmd == "merge":
                self.log(f"Git: Merged '{args[-1]}'")
            elif cmd == "worktree" and "add" in args:
                self.log(f"Git: Added worktree at '{args[args.index('add') + 1]}'")

        return result

    def _run_repo(self, args, cwd=None):
        cwd = cwd or self.root
        repo_path = os.path.join(self.root, "repo")
        result = subprocess.run(
            [repo_path] + args, cwd=cwd, capture_output=True, text=True
        )
        return result

    def _parse_filename(self, name):
        if not name:
            return "task", ""
        name_part = str(name).rsplit(".", 1)[0]
        if "-" in name_part:
            parts = name_part.split("-", 2)
            if len(parts) >= 3:
                return parts[1], name_part
        if "_" in name_part:
            return name_part.split("_", 1)
        return "task", name_part

    def _atomic_write(self, path, task_or_content):
        if path.endswith(".md"):
            dir_name = os.path.dirname(path)
            os.makedirs(dir_name, exist_ok=True)
            fd, temp_path = tempfile.mkstemp(dir=dir_name, text=False)
            try:
                with os.fdopen(fd, "w") as f:
                    if hasattr(task_or_content, "metadata"):
                        FM.dump(task_or_content, path)
                        return
                    else:
                        if isinstance(task_or_content, str):
                            f.write(task_or_content)
                        else:
                            f.write(task_or_content.decode("utf-8"))
                os.replace(temp_path, path)
            except Exception as e:
                if os.path.exists(temp_path):
                    os.remove(temp_path)
                raise e
            return

        temp_dir = tempfile.mkdtemp(dir=os.path.dirname(path.rstrip("/")))
        try:
            shutil.rmtree(temp_dir)
            FM.dump(task_or_content, temp_dir)
            if os.path.exists(path):
                shutil.rmtree(path)
            os.rename(temp_dir, path)
        except Exception as e:
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)
            raise e

    def log(self, message):
        if self.as_json:
            self.output_messages.append(message)
        elif not self.quiet:
            print(message)

    def error(self, message, hint=None):
        if hint:
            message = f"{message} | HINT: {hint}"
        if self.quiet:
            pass
        elif self.as_json:
            print(
                json.dumps(
                    {
                        "success": False,
                        "error": message,
                        "messages": self.output_messages,
                    }
                )
            )
            sys.exit(1)
        else:
            print(f"Error: {message}", file=sys.stderr)
            sys.exit(1)

    def finish(self, data=None):
        if self.quiet:
            pass
        elif self.as_json:
            print(
                json.dumps(
                    {"success": True, "messages": self.output_messages, "data": data},
                    indent=2,
                )
            )
        if not hasattr(sys, "_called_from_test"):
            sys.exit(0)

    def _has_incomplete_checkboxes(self, task_path):
        if not os.path.isdir(task_path):
            return False
        for filename in os.listdir(task_path):
            if not filename.endswith(".md"):
                continue
            filepath = os.path.join(task_path, filename)
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read()
            if re.search(r"^- \[ \]", content, re.MULTILINE):
                return True
        return False

    def _auto_archive(self):
        live_dir = os.path.join(self.tasks_path, STATE_FOLDERS["LIVE"])
        if not os.path.exists(live_dir):
            return
        now = datetime.now()
        for item in os.listdir(live_dir):
            if item == ".gitkeep":
                continue
            path = os.path.join(live_dir, item)
            if os.path.isdir(path):
                log_path = os.path.join(path, "activity.log")
                if os.path.exists(log_path):
                    with open(log_path, "r", encoding="utf-8") as f:
                        lines = f.readlines()
                    live_date = None
                    for line in reversed(lines):
                        if "->LIVE" in line:
                            match = re.search(r"- (\d{6} \d{2}:\d{2}):", line)
                            if match:
                                live_date = datetime.strptime(
                                    match.group(1), "%y%m%d %H:%M"
                                )
                                break
                    if live_date and (now - live_date) > timedelta(days=7):
                        if self._has_incomplete_checkboxes(path):
                            self.log(
                                f"Skipping archive for {item}: incomplete checkboxes"
                            )
                            continue
                        self.log(f"Auto-archiving: {item}")
                        self._move_logic(item, "ARCHIVED", force=True, yes=False)

    def init(self):
        if self.dev:
            # For dev mode, just create folders, no git worktree
            for folder in list(STATE_FOLDERS.values()):
                p = os.path.join(self.tasks_path, folder)
                if not os.path.exists(p):
                    os.makedirs(p, exist_ok=True)
                    Path(os.path.join(p, ".gitkeep")).touch()

            counter_file = os.path.join(self.tasks_path, ".task_counter")
            if not os.path.exists(counter_file):
                with open(counter_file, "w") as f:
                    f.write("0")

            self.log(f"Dev tasks initialized at {self.tasks_path}")
            self.finish()
            return

        original_branch = self._run_git(["branch", "--show-current"]).stdout.strip()
        branches = self._run_git(["branch"]).stdout
        if TASKS_BRANCH not in branches:
            self._run_git(["checkout", "--orphan", TASKS_BRANCH])
            self._run_git(["reset", "--hard"])
            self._run_git(["commit", "--allow-empty", "-m", "Initial tasks commit"])
            if original_branch:
                self._run_git(["checkout", original_branch])
            else:
                self._run_git(["checkout", "-"])
        is_worktree = False
        if os.path.exists(self.tasks_path):
            wt_res = self._run_git(["worktree", "list", "--porcelain"])
            if self.tasks_path in wt_res.stdout:
                is_worktree = True

        if not is_worktree:
            if os.path.exists(self.tasks_path):
                if os.path.isdir(self.tasks_path):
                    shutil.rmtree(self.tasks_path)
                else:
                    os.remove(self.tasks_path)
            self._run_git(["worktree", "add", self.tasks_path, TASKS_BRANCH])
        for folder in list(STATE_FOLDERS.values()):
            p = os.path.join(self.tasks_path, folder)
            if not os.path.exists(p):
                os.makedirs(p)
                Path(os.path.join(p, ".gitkeep")).touch()
                self._run_git(
                    ["add", os.path.join(folder, ".gitkeep")], cwd=self.tasks_path
                )
        st = self._run_git(["status", "--porcelain"], cwd=self.tasks_path)
        if st.stdout:
            self._run_git(
                ["commit", "--allow-empty", "-m", "Init tasks folders"],
                cwd=self.tasks_path,
            )

        counter_file = os.path.join(self.tasks_path, ".task_counter")
        if not os.path.exists(counter_file):
            with open(counter_file, "w") as f:
                f.write("0")
            self._run_git(["add", ".task_counter"], cwd=self.tasks_path)
            self._run_git(
                ["commit", "--allow-empty", "-m", "Init task counter"],
                cwd=self.tasks_path,
            )

        gitignore_path = os.path.join(self.root, ".gitignore")
        ignore_line = f"{TASKS_DIR}/"
        if os.path.exists(gitignore_path):
            with open(gitignore_path, "r") as f:
                content = f.read()
            if ignore_line not in content:
                with open(gitignore_path, "a") as f:
                    f.write(f"\n{ignore_line}\n")
        else:
            with open(gitignore_path, "w") as f:
                f.write(f"{ignore_line}\n")
        self.log("Tasks initialized.")
        self.log(
            'Tip: Create a task with: tasks create "Your task title" --story "As a user..." --tech "..." --criteria "..." --plan "1. ..."'
        )
        self.log("Use -j for JSON output. Run 'list' to see all tasks with their Ids.")
        self.finish()

    def _append_log(self, task_path, entry):
        if not task_path:
            return
        task_path_str = cast(str, task_path)
        log_file = os.path.join(task_path_str, "activity.log")
        timestamp = datetime.now().strftime("%y%m%d %H:%M")
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(f"- {timestamp}: {entry}\n")
        self._run_git(
            [
                "add",
                os.path.join(
                    os.path.relpath(task_path_str, self.tasks_path), "activity.log"
                ),
            ],
            cwd=self.tasks_path,
        )

    def find_task(self, name):
        if not name:
            return None, None
        task_id = name.rsplit(".", 1)[0]

        matches = []
        for state, folder in STATE_FOLDERS.items():
            dir_path = os.path.join(self.tasks_path, folder, task_id)
            if os.path.isdir(dir_path):
                task = FM.load(dir_path)
                task_state = task.metadata.get("St", state)
                matches.append((dir_path, task_state))

        if not matches and task_id.isdigit():
            for state, folder in STATE_FOLDERS.items():
                fp = os.path.join(self.tasks_path, folder)
                if not os.path.exists(fp):
                    continue
                for item in os.listdir(fp):
                    path = os.path.join(fp, item)
                    if os.path.isdir(path):
                        task = FM.load(path)
                        if str(task.metadata.get("Id")) == task_id:
                            task_state = task.metadata.get("St", state)
                            matches.append((path, task_state))

        if not matches:
            return None, None

        if len(matches) == 1:
            return matches[0]

        for path, state in matches:
            if state == "ARCHIVED":
                return path, "ARCHIVED"
        for path, state in matches:
            if state != "BACKLOG":
                return path, state
        return matches[0]

    def _get_next_id(self):
        counter_file = os.path.join(self.tasks_path, ".task_counter")
        with open(counter_file, "r+") as f:
            fcntl.flock(f.fileno(), fcntl.LOCK_EX)
            try:
                current = int(f.read().strip())
                current += 1
                f.seek(0)
                f.truncate()
                f.write(str(current))
            finally:
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)
        self._run_git(["add", ".task_counter"], cwd=self.tasks_path)
        self._run_git(
            ["commit", "--allow-empty", "-m", f"Bump task counter to {current}"],
            cwd=self.tasks_path,
        )
        return current

    def create(
        self,
        title,
        task_type="task",
        priority=None,
        story=None,
        tech=None,
        criteria=None,
        plan=None,
        repro=None,
    ):
        if len(title) < 10:
            self.error("Task title is too vague. Min 10 chars.")
        missing = []
        if not story:
            missing.append("--story")
        if not tech:
            missing.append("--tech")
        if not criteria:
            missing.append("--criteria")
        if not plan:
            missing.append("--plan")
        if task_type == "issue" and not repro:
            missing.append("--repro")
        if missing:
            self.error(
                f"Missing required fields: {', '.join(missing)}. Task not created. These are required to move to PROGRESSING anyway."
            )

        clean_title = "".join(c if c.isalnum() else "-" for c in title.lower()).strip(
            "-"
        )
        numeric_id = self._get_next_id()
        task_id = f"{numeric_id}-{task_type}-{clean_title[:30]}"
        task_dir = os.path.join(self.tasks_path, STATE_FOLDERS["BACKLOG"], task_id)
        if self.find_task(task_id)[0]:
            self.error(f"Task {task_id} exists.")

        for state, folder in STATE_FOLDERS.items():
            fp = os.path.join(self.tasks_path, folder)
            if not os.path.exists(fp):
                continue
            for item in os.listdir(fp):
                if item == ".gitkeep":
                    continue
                path = os.path.join(fp, item)
                task = FM.load(path)
                if task.metadata.get("Id") == numeric_id:
                    self.error(
                        f"Task with Id {numeric_id} already exists (in {state})."
                    )

        task = Task(
            metadata={
                "Id": numeric_id,
                "Ti": title,
                "St": "BACKLOG",
                "Cr": datetime.now().strftime("%y%m%d %H:%M"),
                "Bl": [],
                "Pr": priority or (1 if task_type == "issue" else 2),
            },
            parts={
                "story": story or "",
                "tech": tech or "",
                "criteria": (
                    "\n".join(f"- [ ] {c}" for c in criteria)
                    if isinstance(criteria, list)
                    else f"- [ ] {criteria}"
                )
                if criteria
                else "",
                "plan": (
                    "\n".join(f"{i}. {p}" for i, p in enumerate(plan, 1))
                    if isinstance(plan, list)
                    else f"1. {plan}"
                )
                if plan
                else "",
                "repro": (
                    "\n".join(f"{i}. {r}" for i, r in enumerate(repro, 1))
                    if isinstance(repro, list)
                    else f"1. {repro}"
                )
                if repro
                else None,
            },
        )
        try:
            self._atomic_write(task_dir, task)
            self._append_log(task_dir, "Cr")
            self._run_git(
                ["add", os.path.relpath(task_dir, self.tasks_path)], cwd=self.tasks_path
            )
            self._run_git(
                ["commit", "--allow-empty", "-m", f"Add {task_type}: {title}"],
                cwd=self.tasks_path,
            )
            self._run_git(["checkout", "-b", task_id], cwd=self.root)
            current_branch = self._run_git(
                ["rev-parse", "--abbrev-ref", "HEAD"]
            ).stdout.strip()
            self.log(f"Created: [{numeric_id}] {task_type} | {title}")
            self.log(f"Branch: {task_id} | Now on: {current_branch}")
            self.finish(
                {
                    "id": numeric_id,
                    "task_id": task_id,
                    "title": title,
                    "file": task_id,
                    "path": os.path.relpath(task_dir, self.root),
                    "branch": task_id,
                    "current_branch": current_branch,
                }
            )
        except Exception as e:
            self.error(str(e))

    def modify(
        self,
        filename,
        title=None,
        story=None,
        tech=None,
        criteria=None,
        plan=None,
        repro=None,
        notes=None,
        progress=None,
        findings=None,
        mitigations=None,
    ):
        filepath, _ = self.find_task(filename)
        if not filepath:
            self.error(
                f"Task '{filename}' not found.",
                hint="Use 'tasks list' to see all available task filenames/IDs.",
            )
        task = FM.load(filepath)
        fname = os.path.basename(filepath)
        task_id = fname.rsplit(".", 1)[0]
        tt, _ = self._parse_filename(fname)
        updated = False
        if title:
            if len(title) < 10:
                self.error("Title too vague.")
            task.metadata["Ti"] = title
            updated = True
        if story:
            task.parts["story"] = story
            updated = True
        if tech:
            task.parts["tech"] = tech
            updated = True
        if criteria:
            if isinstance(criteria, list):
                task.parts["criteria"] = "\n".join(f"- [ ] {c}" for c in criteria)
            else:
                task.parts["criteria"] = criteria
            updated = True
        if plan:
            if isinstance(plan, list):
                task.parts["plan"] = "\n".join(
                    f"{i}. {p}" for i, p in enumerate(plan, 1)
                )
            else:
                task.parts["plan"] = plan
            updated = True
        if repro:
            if isinstance(repro, list):
                task.parts["repro"] = "\n".join(
                    f"{i}. {r}" for i, r in enumerate(repro, 1)
                )
            else:
                task.parts["repro"] = repro
            updated = True

        if notes or progress or findings or mitigations:
            n = task.parts.get("notes", "- Progress: \n- Findings: \n- Mitigations: \n")
            if notes:
                n = notes
            if progress:
                n = re.sub(r"- Progress:.*", f"- Progress: {progress}", n)
            if findings:
                n = re.sub(r"- Findings:.*", f"- Findings: {findings}", n)
            if mitigations:
                n = re.sub(r"- Mitigations:.*", f"- Mitigations: {mitigations}", n)
            task.parts["notes"] = n
            updated = True

        if updated:
            self._atomic_write(filepath, task)
            dump_path = os.path.join(filepath, CURRENT_TASK_FILENAME)
            if os.path.exists(dump_path):
                dump = FM.load(dump_path)
                dump.parts["content"] = task.parts.get("notes", "")
                self._atomic_write(dump_path, dump)
            self._append_log(filepath, "Mod")
            self._run_git(["add", "--all"], cwd=self.tasks_path)
            self._run_git(
                ["commit", "--allow-empty", "-m", f"Mod {os.path.basename(filepath)}"],
                cwd=self.tasks_path,
            )
            self.log(
                f"Modified: [{task.metadata.get('Id', '')}] {tt} | {task.metadata.get('Ti', '')}"
            )
            tt, branch = self._parse_filename(os.path.basename(filepath))
            if not self._run_git(["ls-remote", "--heads", "origin", branch]).stdout:
                self._run_git(["checkout", "-b", branch], cwd=self.root)
            if not task.parts.get("story"):
                self.log("Tip: Consider adding --story to document the user context.")
            elif not task.parts.get("tech"):
                self.log("Tip: Consider adding --tech for technical background.")
            elif not task.parts.get("criteria"):
                self.log("Tip: Consider adding --criteria for acceptance criteria.")
            elif not task.parts.get("plan"):
                self.log("Tip: Consider adding --plan for implementation steps.")
        else:
            self.log("No changes.")
        self.finish(
            {
                "id": task.metadata.get("Id"),
                "task_id": task_id,
                "title": task.metadata.get("Ti", ""),
            }
        )

    def delete(self, filename, confirm=None):
        filepath, _ = self.find_task(filename)
        if not filepath:
            self.error(f"Task '{filename}' not found.")

        # filepath is definitely not None here for pyright
        filepath_str = cast(str, filepath)
        task = FM.load(filepath_str)
        fname = os.path.basename(filepath_str)
        task_id = fname.rsplit(".", 1)[0]
        tt, _ = self._parse_filename(fname)

        if not confirm:
            code = "".join(random.choices(string.ascii_lowercase + string.digits, k=8))
            task.metadata["DeleteCode"] = code
            self._atomic_write(filepath_str, task)
            self._run_git(["add", "--all"], cwd=self.tasks_path)
            self._run_git(
                ["commit", "--allow-empty", "-m", f"Mark {task_id} for deletion"],
                cwd=self.tasks_path,
            )
            self.log(
                f"Task '[{task.metadata.get('Id', '')}] {tt} | {task.metadata.get('Ti', '')}' marked for deletion."
            )
            self.log(f"To confirm, run: tasks delete {task_id} --confirm {code}")
            self.log("WARNING: Running any other command will revert this mark.")
            self.finish(
                {
                    "id": task.metadata.get("Id"),
                    "task_id": task_id,
                    "title": task.metadata.get("Ti", ""),
                    "delete_code": code,
                }
            )

        if task.metadata.get("DeleteCode") != confirm:
            self.error(
                "Invalid or missing confirmation code.",
                hint=f"Run 'tasks delete {task_id}' again to get a new code.",
            )

        try:
            if os.path.isdir(filepath_str):
                shutil.rmtree(filepath_str)
            else:
                os.remove(filepath_str)
            self._run_git(["add", "--all"], cwd=self.tasks_path)
            self._run_git(
                ["commit", "--allow-empty", "-m", f"Del {task_id}"], cwd=self.tasks_path
            )
            self.log(
                f"Deleted: [{task.metadata.get('Id', '')}] {tt} | {task.metadata.get('Ti', '')}"
            )
        except Exception as e:
            self.error(str(e))
        self.finish(
            {
                "id": task.metadata.get("Id"),
                "task_id": task_id,
                "title": task.metadata.get("Ti", ""),
            }
        )

    def get_active_task(self, filename=None):
        if filename:
            filepath, _ = self.find_task(filename)
            if filepath:
                return filepath, FM.load(filepath)
            return None, None
        prog_dir = os.path.join(self.tasks_path, STATE_FOLDERS["PROGRESSING"])
        if os.path.exists(prog_dir):
            dirs = [
                d
                for d in os.listdir(prog_dir)
                if os.path.isdir(os.path.join(prog_dir, d)) and d != ".gitkeep"
            ]
            if dirs:
                filepath = os.path.join(prog_dir, dirs[0])
                return filepath, FM.load(filepath)
        return None, None

    def checkpoint(self, filename=None):
        filepath, task = self.get_active_task(filename)
        if not filepath or not task:
            self.error("No active task.")

        # filepath is definitely not None here for pyright
        filepath_str = cast(str, filepath)
        fname = os.path.basename(filepath_str)
        self.log(f"Checkpointing {fname}...")
        if self._sync_task_content(filepath_str, task):
            self._atomic_write(filepath_str, task)
            self._run_git(["add", "--all"], cwd=self.tasks_path)
            self._run_git(
                ["commit", "--allow-empty", "-m", f"Cp: {fname}"],
                cwd=self.tasks_path,
            )
            self.log("Done.")
        else:
            self.log("No changes.")
        self.finish()

    def _sync_task_content(self, filepath, task, is_final=False):
        if not filepath:
            return False
        filepath_str = cast(str, filepath)
        tn = os.path.basename(filepath_str)
        _, branch = self._parse_filename(tn)
        updated = False
        res = self._run_git(
            ["log", branch, f"^{self._get_default_branch()}", "--oneline"]
        )
        commits = res.stdout.strip() if res.returncode == 0 else ""
        if commits:
            task.parts["commits"] = commits
            updated = True
        dump_path = os.path.join(filepath_str, CURRENT_TASK_FILENAME)
        if os.path.exists(dump_path):
            dump = FM.load(dump_path)
            if dump.parts.get("content"):
                task.parts["notes"] = dump.parts["content"]
                updated = True
        return updated

    def _get_default_branch(self):
        for b in ["main", "master"]:
            if self._run_git(["rev-parse", "--verify", b]).returncode == 0:
                return b
        return "main"

    def link(self, filename, blocked_by_filename):
        f1, _ = self.find_task(filename)
        f2, _ = self.find_task(blocked_by_filename)
        if not f1 or not f2:
            self.error("Not found.")
        
        f1_str = cast(str, f1)
        f2_str = cast(str, f2)
        
        task = FM.load(f1_str)
        task_title = str(task.metadata.get("Ti", ""))
        task_id_num = str(task.metadata.get("Id", ""))
        tt, _ = self._parse_filename(os.path.basename(f1_str))
        bl = task.metadata.get("Bl", [])
        if not isinstance(bl, list):
            bl = []
        b_name = os.path.basename(f2_str)
        b_task = FM.load(f2_str)
        b_title = str(b_task.metadata.get("Ti", ""))
        b_id = str(b_task.metadata.get("Id", ""))
        b_tt, _ = self._parse_filename(os.path.basename(f2_str))
        if b_name not in bl:
            bl.append(b_name)
            task.metadata["Bl"] = bl
            self._atomic_write(f1_str, task)
            self._run_git(["add", "--all"], cwd=self.tasks_path)
            self._run_git(
                ["commit", "--allow-empty", "-m", f"Lk {filename}->{b_name}"],
                cwd=self.tasks_path,
            )
            self.log(
                f"Linked: [{task_id_num}] {tt} | {task_title} -> [{b_id}] {b_tt} | {b_title}"
            )
        self.finish(
            {
                "id": task_id_num,
                "task_id": filename,
                "title": task_title,
                "linked_to": b_name,
                "linked_to_title": b_title,
            }
        )

    def move(self, filename, new_status, yes=False):
        filepath, _ = self.find_task(filename)
        if not filepath:
            self.error(
                f"Task '{filename}' not found.",
                hint="Use 'tasks list' to see all available task filenames/IDs.",
            )
        task = FM.load(filepath)
        task_id = os.path.basename(filepath).rsplit(".", 1)[0]
        title = task.metadata.get("Ti", "")
        task_id_num = task.metadata.get("Id", "")
        tt, _ = self._parse_filename(os.path.basename(filepath))

        if "," in new_status:
            statuses = [s.strip().upper() for s in new_status.split(",")]
            current_state = str(task.metadata.get("St", ""))
            for i, target in enumerate(statuses):
                if (
                    target not in ALLOWED_TRANSITIONS.get(current_state, [])
                    and current_state != target
                ):
                    self.error(
                        f"Forbidden transition: {current_state} -> {target}",
                        hint=f"Allowed transitions from {current_state} are: {', '.join(ALLOWED_TRANSITIONS.get(current_state, []))}",
                    )
                if target == "PROGRESSING":
                    bl = task.metadata.get("Bl", [])
                    if not isinstance(bl, list):
                        bl = []
                    for b in bl:
                        _, bs = self.find_task(str(b))
                        if bs != "ARCHIVED":
                            self.error(
                                f"Blocked by {b}. Blocker must be ARCHIVED first."
                            )
                try:
                    task = self._perform_move(task, current_state, target, filepath)
                    fname = os.path.basename(filepath)
                    filepath = os.path.join(
                        self.tasks_path,
                        STATE_FOLDERS[target],
                        fname,
                    )
                    current_state = target
                except Exception as e:
                    self.error(f"Move failed at step {target}: {e}")

            final_status = statuses[-1]
            self.log(f"Moved: [{task_id_num}] {tt} | {title} -> {final_status}")
            self.finish(
                {
                    "id": task_id_num,
                    "task_id": task_id,
                    "title": title,
                    "status": final_status,
                }
            )
        else:
            self._move_logic(filename, new_status, yes=yes)
            self.log(f"Moved: [{task_id_num}] {tt} | {title} -> {new_status}")
            self.finish(
                {
                    "id": task_id_num,
                    "task_id": task_id,
                    "title": title,
                    "status": new_status,
                }
            )

    def _perform_move(self, task, current_state, new_status, filepath):
        if not filepath:
            self.error("Invalid task path.")
        filepath_str = cast(str, filepath)
        self._sync_task_content(filepath_str, task, is_final=(new_status == "ARCHIVED"))
        task.metadata["St"] = new_status
        fname = os.path.basename(filepath_str)
        new_filepath = os.path.join(
            self.tasks_path, STATE_FOLDERS[new_status], fname
        )
        if os.path.isdir(filepath_str):
            shutil.move(filepath_str, new_filepath)
        else:
            self._atomic_write(new_filepath, task)
            if os.path.exists(filepath_str):
                os.remove(filepath_str)
        self._atomic_write(new_filepath, task)
        self._append_log(new_filepath, f"{current_state}->{new_status}")
        return task

    def _move_logic(self, filename, new_status, force=False, yes=False):
        new_status = new_status.upper()
        filepath, current_state = self.find_task(filename)
        if not filepath:
            self.error(
                f"Task '{filename}' not found.",
                hint="Use 'tasks list' to see all available task filenames/IDs.",
            )
        filepath_str = cast(str, filepath)
        if current_state == new_status:
            return
        if new_status not in ALLOWED_TRANSITIONS.get(current_state, []) and not force:
            self.error(
                f"Forbidden transition: {current_state} -> {new_status}",
                hint=f"Allowed transitions from {current_state} are: {', '.join(ALLOWED_TRANSITIONS.get(current_state, []))}",
            )
        task = FM.load(filepath_str)
        fname = os.path.basename(filepath_str)
        tt, branch = self._parse_filename(fname)
        task_id_num = task.metadata.get("Id", "")
        task_id = fname.rsplit(".", 1)[0]
        title = task.metadata.get("Ti", "")

        def _has_complete_content(t, fn):
            if (
                not t.parts.get("story")
                or len(str(t.parts.get("story", "")).strip()) < 10
            ):
                return False
            if (
                not t.parts.get("tech")
                or len(str(t.parts.get("tech", "")).strip()) < 10
            ):
                return False
            if (
                not t.parts.get("criteria")
                or len(str(t.parts.get("criteria", "")).strip()) < 10
            ):
                return False
            if (
                not t.parts.get("plan")
                or len(str(t.parts.get("plan", "")).strip()) < 10
            ):
                return False
            type_part, _ = self._parse_filename(fn)
            if type_part == "issue":
                if (
                    not t.parts.get("repro")
                    or len(str(t.parts.get("repro", "")).strip()) < 10
                ):
                    return False
            return True

        if current_state == "BACKLOG" and new_status != "BACKLOG":
            if not _has_complete_content(task, fname):
                missing = []
                if (
                    not task.parts.get("story")
                    or len(str(task.parts.get("story", "")).strip()) < 10
                ):
                    missing.append("story")
                if (
                    not task.parts.get("tech")
                    or len(str(task.parts.get("tech", "")).strip()) < 10
                ):
                    missing.append("tech")
                if (
                    not task.parts.get("criteria")
                    or len(str(task.parts.get("criteria", "")).strip()) < 10
                ):
                    missing.append("criteria")
                if (
                    not task.parts.get("plan")
                    or len(str(task.parts.get("plan", "")).strip()) < 10
                ):
                    missing.append("plan")
                tt, _ = self._parse_filename(fname)
                if tt == "issue":
                    if (
                        not task.parts.get("repro")
                        or len(str(task.parts.get("repro", "")).strip()) < 10
                    ):
                        missing.append("repro")
                self.error(
                    f"Task lacks required content to leave BACKLOG. Missing or incomplete: {', '.join(missing)}",
                    hint='Use \'tasks modify <id> --story "..." --tech "..." --criteria "..." --plan "..."\' to add details. For issues, also add --repro.',
                )

        if new_status == "PROGRESSING":
            bl = task.metadata.get("Bl", [])
            if not isinstance(bl, list):
                bl = []
            for b in bl:
                _, bs = self.find_task(str(b))
                if bs != "ARCHIVED":
                    self.error(f"Blocked by {b}. Blocker must be ARCHIVED first.")

            missing = []
            if (
                not task.parts.get("story")
                or len(str(task.parts.get("story", "")).strip()) < 10
            ):
                missing.append("story")
            if (
                not task.parts.get("tech")
                or len(str(task.parts.get("tech", "")).strip()) < 10
            ):
                missing.append("tech")
            if (
                not task.parts.get("criteria")
                or len(str(task.parts.get("criteria", "")).strip()) < 10
            ):
                missing.append("criteria")
            if (
                not task.parts.get("plan")
                or len(str(task.parts.get("plan", "")).strip()) < 10
            ):
                missing.append("plan")

            tt, _ = self._parse_filename(fname)
            if tt == "issue":
                if (
                    not task.parts.get("repro")
                    or len(str(task.parts.get("repro", "")).strip()) < 10
                ):
                    missing.append("repro")

            if missing:
                self.error(
                    f"Task lacks sufficient detail to move to PROGRESSING. Missing or incomplete: {', '.join(missing)}",
                    hint='Use \'tasks show <id>\' to see current content, then \'tasks modify <id> --story "..." --tech "..." --criteria "..." --plan "..."\' to add proper details. For issues, also add --repro. Run \'tasks modify --help\' for syntax help.',
                )

        tt, branch = self._parse_filename(fname)
        # Resolve branch to SHA if it exists
        branch_sha_res = self._run_git(["rev-parse", branch])
        branch_sha = branch_sha_res.stdout.strip() if branch_sha_res.returncode == 0 else ""
        if not branch_sha:
            # Try to find it in reflog or by name in commits
            res = self._run_git(["log", "-1", "--format=%H", branch])
            if res.returncode == 0:
                branch_sha = res.stdout.strip()

        if not force:
            has_origin = self._run_git(["remote", "get-url", "origin"]).returncode == 0
            if new_status in ("REVIEW", "ARCHIVED"):
                if has_origin:
                    if not self._run_git(
                        ["ls-remote", "--heads", "origin", branch]
                    ).stdout:
                        self.error(
                            f"Branch '{branch}' not pushed to remote. Push and try again."
                        )

            if new_status == "REVIEW":
                merge_base = self._run_git(
                    ["merge-base", branch_sha or branch, "testing"]
                ).stdout.strip()
                testing_sha = (
                    self._run_git(["rev-parse", "testing"]).stdout.strip()
                    if self._run_git(["rev-parse", "--verify", "testing"]).returncode
                    == 0
                    else None
                )
                if not testing_sha or merge_base != testing_sha:
                    self.error(
                        f"Branch '{branch}' not merged to testing. Merge to testing first."
                    )

            if new_status == "ARCHIVED" and not force:
                main_sha = (
                    self._run_git(["rev-parse", "main"]).stdout.strip()
                    if self._run_git(["rev-parse", "--verify", "main"]).returncode == 0
                    else None
                )
                branch_commit = (
                    branch_sha or self._run_git(["rev-parse", branch]).stdout.strip()
                )
                if main_sha:
                    merge_base = self._run_git(
                        ["merge-base", branch_commit, "main"]
                    ).stdout.strip()
                    if merge_base != main_sha:
                        self.error(
                            f"Branch '{branch}' not merged to main. Merge to main first. Alternatively, move to REJECTED."
                        )
                if yes:
                    self._run_git(["push", "origin", branch], cwd=self.root)
                    self._run_git(["branch", "-d", branch], cwd=self.root)
                else:
                    if not self.as_json:
                        print(f"Branch '{branch}' is merged to main.")
                        print(
                            f"To archive and clean up, run: tasks move {task_id_num} ARCHIVED -y"
                        )
                    self.finish(
                        {
                            "id": task_id_num,
                            "task_id": task_id,
                            "title": title,
                            "branch_merged": True,
                            "needs_confirmation": True,
                        }
                    )

        if new_status == "ARCHIVED" and self._has_incomplete_checkboxes(filepath):
            self.error("Cannot archive task: contains unfinished checkboxes (- [ ])")
        self._sync_task_content(filepath, task, is_final=(new_status == "ARCHIVED"))
        task["St"] = new_status
        new_filepath = os.path.join(
            self.tasks_path, STATE_FOLDERS[new_status], os.path.basename(filepath)
        )
        try:
            if os.path.isdir(filepath):
                shutil.move(filepath, new_filepath)
            else:
                self._atomic_write(new_filepath, task)
                if os.path.exists(filepath):
                    os.remove(filepath)

            self._atomic_write(new_filepath, task)
            self._append_log(new_filepath, f"{current_state}->{new_status}")
            if new_status == "ARCHIVED":
                task_id = task.metadata.get("Id", "")
                title = task.metadata.get("Ti", "")
                self._run_git(["add", "--all"], cwd=self.tasks_path)
                self._run_git(
                    [
                        "commit",
                        "-m",
                        f"Archive [{task_id}] {title}",
                    ],
                    cwd=self.tasks_path,
                )
            if new_status == "PROGRESSING":
                dump_path = os.path.join(new_filepath, CURRENT_TASK_FILENAME)
                d = Task(
                    metadata={"Task": os.path.basename(new_filepath)},
                    parts={
                        "content": task.parts.get(
                            "notes", "- Progress: \n- Findings: \n- Mitigations: \n"
                        )
                    },
                )
                self._atomic_write(dump_path, d)
        except Exception as e:
            self.error(str(e))

    def current(self, filename=None):
        filepath, task = self.get_active_task(filename)
        if not filepath or not task:
            self.error("No active task.")

        # filepath is definitely not None here for pyright
        filepath_str = cast(str, filepath)
        tn = os.path.basename(filepath_str)
        tt, br = self._parse_filename(tn)
        data = {
            "file": os.path.relpath(filepath_str, self.root),
            "name": tn,
            "type": tt,
            "branch": br,
            "metadata": {
                str(KEY_MAP.get(str(k), k)): v for k, v in task.metadata.items()
            },
            "log_file": os.path.relpath(
                os.path.join(filepath_str, "activity.log"), self.root
            ),
        }
        dp = os.path.join(filepath_str, CURRENT_TASK_FILENAME)
        if os.path.exists(dp):
            d = FM.load(dp)
            data["dump"] = {
                "file": os.path.relpath(dp, self.root),
                "content": d.parts.get("content", "").strip(),
            }

        if not self.as_json:
            print(
                f"# TASK: {data['metadata'].get('Title', data['name'])}\n- **File**: `{data['file']}`\n- **Type**: {data['type']} | **Branch**: `{data['branch']}`"
            )
            for k, v in data["metadata"].items():
                if k != "Title":
                    print(f"- **{k}**: {v}")
            if "dump" in data:
                print(f"\n## Active Progress\n{data['dump']['content']}")
            else:
                print(f"\n## Content\n{task.content}")

        self.finish(data)

    def show(self, filename, section=None):
        filepath, _ = self.find_task(filename)
        if not filepath:
            self.error(
                f"Task '{filename}' not found.",
                hint="Use 'tasks list' to see available task Ids.",
            )

        # filepath is definitely not None here for pyright
        filepath_str = cast(str, filepath)
        task = FM.load(filepath_str)
        tn = os.path.basename(filepath_str)
        tt, br = self._parse_filename(tn)
        data = {
            "file": os.path.relpath(filepath_str, self.root),
            "name": tn,
            "type": tt,
            "branch": br,
            "metadata": {
                str(KEY_MAP.get(str(k), k)): v for k, v in task.metadata.items()
            },
            "log_file": os.path.relpath(
                os.path.join(filepath_str, "activity.log"), self.root
            ),
        }
        dp = os.path.join(filepath_str, CURRENT_TASK_FILENAME)
        if os.path.exists(dp):
            d = FM.load(dp)
            data["dump"] = {
                "file": os.path.relpath(dp, self.root),
                "content": d.parts.get("content", "").strip(),
            }

        section_map = {
            "story": ("Story", task.parts.get("story", "No story")),
            "tech": ("Technical", task.parts.get("tech", "No technical details")),
            "criteria": ("Criteria", task.parts.get("criteria", "No criteria")),
            "plan": ("Plan", task.parts.get("plan", "No plan")),
            "repro": ("Reproduction", task.parts.get("repro", "No reproduction steps")),
            "notes": ("Notes", task.parts.get("notes", "No notes")),
            "progress": (
                "Active Progress",
                data.get("dump", {}).get("content", "No active progress"),
            ),
        }

        if not self.as_json:
            if section:
                if section in section_map:
                    title, content = section_map[section]
                    print(f"## {title}\n{content}")
                else:
                    self.error(
                        f"Unknown section '{section}'. Valid sections: {', '.join(section_map.keys())}"
                    )
            else:
                print(
                    f"# TASK: {data['metadata'].get('Title', data['name'])}\n- **Id**: {data['metadata'].get('Id', '')} | **State**: {data['metadata'].get('State', '')} | **Priority**: {data['metadata'].get('Priority', '')}\n- **File**: `{data['file']}`\n- **Type**: {data['type']} | **Branch**: `{data['branch']}`"
                )
                print(f"\n## Story\n{task.parts.get('story', 'No story')}")
                print(
                    f"\n## Technical\n{task.parts.get('tech', 'No technical details')}"
                )
                print(f"\n## Criteria\n{task.parts.get('criteria', 'No criteria')}")
                print(f"\n## Plan\n{task.parts.get('plan', 'No plan')}")
                if task.parts.get("repro"):
                    print(f"\n## Reproduction\n{task.parts.get('repro')}")
                if data.get("dump"):
                    print(f"\n## Active Progress\n{data['dump']['content']}")

        self.finish(data)

    def list(self, show_all=False):
        if not os.path.exists(self.tasks_path):
            self.error("Init required.")
        all_data = {}
        seen = set()
        for state, folder in STATE_FOLDERS.items():
            if state == "ARCHIVED" and not show_all:
                continue
            fp = os.path.join(self.tasks_path, folder)
            if not os.path.exists(fp):
                continue
            items = os.listdir(fp)
            tasks = []
            for item in sorted(items):
                if item == ".gitkeep" or item in seen:
                    continue
                path = os.path.join(fp, item)
                if not os.path.isdir(path):
                    continue
                task = FM.load(path)
                actual_state = task.metadata.get("St", state)
                if actual_state != state:
                    continue
                tt, tb = self._parse_filename(item)
                task_id = task.metadata.get("Id")
                if not task_id:
                    task_id = self._get_next_id()
                    task.metadata["Id"] = task_id
                    self._atomic_write(path, task)
                    self._run_git(["add", "--all"], cwd=self.tasks_path)
                    self._run_git(
                        [
                            "commit",
                            "--allow-empty",
                            "-m",
                            f"Assign Id {task_id} to {item}",
                        ],
                        cwd=self.tasks_path,
                    )
                seen.add(item)
                tasks.append(
                    {
                        "id": task_id,
                        "p": task.get("Pr", 9),
                        "file": item,
                        "type": tt,
                        "branch": tb,
                        "summary": task.metadata.get("Ti", "No Title")[:60],
                        "blocked_by": task.get("Bl", []),
                    }
                )
            if tasks:
                tasks.sort(key=lambda x: (x["p"], x["file"]))
                all_data[state] = tasks
        if self.as_json:
            self.finish(all_data)
        elif self.quiet:
            pass
        else:
            term_width = get_terminal_width()
            summary_width = max(30, term_width - 45)
            branch_width = max(15, term_width - summary_width - 30)

            for state, tasks in all_data.items():
                print(f"\n{state}")
                print("=" * term_width)
                print(
                    f"{'#':>3} {'P':>2} {'Summary':<{summary_width}} {'Type':<6} {'Branch':<{branch_width}}"
                )
                print("-" * term_width)
                for t in tasks:
                    summary_lines = textwrap.wrap(
                        t["summary"], width=summary_width
                    ) or [""]

                    def simple_wrap(text, width):
                        result = []
                        while len(text) > width:
                            result.append(text[:width])
                            text = text[width:]
                        result.append(text)
                        return result

                    branch_lines = simple_wrap(t["branch"], branch_width) or [""]
                    max_lines = max(len(summary_lines), len(branch_lines))
                    for i in range(max_lines):
                        id_str = str(t.get("id", "")) if i == 0 else ""
                        p_str = str(t["p"]) if i == 0 else " "
                        s_line = summary_lines[i] if i < len(summary_lines) else ""
                        type_str = t["type"] if i == 0 else ""
                        b_line = branch_lines[i] if i < len(branch_lines) else ""
                        print(
                            f"{id_str:>3} {p_str:>2} {s_line:<{summary_width}} {type_str:<6} {b_line:<{branch_width}}"
                        )
            self.finish()

    def reconcile(self, target=None, all=False):
        if not target and not all:
            self.cleanup(dry_run=True)
        elif all:
            self.cleanup(yes=True)
        else:
            filepath, _ = self.find_task(target)
            if filepath:
                self._move_logic(target, "ARCHIVED", force=True)

    def _reconcile_scan(self):
        candidates = []
        for state, folder in STATE_FOLDERS.items():
            if state in ("ARCHIVED", "REJECTED", "BACKLOG"):
                continue
            fp = os.path.join(self.tasks_path, folder)
            if not os.path.exists(fp):
                continue
            for item in os.listdir(fp):
                if item == ".gitkeep":
                    continue
                path = os.path.join(fp, item)
                if not os.path.isdir(path):
                    continue
                task = FM.load(path)
                task_id = task.metadata.get("Id")
                if not task_id:
                    continue
                branch = item
                main_sha_res = self._run_git(["rev-parse", "main"])
                main_sha = (
                    main_sha_res.stdout.strip() if main_sha_res.returncode == 0 else ""
                )
                if not main_sha:
                    continue
                branch_sha_res = self._run_git(["rev-parse", branch])
                branch_sha = (
                    branch_sha_res.stdout.strip()
                    if branch_sha_res.returncode == 0
                    else ""
                )
                if not branch_sha:
                    continue
                merge_base = self._run_git(
                    ["merge-base", branch_sha, "main"]
                ).stdout.strip()
                if merge_base == main_sha:
                    candidates.append(
                        {
                            "id": task_id,
                            "task_id": task_id,
                            "title": task.metadata.get("Ti", ""),
                            "state": state,
                            "branch": branch,
                            "filepath": path,
                        }
                    )

        if not candidates:
            if self.as_json:
                self.finish({"candidates": [], "count": 0})
            else:
                print("No archive candidates found.")
            return

        if self.as_json:
            self.finish({"candidates": candidates, "count": len(candidates)})
        else:
            print(f"\nFound {len(candidates)} archive candidates:\n")
            print(f"{'#':>3} {'State':<12} {'Title':<40} {'Branch'}")
            print("-" * 80)
            for c in candidates:
                title = c["title"][:38] if len(c["title"]) > 38 else c["title"]
                print(f"{c['id']:>3} {c['state']:<12} {title:<40} {c['branch']}")
            print("\nTo archive a task, run: tasks reconcile <id>")
            print("To archive all, run: tasks reconcile --all")

    def _reconcile_archive_all(self):
        candidates = []
        for state, folder in STATE_FOLDERS.items():
            if state in ("ARCHIVED", "REJECTED", "BACKLOG"):
                continue
            fp = os.path.join(self.tasks_path, folder)
            if not os.path.exists(fp):
                continue
            for item in os.listdir(fp):
                if item == ".gitkeep":
                    continue
                path = os.path.join(fp, item)
                if not os.path.isdir(path):
                    continue
                task = FM.load(path)
                task_id = task.metadata.get("Id")
                if not task_id:
                    continue
                branch = item
                main_sha_res = self._run_git(["rev-parse", "main"])
                main_sha = (
                    main_sha_res.stdout.strip() if main_sha_res.returncode == 0 else ""
                )
                if not main_sha:
                    continue
                branch_sha_res = self._run_git(["rev-parse", branch])
                branch_sha = (
                    branch_sha_res.stdout.strip()
                    if branch_sha_res.returncode == 0
                    else ""
                )
                if not branch_sha:
                    continue
                merge_base = self._run_git(
                    ["merge-base", branch_sha, "main"]
                ).stdout.strip()
                if merge_base == main_sha:
                    candidates.append(
                        {
                            "id": task_id,
                            "task_id": task_id,
                            "title": task.metadata.get("Ti", ""),
                            "state": state,
                            "branch": branch,
                            "filepath": path,
                        }
                    )

        if not candidates:
            if self.as_json:
                self.finish({"archived": 0, "count": 0})
            else:
                print("No candidates to archive.")
            return

        archived = 0
        for c in candidates:
            self._move_logic(c["branch"], "ARCHIVED", force=True, yes=True)
            archived += 1
            if not self.as_json:
                print(f"Archived: [{c['id']}] {c['title']}")

        if self.as_json:
            self.finish({"archived": archived, "count": len(candidates)})

    def _reconcile_single(self, filename):
        filepath, _ = self.find_task(filename)
        if not filepath:
            self.error(
                f"Task '{filename}' not found.",
                hint="Use 'tasks list' to see available task Ids and filenames.",
            )
        task = FM.load(filepath)
        task_id = os.path.basename(filepath).rsplit(".", 1)[0]
        title = task.metadata.get("Ti", "")
        branch = task_id

        # Check if remote 'origin' exists
        has_origin = self._run_git(["remote", "get-url", "origin"]).returncode == 0
        if has_origin:
            if self._run_git(["ls-remote", "--heads", "origin", branch]).stdout:
                return
            if not self.as_json:
                print(f"Branch: {branch} (no longer exists in remote)")
        else:
            # If no origin, check if local branch exists
            has_local = self._run_git(["rev-parse", "--verify", branch]).returncode == 0
            if has_local:
                return
            if not self.as_json:
                print(f"Branch: {branch} (does not exist locally)")

        if not self.as_json:
            print(f"Task: [{task.metadata.get('Id', '')}] {title}")
            print(f"State: {task.metadata.get('St', 'unknown')}")

        do_archive = False
        if self.as_json:
            do_archive = True
        else:
            if input("Archive this task? [y/N]: ").strip().lower() == "y":
                do_archive = True

        if do_archive:
            self._move_logic(
                os.path.basename(filepath), "ARCHIVED", force=True, yes=False
            )
            if self.as_json:
                self.finish({"archived": True, "task_id": task_id})
            else:
                print(f"Archived: [{task.metadata.get('Id', '')}] {title}")
        else:
            if self.as_json:
                self.finish({"archived": False, "task_id": task_id})
            else:
                print("Cancelled.")

    def cleanup(self, dry_run=False, yes=False):
        """Clean up branches merged to main and archive corresponding tasks."""
        current_branch = self._run_git(
            ["rev-parse", "--abbrev-ref", "HEAD"]
        ).stdout.strip()

        default_branch = self._get_default_branch()

        if current_branch not in ("main", "master", "staging", "testing"):
            if self.as_json:
                self.finish(
                    {
                        "error": f"Cleanup must be run from {default_branch}, staging, or testing branch. Currently on '{current_branch}'."
                    }
                )
            else:
                print(
                    f"Error: Cleanup must be run from {default_branch}, staging, or testing branch."
                )
                print(f"Currently on: {current_branch}")
            return

        main_sha = self._run_git(["rev-parse", default_branch]).stdout.strip()
        if not main_sha:
            if self.as_json:
                self.finish({"cleaned": [], "archived": [], "count": 0})
            else:
                print(f"No {default_branch} branch found.")
            return

        branches = self._run_git(
            ["branch", "--format", "%(refname:short)"]
        ).stdout.strip()
        if not branches:
            if self.as_json:
                self.finish({"cleaned": [], "archived": [], "count": 0})
            else:
                print("No local branches found.")
            return

        cleaned = []
        archived = []
        has_origin = self._run_git(["remote", "get-url", "origin"]).returncode == 0

        for branch in branches.splitlines():
            branch = branch.strip()
            if not branch or branch in ("main", "master", "staging", "testing"):
                continue

            branch_sha = self._run_git(["rev-parse", branch]).stdout.strip()

            is_ancestor = (
                self._run_git(
                    ["merge-base", "--is-ancestor", branch_sha, default_branch]
                ).returncode
                == 0
            )

            if not is_ancestor:
                continue

            if not dry_run:
                if has_origin:
                    self._run_git(["push", "origin", branch], cwd=self.root)
                self._run_git(["branch", "-D", branch], cwd=self.root)

            cleaned.append(branch)

            res_find = self.find_task(branch)
            filepath = res_find[0]
            state = res_find[1]
            if filepath and state in ("REVIEW", "ARCHIVED"):
                if not dry_run:
                    if state == "REVIEW":
                        self._move_logic(branch, "ARCHIVED", force=True, yes=yes)
                        archived.append(branch)
                else:
                    archived.append(branch)

        if self.as_json:
            self.finish(
                {"cleaned": cleaned, "archived": archived, "count": len(cleaned)}
            )
        else:
            if dry_run:
                print("Dry run - would clean up:")
            else:
                print("Cleaned up:")
            for b in cleaned:
                print(f"  - {b}")
            if archived:
                print("\nArchived tasks:")
                for b in archived:
                    print(f"  - {b}")

    def config(self, action=None, key=None, value=None, save=False):
        """Manage configuration (get/set/list/detect)."""
        config_path = os.path.join(self.tasks_path, "config.yaml")

        def load_config():
            if os.path.exists(config_path):
                try:
                    import yaml

                    with open(config_path, "r") as f:
                        return yaml.safe_load(f) or {}
                except Exception:
                    return {}
            return {}

        def save_config(cfg):
            try:
                import yaml

                with open(config_path, "w") as f:
                    yaml.safe_dump(cfg, f)
            except Exception as e:
                self.error(f"Failed to save config: {e}")

        if action == "detect":
            detected = self._detect_tools()
            if save and detected:
                cfg = load_config()
                for k, v in detected.items():
                    key_name = (
                        f"repo.{k}"
                        if k in ["lint", "test", "type_check", "format"]
                        else k
                    )
                    if v:
                        cfg[key_name] = v
                save_config(cfg)
                if self.as_json:
                    self.finish({"detected": detected, "saved": True})
                else:
                    print("Configuration saved.")
            elif self.as_json:
                self.finish({"detected": detected})
            return

        cfg = load_config()

        if action == "list":
            if self.as_json:
                self.finish(cfg)
            else:
                if cfg:
                    print("Configuration:")
                    for k, v in cfg.items():
                        print(f"  {k} = {v}")
                else:
                    print("No configuration found.")
                print("\nRun 'config detect' to auto-detect project tools.")
        elif action == "get":
            if not key:
                self.error("Missing config key.")
            if self.as_json:
                self.finish({"key": key, "value": cfg.get(key)})
            else:
                print(cfg.get(key, ""))
        elif action == "set":
            if not key or value is None:
                self.error("Missing config key or value.")
            cfg[key] = value
            save_config(cfg)
            if self.as_json:
                self.finish({"key": key, "value": value})
            else:
                print(f"Set {key} = {value}")
        else:
            if self.as_json:
                self.finish({"actions": ["get", "set", "list", "detect"]})
            else:
                print("Usage: tasks config [get|set|list|detect] [key] [value]")
                print("  get <key>     - Get config value")
                print("  set <key> <val> - Set config value")
                print("  list          - List all config")
                print("  detect        - Detect project tools and create config")

    def _detect_tools(self):
        """Detect project type and suggest/create config."""
        detected = {}

        if os.path.exists("package.json"):
            detected["package_manager"] = "npm"
            if os.path.exists("yarn.lock"):
                detected["package_manager"] = "yarn"
            elif os.path.exists("pnpm-lock.yaml"):
                detected["package_manager"] = "pnpm"

        if os.path.exists("pyproject.toml"):
            detected["package_manager"] = "pip"
        elif os.path.exists("requirements.txt"):
            detected["package_manager"] = "pip"
        elif os.path.exists("Pipfile"):
            detected["package_manager"] = "pipenv"

        if os.path.exists("go.mod"):
            detected["language"] = "go"

        if os.path.exists("Cargo.toml"):
            detected["language"] = "rust"

        if os.path.exists("composer.json"):
            detected["language"] = "php"

        if os.path.exists("Gemfile"):
            detected["language"] = "ruby"

        lint_files = {
            "ruff.toml": "ruff",
            "pyproject.toml": "ruff",
            ".eslintrc.js": "eslint",
            ".eslintrc.json": "eslint",
            "eslint.config.js": "eslint",
            "tsconfig.json": "typescript",
            "rust-toolchain.toml": "rust",
            ".golangci.yml": "golangci-lint",
            "pylintrc": "pylint",
            ".pylintrc": "pylint",
        }

        for file, tool in lint_files.items():
            if os.path.exists(file):
                detected["lint"] = tool
                break

        type_check_files = {
            "mypy.ini": "mypy",
            "pyrightconfig.json": "pyright",
            "tsconfig.json": "typescript",
        }

        for file, tool in type_check_files.items():
            if os.path.exists(file):
                detected["type_check"] = tool
                break

        if os.path.exists("pytest.ini") or os.path.exists("pyproject.toml"):
            detected["test"] = "pytest"
        elif os.path.exists("go.mod"):
            detected["test"] = "go test"
        elif os.path.exists("Cargo.toml"):
            detected["test"] = "cargo test"

        format_files = {
            "ruff.toml": "ruff",
            "pyproject.toml": "ruff",
            ".prettierrc": "prettier",
            "rustfmt.toml": "rustfmt",
        }

        for file, tool in format_files.items():
            if os.path.exists(file):
                detected["format"] = tool
                break

        if not self.as_json:
            print("Detected tools:")
            for k, v in detected.items():
                print(f"  {k}: {v}")

            if detected:
                print("\nWould you like to save this configuration?")
                print(
                    "Run: tasks config set repo.lint " + detected.get("lint", "<tool>")
                )
                print(
                    "      tasks config set repo.type_check "
                    + detected.get("type_check", "<tool>")
                )
                print(
                    "      tasks config set repo.test " + detected.get("test", "<tool>")
                )
                print(
                    "      tasks config set repo.format "
                    + detected.get("format", "<tool>")
                )

        return detected

    def _get_config(self, key=None):
        """Load config and optionally get a specific key."""
        config_path = os.path.join(self.tasks_path, "config.yaml")
        if os.path.exists(config_path):
            try:
                import yaml

                with open(config_path, "r") as f:
                    cfg = yaml.safe_load(f) or {}
            except Exception:
                cfg = {}
        else:
            cfg = {}

        if key:
            return cfg.get(key)
        return cfg

    def get_tool(self, tool_type):
        """Get the configured tool for a given type (lint, test, type_check, format)."""
        key_map = {
            "lint": "repo.lint",
            "test": "repo.test",
            "type_check": "repo.type_check",
            "format": "repo.format",
        }
        config_key = key_map.get(tool_type)
        if config_key:
            return self._get_config(config_key)
        return None

    def run_tool(self, tool_name=None, fix=False):
        """Run configured tools (lint, test, typecheck, format)."""
        root_str = cast(str, self.root)
        check_py = os.path.join(root_str, "check.py")
        if not os.path.exists(check_py):
            self.error("check.py not found in project root.")
            return 1

        cmd = [sys.executable, check_py, tool_name or "all"]
        if fix:
            cmd.append("--fix")
        if self.as_json:
            cmd.append("--json")

        # Run check.py and capture output to pass it through TasksCLI's finish/error
        result = subprocess.run(cmd, cwd=self.root, capture_output=True, text=True)

        if self.as_json:
            try:
                data = json.loads(result.stdout)
                if result.returncode == 0:
                    self.finish(data)
                else:
                    # In JSON mode, check.py outputs success: False
                    print(result.stdout)
                    sys.exit(1)
            except json.JSONDecodeError:
                self.error(
                    f"Validation failed with exit code {result.returncode}\n{result.stdout}\n{result.stderr}"
                )
        else:
            # In plain mode, check.py prints directly to stdout/stderr
            print(result.stdout)
            if result.stderr:
                print(result.stderr, file=sys.stderr)
            if result.returncode != 0:
                sys.exit(result.returncode)

        return result.returncode

    def upgrade(self):
        """Upgrade tasks to latest version by running install.sh."""
        import shutil

        user_dir = os.path.expanduser("~/.local/tasks-ai")
        system_dir = "/opt/tasks-ai"

        can_write_user = os.access(user_dir, os.W_OK)
        can_write_system = os.access(system_dir, os.W_OK)

        install_path = None
        mode = None

        if can_write_user:
            install_path = user_dir
            mode = "user"
        elif can_write_system:
            install_path = system_dir
            mode = "system"
        else:
            self.error("Cannot write to either ~/.local/tasks-ai or /opt/tasks-ai")

        install_script = os.path.join(install_path, "install.sh")

        if not os.path.exists(install_script):
            self.error(
                f"install.sh not found at {install_path}. Run 'tasks init' first or install manually."
            )

        self.log(f"Detected installation: {mode} at {install_path}")

        this_dir = os.path.dirname(os.path.abspath(__file__))
        local_install = os.path.join(os.path.dirname(this_dir), "install.sh")

        if os.path.exists(local_install):
            self.log("Using local install.sh...")
            shutil.copy(local_install, install_script)
            os.chmod(install_script, 0o755)
        else:
            self.log("Downloading install.sh from GitHub...")
            result = subprocess.run(
                [
                    "curl",
                    "-sSL",
                    "https://raw.githubusercontent.com/tim-projects/tasks-ai/main/install.sh",
                    "-o",
                    install_script,
                ],
                capture_output=True,
                text=True,
            )
            if result.returncode != 0:
                self.error(f"Failed to download install.sh: {result.stderr}")
            os.chmod(install_script, 0o755)

        if mode == "system":
            self.log("System-wide installation detected. Running with sudo...")
            result = subprocess.run(
                ["sudo", "bash", install_script, "-g"], capture_output=True, text=True
            )
        else:
            result = subprocess.run(
                ["bash", install_script, "-u"], capture_output=True, text=True
            )

        if result.returncode != 0:
            self.error(f"Upgrade failed: {result.stderr}")

        if self.as_json:
            self.finish({"success": True, "mode": mode, "path": install_path})
        else:
            self.log("✅ Upgrade complete!")
            self.log(f"Installed to: {install_path}")
