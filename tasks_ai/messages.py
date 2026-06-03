import json
import os


class MessageRegistry:
    def __init__(self, data_dir="data"):
        # Resolve data directory relative to the project root
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        data_path = os.path.join(project_root, data_dir)
        self.errors = self._load_json(os.path.join(data_path, "errors.json"))
        self.hints = self._load_json(os.path.join(data_path, "hints.json"))

    def _load_json(self, path):
        if not os.path.exists(path):
            return {}
        with open(path, "r") as f:
            return json.load(f)

    def get_error(self, code, **kwargs):
        msg = self.errors.get(code, f"Unknown error: {code}")
        return msg.format(**kwargs)

    def get_hint(self, code, **kwargs):
        return self.hints.get(code, "").format(**kwargs)
