from ..constants import ALLOWED_CONFIG_KEYS, load_config, save_config


def run(cli, action=None, key=None, value=None, save=False):
    """Execution logic for 'tasks config'."""
    if action == "detect":
        detected = cli._detect_tools()
        if not detected:
            if not cli.as_json:
                cli.log("No tools detected in project root.")
            cli.finish({})
            return

        if save:
            cfg = load_config(cli.tasks_path)
            for k, v in detected.items():
                key_name = (
                    f"repo.{k}"
                    if k in ["lint", "test", "type_check", "format"]
                    else k
                )
                if v:
                    cfg[key_name] = v
            save_config(cli.tasks_path, cfg)
            if not cli.as_json:
                cli.log("Configuration saved.")
            if cli.as_json:
                cli.finish({"detected": detected, "saved": True})
            else:
                cli.finish({})
            return

        if not cli.as_json:
            cli.log("Detected tools:")
            for k, v in detected.items():
                cli.log(f"  {k}: {v}")
            cli.log("")
            cli.log("Would you like to save this configuration?")
            cli.log(
                "Run: tasks config set repo.lint " + detected.get("lint", "<tool>")
            )
            cli.log(
                "      tasks config set repo.type_check "
                + detected.get("type_check", "<tool>")
            )
            cli.log(
                "      tasks config set repo.test "
                + detected.get("test", "<tool>")
            )
            cli.log(
                "      tasks config set repo.format "
                + "<path to format tool>"
            )

        cli.finish({"detected": detected})
        return

    cfg = load_config(cli.tasks_path)

    if action == "list":
        cli.finish(cfg)
    elif action == "get":
        if not key:
            cli.error("MISSING_CONFIG_KEY")
        if cli.as_json:
            cli.finish({"key": key, "value": cfg.get(key)})
        else:
            print(cfg.get(key, ""))
    elif action == "set":
        if not key or value is None:
            cli.error("MISSING_CONFIG_KEY_OR_VALUE")
        if key not in ALLOWED_CONFIG_KEYS:
            cli.error(
                "INVALID_CONFIG_KEY",
                key=key,
                allowed_keys=", ".join(sorted(ALLOWED_CONFIG_KEYS)),
            )
        cfg[key] = value
        save_config(cli.tasks_path, cfg)
        if cli.as_json:
            cli.finish({"key": key, "value": value})
        else:
            print(f"Set {key} = {value}")
    else:
        cli.finish(cfg)
