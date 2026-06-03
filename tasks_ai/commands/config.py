from ..constants import KEY_MAP, ALLOWED_CONFIG_KEYS, load_config, save_config


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
                key_name = KEY_MAP.get(k, k)
                if v:
                    cfg[key_name] = v
            save_config(cli.tasks_path, cfg)
            if not cli.as_json:
                cli.log("Detected tools saved to config.yaml.")

        if not cli.as_json:
            cli.log(f"Detected tools: {detected}")
        cli.finish(detected)
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
