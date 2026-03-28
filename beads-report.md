# Beads Feature Report: Security & Robustness

This report documents security and robustness features from [beads (bd)](https://github.com/steveyegge/beads) applicable to tasks-ai (Python + Markdown, no database).

## 1. Security Features

### 1.1 Binary Verification with Checksums

**Description:** Verify downloaded binaries against release checksums before execution.

**Implementation:**
- Publish a `checksums.txt` file with each release containing SHA256 hashes
- Provide an install script that verifies checksums before installation
- Document manual verification steps for users

**Reference:** beads README - "Security And Verification" section

### 1.2 Input Validation

**Description:** Validate all user inputs to prevent injection attacks and ensure data integrity.

**Implementation:**
- Validate task IDs against a strict pattern (e.g., `^[0-9]+-[a-z-]+$`)
- Validate file paths before reading/writing
- Sanitize markdown content to prevent injection

**Reference:** beads SECURITY.md - "Command Injection Protection"

### 1.3 Actor Identity Tracking

**Description:** Track who created/updated each task for audit trails.

**Implementation:**
- Use `git config user.name` as default actor
- Allow override via environment variable (`TASKS_AI_ACTOR`) or flag
- Store `created_by` field in task metadata

**Reference:** beads CONFIG.md - "Actor Identity Resolution"

### 1.4 No Secrets Guidance

**Description:** Document that sensitive data should not be stored in task metadata.

**Implementation:**
- Add SECURITY.md documenting that passwords, API keys, secrets should not be stored in task content
- Task files are committed to version control

**Reference:** beads SECURITY.md - "Database Security"

### 1.5 Directory Permissions Guidance

**Description:** Recommend restrictive permissions on data directories.

**Implementation:**
- Document that the `.tasks/` directory should have restrictive permissions (0700)
- Prevents other local users from tampering with data

**Reference:** beads SECURITY.md - "Database Security"

---

## 2. Robustness Features

### 2.1 Debug Environment Variables

**Description:** Provide environment variables to enable debug logging for troubleshooting.

**Implementation:**
- `TASKS_AI_DEBUG` - General debug logging to stderr
- `TASKS_AI_DEBUG_FILE` - Write debug output to a file
- `TASKS_AI_DEBUG_VERBOSE` - Include verbose trace details

**Reference:** beads TROUBLESHOOTING.md - "Debug Environment Variables"

### 2.2 Health Check / Doctor Command

**Description:** Provide a command to diagnose task data health.

**Implementation:**
- `tasks-ai doctor` command
- Check task file integrity (valid YAML/markdown)
- Verify dependency links exist
- Report orphaned task files
- Optionally fix common issues (`--fix` flag)

**Reference:** beads TROUBLESHOOTING.md - "bd doctor --server"

### 2.3 Multi-Directory Detection

**Description:** Detect when multiple task directories exist in directory hierarchy.

**Implementation:**
- Warn user when multiple `.tasks/` directories detected
- Show which directory is being used
- Allow override via `TASKS_AI_DIR` environment variable

**Reference:** beads TROUBLESHOOTING.md - "Multiple databases detected warning"

### 2.4 Circular Dependency Detection

**Description:** Detect and prevent circular dependencies between tasks.

**Implementation:**
- `tasks-ai dep cycles` command
- Detect all dependency cycles
- Report the dependency causing the cycle
- Optionally auto-fix by removing one link

**Reference:** beads TROUBLESHOOTING.md - "Circular dependency errors"

### 2.5 Ready Work Detection

**Description:** List tasks that have no open blockers.

**Implementation:**
- `tasks-ai ready` command
- Only show tasks with no open `blocks` dependencies
- `tasks-ai blocked` to see blocked tasks

**Reference:** beads README - "Essential Commands" / `bd ready`

### 2.6 Validation on Create

**Description:** Validate task content on create operations.

**Implementation:**
- `validation.on-create` config: `none`, `warn`, `error`
- Validate required sections based on task type (story, tech, criteria, etc.)
- Check for missing required fields

**Reference:** beads CONFIG.md - "Example Config File"

### 2.7 Export Error Handling

**Description:** Configure how export operations handle errors.

**Implementation:**
- `strict`: Fail immediately on any error
- `best-effort`: Skip failed exports with warnings
- `partial`: Retry transient failures, skip with manifest

**Reference:** beads CONFIG.md - "Example: Export Error Handling"

### 2.8 Sandbox Mode for Restricted Environments

**Description:** Detect and adapt to sandboxed/restricted environments.

**Implementation:**
- Auto-detect sandboxed environments (container, limited permissions)
- Disable file system operations that require broad access
- Provide `--sandbox` flag for manual override
- Warn when operations may fail

**Reference:** beads TROUBLESHOOTING.md - "Sandboxed environments"

### 2.9 Hook Timeout Configuration

**Description:** Allow configuration of git hook timeouts.

**Implementation:**
- `TASKS_AI_HOOK_TIMEOUT` environment variable
- Default: 300 seconds (5 minutes)
- Increase for heavy pre-commit pipelines

**Reference:** beads TROUBLESHOOTING.md - "Hook timeout kills chained pre-commit hooks"

### 2.10 Comprehensive Troubleshooting Documentation

**Description:** Detailed troubleshooting guide for common issues.

**Implementation:**
- Create docs/TROUBLESHOOTING.md
- Include: debug variables, installation issues, file issues, git issues, platform-specific issues
- Provide clear diagnosis and fix steps

**Reference:** beads docs/TROUBLESHOOTING.md (1032 lines)

### 2.11 Configuration System

**Description:** Structured configuration via CLI with namespaces.

**Implementation:**
- `tasks-ai config set <key> <value>`
- `tasks-ai config get <key>`
- `tasks-ai config list`
- Namespaced keys (e.g., `validation.*`, `output.*`)
- Config stored in `.tasks/config.yaml` or `~/.config/tasks-ai/config.yaml`

**Reference:** beads CONFIG.md - "Project-Level Configuration (bd config)"

### 2.12 Dependency Tree Visualization

**Description:** Visualize task dependency tree to understand relationships.

**Implementation:**
- `tasks-ai dep tree <task-id>` command
- Limit depth to prevent deep traversals (`--max-depth`)
- Show dependency direction and types

**Reference:** beads TROUBLESHOOTING.md - "Dependencies not showing up"

### 2.13 Atomic File Operations

**Description:** Ensure file operations are crash-safe.

**Implementation:**
- Write to temp file first, then rename
- Prevents data loss on crash during write
- Handle file lock conflicts gracefully

**Reference:** beads CONFIG.md - "JSONL Backup"

---

## 3. Priority Recommendations

| Priority | Feature | Complexity | Impact |
|----------|---------|------------|--------|
| High | Input validation (ID pattern, paths) | Low | Security |
| High | Validation on create | Low | Robustness |
| High | Circular dependency detection | Medium | Robustness |
| Medium | Debug environment variables | Low | Debugging |
| Medium | Health check / doctor | Medium | Robustness |
| Medium | Troubleshooting docs | High | DX |
| Medium | Configuration system | Medium | UX |
| Low | Binary checksum verification | Medium | Security |
| Low | Actor identity tracking | Low | Audit |
| Low | Ready work / blocked detection | Low | UX |

---

## 4. Excluded (Database-Dependent)

The following beads features are not applicable to tasks-ai's Python + Markdown architecture:

- Circuit breaker for database connections
- Port conflict handling / shared server mode
- Import orphan handling (with resurrect mode)
- Database auto-commit
- Auto-push with debounce
- JSONL backup system (beads uses Dolt, we use git directly)

---

## 5. References

- [beads GitHub](https://github.com/steveyegge/beads)
- [beads SECURITY.md](https://github.com/steveyegge/beads/blob/main/SECURITY.md)
- [beads TROUBLESHOOTING.md](https://github.com/steveyegge/beads/blob/main/docs/TROUBLESHOOTING.md)
- [beads CONFIG.md](https://github.com/steveyegge/beads/blob/main/docs/CONFIG.md)
- [beads README](https://github.com/steveyegge/beads/blob/main/README.md)
