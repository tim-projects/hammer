

- Progress: Fixed check.py's project root detection and deadlock issue. Implemented find_project_root() that searches from script location. Replaced subprocess.Popen with subprocess.run using temporary files for capture (JSON) and direct streaming (normal) to avoid pipe deadlocks. Removed debug prints. Verified check.py test completes (takes ~2 minutes) and all other tools work from /opt/tasks-ai.
- Findings: The "No lint tool configured" error was due to check.py using os.getcwd() to locate .tasks/config, which fails when running from /opt. The hang was caused by using Popen with stdout/stderr pipes; pytest child processes inherited those pipes and kept them open, causing communicate() to block indefinitely. 
- Mitigations: Using subprocess.run without capture for normal output avoids deadlock; for JSON output, temporary files are used. Config is now found regardless of cwd.
- Next steps: Run full validation (check.py all), commit and push changes, reinstall, then merge to main.