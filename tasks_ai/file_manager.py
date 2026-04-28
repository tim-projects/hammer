# tasks_ai/file_manager.py
import os
import json
import tempfile
import shutil
from .models import Task


def _atomic_write(path, content):
    """Write content to file atomically using temp file + rename."""
    dir_path = os.path.dirname(path) or "."
    with tempfile.NamedTemporaryFile(
        mode="w", dir=dir_path, delete=False, encoding="utf-8"
    ) as tmp:
        tmp.write(content)
        tmp_path = tmp.name
    shutil.move(tmp_path, path)


class FM:
    @staticmethod
    def load(path):
        if not os.path.exists(path):
            return Task()

        if os.path.isfile(path):
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
            if not content.startswith("---"):
                return Task(parts={"content": content})

            meta = {}
            lines = content.splitlines()
            content_start = -1
            for i in range(1, len(lines)):
                line = lines[i].strip()
                if line == "---":
                    content_start = i + 1
                    break
                if ":" in line:
                    k, v = [s.strip() for s in line.split(":", 1)]
                    if v.startswith("[") and v.endswith("]"):
                        inner = v[1:-1].strip()
                        meta[k] = (
                            [
                                item.strip().strip("'").strip('"')
                                for item in inner.split(",")
                            ]
                            if inner
                            else []
                        )
                    elif v.isdigit():
                        meta[k] = int(v)
                    else:
                        meta[k] = v.strip("'").strip('"')

            body = "\n".join(lines[content_start:]) if content_start != -1 else ""
            return Task(metadata=meta, parts={"content": body})

        meta = {}
        meta_path = os.path.join(path, "meta.json")
        if os.path.exists(meta_path):
            try:
                with open(meta_path, "r") as f:
                    meta = json.load(f)
            except (json.JSONDecodeError, ValueError):
                # Robustness: ignore corrupted meta.json
                pass

        if not os.path.isdir(path):
            return Task(metadata=meta, parts={})

        parts = {}
        for f in os.listdir(path):
            if f.endswith(".md"):
                part_name = f[:-3]
                with open(os.path.join(path, f), "r") as file:
                    parts[part_name] = file.read()
        return Task(metadata=meta, parts=parts)

    @staticmethod
    def dump(task, path):
        if path.endswith(".md"):
            os.makedirs(os.path.dirname(path), exist_ok=True)
            content = "---\n"
            for k, v in task.metadata.items():
                val = (
                    "[" + ", ".join(f'"{item}"' for item in v) + "]"
                    if isinstance(v, list)
                    else v
                )
                content += f"{k}: {val}\n"
            content += "---\n\n"
            content += task.parts.get("content", task.content)
            _atomic_write(path, content)
            return

        os.makedirs(path, exist_ok=True)
        meta_path = os.path.join(path, "meta.json")
        _atomic_write(
            meta_path,
            json.dumps(task.metadata, indent=2),
        )

        for name, content in task.parts.items():
            if name == "content":
                continue
            if content is None:
                continue
            _atomic_write(os.path.join(path, f"{name}.md"), content)
