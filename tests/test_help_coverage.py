"""Every hammer tool and subcommand must answer -h and --help with usage.

Locked down here:

1. Explicit form: 'hammer <tool> <command> -h' and '--help' exit 0 and print
   usage, for every command the tool advertises in its own help.
2. Auto-detect form: 'hammer <command> -h' and '--help' work for every command
   the wrapper maps in COMMAND_TO_TOOL (no 'Unknown tool or command').
3. Tool-level help: 'hammer <tool> -h'/'--help' print the tool layout plus the
   agent contract, plain text with no persona, and exit 0.
4. Bare invocation: 'hammer <tool>' prints usage and exits 1.
5. JSON mode never wraps help: -j does not turn help into a JSON envelope.
"""

import importlib.machinery
import importlib.util
import os
import re
import subprocess
import sys
import unittest
from concurrent.futures import ThreadPoolExecutor

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HAMMER = os.path.join(PROJECT_ROOT, "hammer")

# Tools whose command list is nested one level deeper (e.g. 'repo branch').
NESTED_PATHS = [("repo", "branch")]

# A positional sample per command that takes one, so -h can be locked in the
# position a real call puts it: after the positionals. Values are deliberately
# non-existent ids/branches - if -h ever stopped short-circuiting, the command
# would fail on the unknown name instead of touching real state.
POSITIONAL_SAMPLE = {
    ("tasks", "show"): ["999999"],
    ("tasks", "modify"): ["999999"],
    ("tasks", "move"): ["999999", "TESTING"],
    ("tasks", "delete"): ["999999"],
    ("tasks", "mount"): ["999999"],
    ("tasks", "checkpoint"): ["999999"],
    ("tasks", "undo"): ["999999"],
    ("tasks", "link"): ["999999", "999998"],
    ("tasks", "unlink"): ["999999", "999998"],
    ("tasks", "unarchive"): ["999999"],
    ("tasks", "audit"): ["999999"],
    ("tasks", "verify"): ["999999"],
    ("tasks", "config"): ["get", "lint"],
    ("repo", "merge"): ["zzz-no-such-branch", "testing"],
    ("repo", "promote"): ["zzz-no-such-branch"],
    ("repo", "demote"): ["999999", "PROGRESSING"],
    ("repo", "commit"): ["zzz-no-changes"],
    ("repo", "check-merged"): ["zzz-no-such-branch"],
    ("repo", "check-merged-testing"): ["zzz-no-such-branch"],
    ("guard", "check"): ["999999"],
}

EMOJI = re.compile(r"[\U0001F300-\U0001FAFF\u2600-\u27BF\u274C\u2705]")


def load_hammer_module():
    loader = importlib.machinery.SourceFileLoader("hammer_script", HAMMER)
    spec = importlib.util.spec_from_loader("hammer_script", loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


hammer_module = load_hammer_module()
COMMAND_TO_TOOL = hammer_module.COMMAND_TO_TOOL


def run_hammer(*args):
    return subprocess.run(  # noqa: PLW1510
        [HAMMER, *args],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )


def run_many(invocations):
    """Run help invocations concurrently: each one is a fresh interpreter
    against a tool that imports its package, so serial execution is slow."""
    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = {pool.submit(run_hammer, *args): args for args in invocations}
        return {args: future.result() for future, args in futures.items()}


def advertised_commands(*path):
    """Commands a tool advertises in its own help - read from the help text so a
    new subcommand is audited the moment it is added."""
    result = run_hammer(*path, "-h")
    assert result.returncode == 0, f"{path} -h failed: {result.stderr}"
    braces = re.search(r"\{([^}]*)\}", result.stdout)
    if braces:
        return [
            name for name in braces.group(1).split(",") if not name.startswith("-")
        ]
    section = result.stdout.split("positional arguments:", 1)[1].split(
        "\noptions:", 1
    )[0]
    commands = []
    for line in section.splitlines():
        entry = re.match(r"^ {4}(\S+)", line)
        if entry and entry.group(1) not in commands:
            commands.append(entry.group(1))
    return commands


class TestHelpCoverage(unittest.TestCase):
    def assert_help_works(self, path, commands):
        invocations = [
            (*(path or ()), command, flag) for command in commands for flag in ("-h", "--help")
        ]
        for args, result in run_many(invocations).items():
            with self.subTest(cmd=" ".join(args)):
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn("usage", result.stdout.lower())
                self.assertNotEqual(result.stdout.strip(), "")

    def assert_tool_help_layout(self, tool):
        for flag in ("-h", "--help"):
            with self.subTest(tool=tool, flag=flag):
                result = run_hammer(tool, flag)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn("usage", result.stdout.lower())
                self.assertIn(
                    "Always use -j for JSON output (machine-parseable for agents).",
                    result.stdout,
                    f"agent contract missing from '{tool} {flag}'",
                )
                self.assertIn(f"use {tool} <command> -h", result.stdout)
                self.assertIsNone(
                    EMOJI.search(result.stdout), "help text must stay plain"
                )

    def test_wrapper_help(self):
        for args in (["-h"], ["--help"], ["help"]):
            with self.subTest(args=args):
                result = run_hammer(*args)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn("Tools:", result.stdout)
                self.assertIn("Examples:", result.stdout)

    def test_tool_help_layout(self):
        for tool in ("tasks", "check", "repo", "guard"):
            self.assert_tool_help_layout(tool)

    def test_bare_tool_invocation_prints_usage(self):
        for tool in ("tasks", "check", "repo", "guard"):
            with self.subTest(tool=tool):
                result = run_hammer(tool)
                self.assertEqual(result.returncode, 1, result.stdout)
                self.assertIn("usage", (result.stdout + result.stderr).lower())

    def test_subcommand_help_explicit_form(self):
        for path in [(tool,) for tool in ("tasks", "check", "repo", "guard")] + NESTED_PATHS:
            self.assert_help_works(path, advertised_commands(*path))

    def test_subcommand_help_auto_detect_form(self):
        for path in [(tool,) for tool in ("tasks", "check", "repo", "guard")]:
            tool = path[0]
            commands = [
                command
                for command in advertised_commands(tool)
                if COMMAND_TO_TOOL.get(command) == tool
            ]
            self.assert_help_works(None, commands)

    def test_help_flag_wins_from_any_position(self):
        """-h is global: it wins before the subcommand, and after positionals."""
        for path in [(tool,) for tool in ("tasks", "check", "repo", "guard")] + NESTED_PATHS:
            tool = path[0]
            before = [(tool, "-h", *path[1:], command) for command in advertised_commands(*path)]
            after = [
                (*path, command, *POSITIONAL_SAMPLE[(tool, command)], "-h")
                for command in advertised_commands(*path)
                if (tool, command) in POSITIONAL_SAMPLE
            ]
            for args, result in run_many(before + after).items():
                with self.subTest(cmd=" ".join(args)):
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertIn("usage", result.stdout.lower())

    def test_git_passthrough_keeps_help_for_git(self):
        """'repo git <args> -h' forwards -h to git: once args are passed through,
        the flag belongs to git, not to repo (git's own exit code applies)."""
        result = run_hammer("repo", "git", "status", "-h")
        self.assertIn("git status", result.stdout)
        self.assertNotIn("usage: repo", result.stdout)

    def test_help_is_never_json_wrapped(self):
        for args in (
            ["tasks", "-j", "-h"],
            ["check", "--dev", "-h"],
            ["repo", "-j", "merge", "-h"],
        ):
            with self.subTest(args=args):
                result = run_hammer(*args)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertTrue(
                    result.stdout.lstrip().startswith("usage"),
                    f"help was wrapped: {result.stdout[:80]}",
                )
                self.assertNotIn('"success"', result.stdout)


if __name__ == "__main__":
    unittest.main()
