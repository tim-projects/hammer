import os
import sys
import json


def get_terminal_width():
    try:
        return os.get_terminal_size().columns
    except OSError:
        return 80


def log(cli, message):
    if cli.as_json:
        cli.output_messages.append(message)
    elif not cli.quiet:
        print(message)


def error(cli, message, hint=None):
    if cli.quiet:
        pass
    elif cli.as_json:
        response = {
            "success": False,
            "error": message,
            "messages": cli.output_messages,
        }
        if hint:
            response["hint"] = hint
        print(json.dumps(response))
        sys.exit(1)
    else:
        if hint:
            message = f"{message} | HINT: {hint}"
        print(f"Error: {message}", file=sys.stderr)
        sys.exit(1)


def finish(cli, data=None):
    if cli.quiet:
        pass
    elif cli.as_json:
        print(
            json.dumps(
                {"success": True, "messages": cli.output_messages, "data": data},
                indent=2,
            )
        )
    if not hasattr(sys, "_called_from_test"):
        sys.exit(0)
