import json
import os


class MessageRegistry:
    def __init__(self, data_dir="data"):
        package_dir = os.path.dirname(os.path.abspath(__file__))
        data_path = os.path.join(os.path.dirname(package_dir), data_dir)
        self.errors = self._load_json(os.path.join(data_path, "errors.json"))
        self.hints = self._load_json(os.path.join(data_path, "hints.json"))
        self.next_steps = self._load_json(os.path.join(data_path, "next_steps.json"))

    def _load_json(self, path):
        if not os.path.exists(path):
            return {}
        with open(path, "r") as f:
            return json.load(f)

    class SafeFormatter(dict):
        def __missing__(self, key):
            return "{" + key + "}"

    def get_error(self, code, **kwargs):
        msg = self.errors.get(code, code)
        return str(msg).format_map(self.SafeFormatter(kwargs))

    def get_hint(self, code, **kwargs):
        return self.hints.get(code, "").format_map(self.SafeFormatter(kwargs))

    def get_next_step(self, code, **kwargs):
        entry = self.next_steps.get(code, {})
        message = entry.get("message", f"Complete the required step for {code}.")
        return message.format_map(self.SafeFormatter(kwargs))

    def get_next_step_hint(self, code, **kwargs):
        entry = self.next_steps.get(code, {})
        hint = entry.get("hint", "")
        return hint.format_map(self.SafeFormatter(kwargs))
