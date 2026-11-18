import argparse
import json
import os
import signal
import sys


def configure_sigpipe():
    """Restore Unix's normal behavior when a downstream pipe closes early."""
    if hasattr(signal, "SIGPIPE"):
        signal.signal(signal.SIGPIPE, signal.SIG_DFL)


class NextStepArgumentParser(argparse.ArgumentParser):
    """Report invalid usage as an actionable next step."""

    def error(self, message):
        self.print_usage(sys.stderr)
        next_step = (
            f"Correct the command syntax: {message}. "
            f"Run './hammer {self.prog} --help' to see correct usage."
        )
        if any(arg in ("-j", "--json") for arg in sys.argv[1:]):
            print(
                json.dumps(
                    {
                        "success": False,
                        "status": "next_step",
                        "next_step": next_step,
                    }
                )
            )
            self.exit(2)
        if getattr(self, "hammer_voice", False):
            self.exit(
                2,
                f"NEXT STEP: {next_step}\n"
                f"WHAT: {message}.\n"
                "WHY: Command syntax invalid.\n"
                f"HOW: Run './hammer {self.prog} --help' to see correct usage.\n"
                "CONSEQUENCE: Command halted until the syntax is corrected.\n",
            )
        self.exit(2, f"NEXT STEP: {next_step}\n")


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


def error(cli, message, hint=None, error_code="UNEXPECTED_ERROR"):
    error_code = str(error_code).strip() or "UNEXPECTED_ERROR"
    if cli.quiet:
        sys.exit(1)
    if cli.as_json:
        response = {
            "success": False,
            "error_code": error_code,
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
        print(f"Error [{error_code}]: {message}", file=sys.stderr)
        sys.exit(1)


def next_step(cli, message, hint=None):
    """Render an expected workflow prerequisite without weakening the gate."""
    if cli.quiet:
        sys.exit(1)
    if cli.as_json:
        response = {
            "success": False,
            "status": "next_step",
            "next_step": message,
            "messages": cli.output_messages,
        }
        if hint:
            response["hint"] = hint
        print(json.dumps(response))
        sys.exit(1)
    print(f"NEXT STEP: {message}")
    if hint:
        print(hint)
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
