import os
import yaml
from .constants import ALLOWED_CONFIG_KEYS

class Commands:
    def __init__(self, cli):
        self.cli = cli

    def config(self, action=None, key=None, value=None, save=False):
        """Manage configuration (get/set/list/detect)."""
        config_path = os.path.join(self.cli.tasks_path, "config.yaml")

        def load_config():
            if os.path.exists(config_path):
                try:
                    with open(config_path, "r") as f:
                        return yaml.safe_load(f) or {}
                except Exception:
                    return {}
            return {}

        def save_config(cfg):
            try:
                with open(config_path, "w") as f:
                    yaml.safe_dump(cfg, f)
            except Exception as e:
                self.cli.error(f"❌ CONFIG SAVE FAIL! {e}! 🔨")

        if action == "detect":
            detected = self.cli._detect_tools()
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
                if self.cli.as_json:
                    self.cli.finish({"detected": detected, "saved": True})
                else:
                    print("Configuration saved.")
            elif self.cli.as_json:
                self.cli.finish({"detected": detected})
            return

        cfg = load_config()

        if action == "list":
            if self.cli.as_json:
                self.cli.finish(cfg)
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
                self.cli.error("❌ MISSING CONFIG KEY! 🔨")
            if self.cli.as_json:
                self.cli.finish({"key": key, "value": cfg.get(key)})
            else:
                print(cfg.get(key, ""))
        elif action == "set":
            if not key or value is None:
                self.cli.error("❌ MISSING CONFIG KEY OR VALUE! 🔨")
            if key not in ALLOWED_CONFIG_KEYS:
                self.cli.error(
                    f"❌ INVALID CONFIG KEY '{key}'! 🔨",
                    hint=f"ALLOWED: {', '.join(sorted(ALLOWED_CONFIG_KEYS))}! RUN 'tasks config detect' AUTO-DETECT TOOLS!",
                )
            cfg[key] = value
            save_config(cfg)
            if self.cli.as_json:
                self.cli.finish({"key": key, "value": value})
            else:
                print(f"Set {key} = {value}")
        else:
            if self.cli.as_json:
                self.cli.finish({"actions": ["get", "set", "list", "detect"]})
            else:
                print("Usage: tasks config [get|set|list|detect] [key] [value]")
                print("  get <key>     - Get config value")
                print("  set <key> <val> - Set config value")
                print("  list          - List all config")
                print("  detect        - Detect project tools and create config")

    def doctor(self, fix=False):
        """Diagnose task data integrity and git state, create bug reports for issues."""
        # (doctor implementation)
        # Note: I'll need to move doctor method logic here from cli.py.
        # This will be large, I should check if I can keep it in cli.py or if it MUST move.
        # The task says: Extract config, doctor, and validation.
