"""
check - Run validation and quality checks on the codebase
Usage: check <command> [options]

Commands:
  lint         - Run linter
  test         - Run tests
  typecheck    - Run type checker
  format       - Run formatter
  all          - Run all checks

Options:
  --fix        - Apply fixes where possible
  --json       - JSON output
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

def get_git_root():
    try:
        return subprocess.check_output(['git', 'rev-parse', '--show-toplevel'], stderr=subprocess.DEVNULL).decode().strip()
    except Exception:
        return os.getcwd()

def find_project_root(start_path=None):
    """Search upward for .tasks directory or .git directory."""
    if start_path is None:
        start_path = os.getcwd()
    current = os.path.abspath(start_path)
    while True:
        if os.path.isdir(os.path.join(current, '.tasks')) or os.path.isdir(os.path.join(current, '.git')):
            return current
        parent = os.path.dirname(current)
        if parent == current:
            break
        current = parent
    return Path(__file__).parent.resolve()
ROOT = find_project_root()

def load_config(dev=False):
    project_root = find_project_root()
    if dev:
        config_path_yaml = '/tmp/.tasks/config.yaml'
    else:
        config_path_yaml = os.path.join(project_root, '.tasks', 'config.yaml')
    config_path_toml = os.path.join(project_root, 'pyproject.toml')
    config = {}
    if os.path.exists(config_path_yaml):
        try:
            import yaml
            with open(config_path_yaml, 'r') as f:
                config.update(yaml.safe_load(f) or {})
        except ImportError:
            print("Warning: 'PyYAML' library not found. Skipping config.yaml parsing.", file=sys.stderr)
        except Exception as e:
            print(f'Warning: Could not parse {config_path_yaml}: {e}', file=sys.stderr)
    if os.path.exists(config_path_toml):
        try:
            import toml
            with open(config_path_toml, 'r') as f:
                pyproject_data = toml.load(f)
                config_section = pyproject_data.get('tool', {}).get('tasks_ai', {}).get('repo', {})
                config.update(config_section)
        except ImportError:
            pass
        except Exception as e:
            print(f'Warning: Could not parse pyproject.toml: {e}', file=sys.stderr)
    return config

def get_tool(config, tool_type):
    key_map = {'lint': 'repo.lint', 'test': 'repo.test', 'typecheck': 'repo.type_check', 'format': 'repo.format'}
    return config.get(key_map.get(tool_type))

def get_commands(fix=False):
    return {'lint': {'ruff': ['ruff', 'check', '.'] + (['--fix'] if fix else []), 'pylint': ['pylint', '.'], 'eslint': ['npx', 'eslint', '.'] + (['--fix'] if fix else []), 'oxlint': ['npx', 'oxlint', '.'] + (['--fix'] if fix else []), 'golangci-lint': ['golangci-lint', 'run', './...'] + (['--fix'] if fix else [])}, 'test': {'pytest': ['pytest'], 'go test': ['go', 'test', './...'], 'cargo test': ['cargo', 'test'], 'npm test': ['npm', 'test']}, 'typecheck': {'mypy': ['mypy', '.'], 'pyright': ['npx', 'pyright'], 'typescript': ['npx', 'tsc', '--noEmit']}, 'format': {'ruff': ['ruff', 'format', '.'] + (['--check'] if not fix else []), 'prettier': ['npx', 'prettier', '--write', '.'] if fix else ['npx', 'prettier', '--check', '.'], 'rustfmt': ['cargo', 'fmt'] + (['--check'] if not fix else [])}}

def run_check(tool_type, fix=False, as_json=False, dev=False):
    sys.stderr.flush()
    config = load_config(dev)
    sys.stderr.flush()
    key_map = {'lint': 'repo.lint', 'test': 'repo.test', 'typecheck': 'repo.type_check', 'format': 'repo.format'}
    config_key = key_map.get(tool_type)
    tool = config.get(config_key)
    sys.stderr.flush()
    commands = get_commands(fix).get(tool_type, {})
    sys.stderr.flush()
    tool_basename = os.path.basename(tool) if tool else None
    lookup_key = tool_basename if tool and tool_basename in commands else tool
    if not tool or lookup_key not in commands:
        msg = f"No {tool_type} tool configured (expected key: {config_key}). Run 'tasks config detect' or set manually: tasks config set {config_key} <tool>"
        if as_json:
            print(json.dumps({'success': False, 'tool': tool_type, 'error': msg, 'configured': tool}))
        else:
            print(f'Error: {msg}')
        return 1
    cmd = commands[lookup_key].copy()
    project_root = find_project_root()
    cmd0 = shutil.which(cmd[0])
    if not cmd0:
        venv_bin = os.path.join(project_root, 'venv', 'bin', cmd[0])
        if os.path.exists(venv_bin):
            cmd0 = venv_bin
    if not cmd0:
        msg = f"Tool '{cmd[0]}' not found in PATH. Install it or check configuration."
        if as_json:
            print(json.dumps({'success': False, 'tool': tool_type, 'error': msg, 'configured': tool}))
        else:
            print(f'Error: {msg}')
        return 1
    cmd[0] = cmd0
    cmd_to_run = cmd.copy()
    env = os.environ.copy()
    if tool == 'pytest':
        cmd_to_run.append(project_root)
        cmd_to_run.append('--cache-clear')
        cmd_to_run.extend(['test_cli_robustness.py', 'test_repo.py', 'test_security.py', '--ignore=test_tasks.py', '--ignore=test_robustness.py'])
        env['PYTHONPATH'] = project_root
    if not as_json:
        print(f'Running {tool} ({tool_type})...')
    try:
        if as_json:
            with tempfile.NamedTemporaryFile(mode='w+b', delete=False) as stdout_file, tempfile.NamedTemporaryFile(mode='w+b', delete=False) as stderr_file:
                result = subprocess.run(cmd_to_run, cwd=project_root, stdout=stdout_file, stderr=stderr_file, timeout=300, env=env, check=False)
                stdout_file.seek(0)
                stderr_file.seek(0)
                stdout_content = stdout_file.read().decode('utf-8', errors='replace')
                stderr_content = stderr_file.read().decode('utf-8', errors='replace')
            try:
                os.unlink(stdout_file.name)
                os.unlink(stderr_file.name)
            except Exception:
                pass
        else:
            result = subprocess.run(cmd_to_run, cwd=project_root, timeout=300, env=env, check=False)
            stdout_content = ''
            stderr_content = ''
    except subprocess.TimeoutExpired:
        msg = f"Tool '{tool}' timed out after 5 minutes."
        if as_json:
            print(json.dumps({'success': False, 'tool': tool_type, 'error': msg, 'configured': tool}))
        else:
            print(f'Error: {msg}')
        return 1
    result.stdout = stdout_content
    result.stderr = stderr_content
    if as_json:
        print(json.dumps({'success': result.returncode == 0, 'tool': tool_type, 'configured': tool, 'stdout': result.stdout, 'stderr': result.stderr, 'exit_code': result.returncode}))
    else:
        if result.stdout:
            print(result.stdout)
        if result.stderr:
            print(result.stderr, file=sys.stderr)
        if result.returncode == 0:
            print(f'✅ {tool} passed')
        else:
            print(f'❌ {tool} failed')
            print('\n⚠️ Do not bypass the tool - fix the actual code issues, not the validation config.')
            print('   See AGENTS.md - Never Skip or Bypass section.')
    return result.returncode

def get_current_hash():
    try:
        return subprocess.check_output(['git', 'rev-parse', 'HEAD'], stderr=subprocess.DEVNULL).decode().strip()
    except Exception:
        return None

def get_last_hash_path():
    return os.path.join(find_project_root(), '.tasks', '.last_validation_hash')

def run_all(fix=False, as_json=False, dev=False):
    current_hash = get_current_hash()
    hash_path = get_last_hash_path()
    if not fix and current_hash and os.path.exists(hash_path):
        with open(hash_path, 'r') as f:
            last_hash = f.read().strip()
        if last_hash == current_hash:
            if not as_json:
                print('✅ Codebase unchanged, skipping validation.')
            return 0
    results = {}
    total_code = 0
    for check in ['lint', 'test', 'typecheck', 'format']:
        code = run_check(check, fix, as_json, dev)
        results[check] = code
        if code != 0:
            total_code = 1
    if total_code == 0 and current_hash:
        with open(hash_path, 'w') as f:
            f.write(current_hash)
    if not as_json:
        print('\n' + '=' * 40)
        all_passed = total_code == 0
        if all_passed:
            print('✅ All checks passed')
        else:
            print('❌ Some checks failed')
            for check, code in results.items():
                status = '✅' if code == 0 else '❌'
                print(f'  {status} {check}')
            print('\n⚠️ IMPORTANT: Do not modify validation config or disable checks to hide errors.')
            print('   See AGENTS.md - Never Skip or Bypass section.')
            print('   Fix the actual code issues, not the validation tool.')
    return total_code

def main():
    parser = argparse.ArgumentParser(prog='check', description='Run validation and quality checks on the codebase')
    parser.add_argument('command', nargs='?', choices=['lint', 'test', 'typecheck', 'format', 'all'], help='Check to run')
    parser.add_argument('--fix', action='store_true', help='Apply fixes where possible')
    parser.add_argument('--json', action='store_true', help='JSON output')
    parser.add_argument('--dev', action='store_true', help='Use /tmp/.tasks for config')
    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        return 1
    if args.command == 'all':
        return run_all(args.fix, args.json, args.dev)
    else:
        return run_check(args.command, args.fix, args.json, args.dev)
if __name__ == '__main__':
    sys.exit(main())