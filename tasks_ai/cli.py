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
import uuid
from datetime import datetime, timedelta
from pathlib import Path


def get_terminal_width():
    try:
        return os.get_terminal_size().columns
    except OSError:
        return 80


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


class TasksCLI:
    def __init__(self, as_json=False, command=None):
        self.as_json = as_json
        self.output_messages = []
        self.root = self._get_git_root()
        self.tasks_path = os.path.join(self.root, TASKS_DIR)
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
                if "DeleteCode" in task.metadata:
                    del task.metadata["DeleteCode"]
                    self._atomic_write(path, task)
                    updated = True
        if updated:
            self._run_git(["add", "--all"], cwd=self.tasks_path)
            self._run_git(["commit", "-m", "Clear delete marks"], cwd=self.tasks_path)

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
        return subprocess.run(["git"] + args, cwd=cwd, capture_output=True, text=True)

    def _parse_filename(self, name):
        name_part = name.rsplit(".", 1)[0]
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
        else:
            print(message)

    def error(self, message, hint=None):
        if hint:
            message = f"{message} | HINT: {hint}"
        if self.as_json:
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
        if self.as_json:
            print(
                json.dumps(
                    {"success": True, "messages": self.output_messages, "data": data},
                    indent=2,
                )
            )
        if not hasattr(sys, "_called_from_test"):
            sys.exit(0)

    def _auto_archive(self):
        live_dir = os.path.join(self.tasks_path, STATE_FOLDERS["LIVE"])
        if not os.path.exists(live_dir):
            return
        now = datetime.now()
        for folder in os.listdir(live_dir):
            path = os.path.join(live_dir, folder)
            if not os.path.isdir(path):
                continue
            log_path = os.path.join(self.logs_path, folder)
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
                    self.log(f"Auto-archiving: {folder}")
                    self._move_logic(folder, "ARCHIVED", force=True)

    def init(self):
        branches = self._run_git(["branch"]).stdout
        if TASKS_BRANCH not in branches:
            self._run_git(["checkout", "--orphan", TASKS_BRANCH])
            self._run_git(["reset", "--hard"])
            self._run_git(["commit", "--allow-empty", "-m", "Initial tasks commit"])
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
            self._run_git(["worktree", "add", TASKS_DIR, TASKS_BRANCH])
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
            self._run_git(["commit", "-m", "Init tasks folders"], cwd=self.tasks_path)
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
            'Tip: Create a task with: tasks-ai create "Your task title" --story "As a user..." --tech "..." --criteria "..." --plan "1. ..."'
        )
        self.log("Use -j for JSON output. Run 'list' to see all tasks with their Ids.")
        self.finish()

    def _append_log(self, task_path, entry):
        log_file = os.path.join(task_path, "activity.log")
        timestamp = datetime.now().strftime("%y%m%d %H:%M")
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(f"- {timestamp}: {entry}\n")
        self._run_git(
            [
                "add",
                os.path.join(
                    os.path.relpath(task_path, self.tasks_path), "activity.log"
                ),
            ],
            cwd=self.tasks_path,
        )

    def find_task(self, name):
        if not name:
            return None, None
        task_id = name.rsplit(".", 1)[0]

        # First try direct lookup by filename
        for state, folder in STATE_FOLDERS.items():
            dir_path = os.path.join(self.tasks_path, folder, task_id)
            if os.path.isdir(dir_path):
                return dir_path, state
            file_path = dir_path + ".md"
            if os.path.isfile(file_path):
                return file_path, state

        # If not found and looks like a numeric ID, search by metadata Id
        if task_id.isdigit():
            for state, folder in STATE_FOLDERS.items():
                fp = os.path.join(self.tasks_path, folder)
                if not os.path.exists(fp):
                    continue
                for item in os.listdir(fp):
                    if item == ".gitkeep":
                        continue
                    path = os.path.join(fp, item)
                    task = FM.load(path)
                    if str(task.metadata.get("Id")) == task_id:
                        return path, state

        return None, None

    def _get_next_id(self):
        counter_file = os.path.join(self.tasks_path, ".task_counter")
        if os.path.exists(counter_file):
            with open(counter_file, "r") as f:
                current = int(f.read().strip())
        else:
            current = 0
        current += 1
        with open(counter_file, "w") as f:
            f.write(str(current))
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
        task_id = f"{task_type}_{clean_title[:30]}"
        numeric_id = self._get_next_id()
        task_dir = os.path.join(self.tasks_path, STATE_FOLDERS["BACKLOG"], task_id)
        if self.find_task(task_id)[0]:
            self.error(f"Task {task_id} exists.")

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
                "criteria": "\n".join(f"- [ ] {c}" for c in criteria)
                if criteria
                else "",
                "plan": "\n".join(f"{i}. {p}" for i, p in enumerate(plan, 1))
                if plan
                else "",
                "repro": "\n".join(f"{i}. {r}" for i, r in enumerate(repro, 1))
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
                ["commit", "-m", f"Add {task_type}: {title}"], cwd=self.tasks_path
            )
            self.log(f"Created: [{numeric_id}] {task_type} | {title}")
            self.finish(
                {
                    "id": numeric_id,
                    "task_id": task_id,
                    "title": title,
                    "file": task_id,
                    "path": os.path.relpath(task_dir, self.root),
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
                hint="Use 'tasks-ai list' to see all available task filenames/IDs.",
            )
        task = FM.load(filepath)
        task_id = os.path.basename(filepath).rsplit(".", 1)[0]
        tt, _ = self._parse_filename(os.path.basename(filepath))
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
            task.parts["criteria"] = "\n".join(f"- [ ] {c}" for c in criteria)
            updated = True
        if plan:
            task.parts["plan"] = "\n".join(f"{i}. {p}" for i, p in enumerate(plan, 1))
            updated = True
        if repro:
            task.parts["repro"] = "\n".join(f"{i}. {r}" for i, r in enumerate(repro, 1))
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
                ["commit", "-m", f"Mod {os.path.basename(filepath)}"],
                cwd=self.tasks_path,
            )
            self.log(
                f"Modified: [{task.metadata.get('Id', '')}] {tt} | {task.metadata.get('Ti', '')}"
            )
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
        task = FM.load(filepath)
        task_id = os.path.basename(filepath).rsplit(".", 1)[0]
        tt, _ = self._parse_filename(os.path.basename(filepath))

        if not confirm:
            code = "".join(random.choices(string.ascii_lowercase + string.digits, k=8))
            task.metadata["DeleteCode"] = code
            self._atomic_write(filepath, task)
            self._run_git(["add", "--all"], cwd=self.tasks_path)
            self._run_git(
                ["commit", "-m", f"Mark {task_id} for deletion"], cwd=self.tasks_path
            )
            self.log(
                f"Task '[{task.metadata.get('Id', '')}] {tt} | {task.metadata.get('Ti', '')}' marked for deletion."
            )
            self.log(f"To confirm, run: tasks-ai delete {task_id} --confirm {code}")
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
                hint=f"Run 'tasks-ai delete {task_id}' again to get a new code.",
            )

        try:
            if os.path.isdir(filepath):
                shutil.rmtree(filepath)
            else:
                os.remove(filepath)
            self._run_git(["add", "--all"], cwd=self.tasks_path)
            self._run_git(["commit", "-m", f"Del {task_id}"], cwd=self.tasks_path)
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
                if os.path.isdir(os.path.join(prog_dir, d))
            ]
            if dirs:
                filepath = os.path.join(prog_dir, dirs[0])
                return filepath, FM.load(filepath)
        return None, None

    def checkpoint(self, filename=None):
        filepath, task = self.get_active_task(filename)
        if not filepath:
            self.error("No active task.")
        self.log(f"Checkpointing {os.path.basename(filepath)}...")
        if self._sync_task_content(filepath, task):
            self._atomic_write(filepath, task)
            self._run_git(["add", "--all"], cwd=self.tasks_path)
            self._run_git(
                ["commit", "-m", f"Cp: {os.path.basename(filepath)}"],
                cwd=self.tasks_path,
            )
            self.log("Done.")
        else:
            self.log("No changes.")
        self.finish()

    def _sync_task_content(self, filepath, task, is_final=False):
        _, branch = self._parse_filename(os.path.basename(filepath))
        updated = False
        res = self._run_git(
            ["log", branch, f"^{self._get_default_branch()}", "--oneline"]
        )
        commits = res.stdout.strip() if res.returncode == 0 else ""
        if commits:
            task.parts["commits"] = commits
            updated = True
        dump_path = os.path.join(filepath, CURRENT_TASK_FILENAME)
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
        task = FM.load(f1)
        task_title = task.metadata.get("Ti", "")
        task_id_num = task.metadata.get("Id", "")
        tt, _ = self._parse_filename(os.path.basename(f1))
        bl = task.get("Bl", [])
        b_name = os.path.basename(f2)
        b_task = FM.load(f2)
        b_title = b_task.metadata.get("Ti", "")
        b_id = b_task.metadata.get("Id", "")
        b_tt, _ = self._parse_filename(os.path.basename(f2))
        if b_name not in bl:
            bl.append(b_name)
            task["Bl"] = bl
            self._atomic_write(f1, task)
            self._run_git(["add", "--all"], cwd=self.tasks_path)
            self._run_git(
                ["commit", "-m", f"Lk {filename}->{b_name}"], cwd=self.tasks_path
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

    def move(self, filename, new_status):
        filepath, _ = self.find_task(filename)
        if not filepath:
            self.error(
                f"Task '{filename}' not found.",
                hint="Use 'tasks-ai list' to see all available task filenames/IDs.",
            )
        task = FM.load(filepath)
        task_id = os.path.basename(filepath).rsplit(".", 1)[0]
        title = task.metadata.get("Ti", "")
        task_id_num = task.metadata.get("Id", "")
        tt, _ = self._parse_filename(os.path.basename(filepath))

        if "," in new_status:
            statuses = [s.strip().upper() for s in new_status.split(",")]
            current_state = task.get("St")
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
                    for b in task.get("Bl", []):
                        _, bs = self.find_task(b)
                        if bs != "ARCHIVED":
                            self.error(
                                f"Blocked by {b}. Blocker must be ARCHIVED first."
                            )
                task = self._perform_move(task, current_state, target, filepath)
                current_state = target
                if i == len(statuses) - 1:
                    filepath = os.path.join(
                        self.tasks_path,
                        STATE_FOLDERS[target],
                        os.path.basename(filepath),
                    )
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
            self._move_logic(filename, new_status)
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
        self._sync_task_content(filepath, task, is_final=(new_status == "ARCHIVED"))
        task["St"] = new_status
        new_filepath = os.path.join(
            self.tasks_path, STATE_FOLDERS[new_status], os.path.basename(filepath)
        )
        if os.path.isdir(filepath):
            shutil.move(filepath, new_filepath)
        else:
            self._atomic_write(new_filepath, task)
            if os.path.exists(filepath):
                os.remove(filepath)
        self._atomic_write(new_filepath, task)
        self._append_log(new_filepath, f"{current_state}->{new_status}")
        return task

    def _move_logic(self, filename, new_status, force=False):
        new_status = new_status.upper()
        filepath, current_state = self.find_task(filename)
        if not filepath:
            self.error(
                f"Task '{filename}' not found.",
                hint="Use 'tasks-ai list' to see all available task filenames/IDs.",
            )
        if current_state == new_status:
            return
        if new_status not in ALLOWED_TRANSITIONS.get(current_state, []) and not force:
            self.error(
                f"Forbidden transition: {current_state} -> {new_status}",
                hint=f"Allowed transitions from {current_state} are: {', '.join(ALLOWED_TRANSITIONS.get(current_state, []))}",
            )
        task = FM.load(filepath)
        if new_status == "PROGRESSING":
            for b in task.get("Bl", []):
                _, bs = self.find_task(b)
                if bs != "ARCHIVED":
                    self.error(f"Blocked by {b}. Blocker must be ARCHIVED first.")

            missing = []
            if (
                not task.parts.get("story")
                or len(task.parts.get("story", "").strip()) < 10
            ):
                missing.append("story")
            if (
                not task.parts.get("tech")
                or len(task.parts.get("tech", "").strip()) < 10
            ):
                missing.append("tech")
            if (
                not task.parts.get("criteria")
                or len(task.parts.get("criteria", "").strip()) < 10
            ):
                missing.append("criteria")
            if (
                not task.parts.get("plan")
                or len(task.parts.get("plan", "").strip()) < 10
            ):
                missing.append("plan")

            tt, _ = self._parse_filename(os.path.basename(filepath))
            if tt == "issue":
                if (
                    not task.parts.get("repro")
                    or len(task.parts.get("repro", "").strip()) < 10
                ):
                    missing.append("repro")

            if missing:
                self.error(
                    f"Task lacks sufficient detail to move to PROGRESSING. Missing or incomplete: {', '.join(missing)}",
                    hint='Use \'tasks-ai show <id>\' to see current content, then \'tasks-ai modify <id> --story "..." --tech "..." --criteria "..." --plan "..."\' to add proper details. For issues, also add --repro. Run \'tasks-ai modify --help\' for syntax help.',
                )
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
            self._run_git(["add", "--all"], cwd=self.tasks_path)
            self._run_git(
                [
                    "commit",
                    "-m",
                    f"Mv {os.path.basename(filepath)}: {current_state}->{new_status}",
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
        if not filepath:
            self.error("No active task.")
        tn = os.path.basename(filepath)
        tt, br = self._parse_filename(tn)
        data = {
            "file": os.path.relpath(filepath, self.root),
            "name": tn,
            "type": tt,
            "branch": br,
            "metadata": {KEY_MAP.get(k, k): v for k, v in task.metadata.items()},
            "log_file": os.path.relpath(
                os.path.join(filepath, "activity.log"), self.root
            ),
        }
        dp = os.path.join(filepath, CURRENT_TASK_FILENAME)
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
                hint="Use 'tasks-ai list' to see available task Ids.",
            )
        task = FM.load(filepath)
        tn = os.path.basename(filepath)
        tt, br = self._parse_filename(tn)
        data = {
            "file": os.path.relpath(filepath, self.root),
            "name": tn,
            "type": tt,
            "branch": br,
            "metadata": {KEY_MAP.get(k, k): v for k, v in task.metadata.items()},
            "log_file": os.path.relpath(
                os.path.join(filepath, "activity.log"), self.root
            ),
        }
        dp = os.path.join(filepath, CURRENT_TASK_FILENAME)
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
                seen.add(item)
                path = os.path.join(fp, item)
                task = FM.load(path)
                tt, tb = self._parse_filename(item)
                task_id = task.metadata.get("Id")
                if not task_id:
                    task_id = self._get_next_id()
                    task.metadata["Id"] = task_id
                    self._atomic_write(path, task)
                    self._run_git(["add", "--all"], cwd=self.tasks_path)
                    self._run_git(
                        ["commit", "-m", f"Assign Id {task_id} to {item}"],
                        cwd=self.tasks_path,
                    )
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

    def reconcile(self, target=None):
        if not target:
            self.error(
                "Missing target. Use 'tasks-ai reconcile all' to archive orphaned tasks (tasks whose branches no longer exist in remote), or provide a specific task Id/filename.",
                hint="Run 'tasks-ai list' to see available task Ids and filenames.",
            )
        if target == "all":
            self._reconcile_all()
        else:
            self._reconcile_single(target)

    def _reconcile_single(self, filename):
        filepath, _ = self.find_task(filename)
        if not filepath:
            self.error(
                f"Task '{filename}' not found.",
                hint="Use 'tasks-ai list' to see available task Ids and filenames. You can also use 'tasks-ai reconcile all' to check all tasks for orphaned branches.",
            )
        task = FM.load(filepath)
        task_id = os.path.basename(filepath).rsplit(".", 1)[0]
        title = task.metadata.get("Ti", "")
        branch = task_id
        if self._run_git(["ls-remote", "--heads", "origin", branch]).stdout:
            return
        print(f"Task: [{task.metadata.get('Id', '')}] {title}")
        print(f"Branch: {branch} (no longer exists in remote)")
        print(f"State: {task.metadata.get('St', 'unknown')}")
        if input(f"Archive this task? [y/N]: ").strip().lower() == "y":
            self._move_logic(os.path.basename(filepath), "ARCHIVED", force=True)
            print(f"Archived: [{task.metadata.get('Id', '')}] {title}")

    def _reconcile_all(self):
        orphans = []
        for state, folder in STATE_FOLDERS.items():
            if state == "ARCHIVED":
                continue
            fp = os.path.join(self.tasks_path, folder)
            if not os.path.exists(fp):
                continue
            for item in os.listdir(fp):
                if item == ".gitkeep":
                    continue
                filepath = os.path.join(fp, item)
                _, branch = self._parse_filename(item)
                if not self._run_git(["ls-remote", "--heads", "origin", branch]).stdout:
                    orphans.append(item)
        if not orphans:
            print("No orphans.")
            return
        for o in orphans:
            print(f"  - {o}")
        if input("Archive all? [y/N]: ").strip().lower() == "y":
            for o in orphans:
                self._move_logic(o, "ARCHIVED", force=True)
