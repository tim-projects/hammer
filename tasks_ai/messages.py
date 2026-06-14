import json
import os


class MessageRegistry:
    def __init__(self, data_dir="data"):
        # Resolve data directory absolute path relative to the tasks_ai package location.
        # This assumes tasks_ai is in the same directory as the data/ folder.
        package_dir = os.path.dirname(os.path.abspath(__file__))
        data_path = os.path.join(os.path.dirname(package_dir), data_dir)
        
        self.errors = self._load_json(os.path.join(data_path, "errors.json"))
        self.hints = self._load_json(os.path.join(data_path, "hints.json"))

    def _load_json(self, path):
        if not os.path.exists(path):
            return {}
        with open(path, "r") as f:
            return json.load(f)

    class SafeFormatter(dict):
        def __missing__(self, key):
            return "{" + key + "}"

    def get_error(self, code, **kwargs):
        msg = self.errors.get(code, f"Unknown error: {code}")
        return msg.format_map(self.SafeFormatter(kwargs))

    def get_hint(self, code, **kwargs):
        return self.hints.get(code, "").format_map(self.SafeFormatter(kwargs))
