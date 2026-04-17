# Ship Faster with AI-Powered Git-Backed Project Management

`tasks` gives your project a complete project management system that dones IN your repo. State machines, quality gates, audit trails, full automation - all powered by git worktrees, designed for AI agents.

## 🚀 One-Line Install

### Local (No Sudo)
Installs to `~/.local/bin/tasks`.
```bash
curl -sSL https://raw.githubusercontent.com/tim-projects/tasks/main/install.sh | bash
```

### System-Wide (Global)
Installs to `/usr/local/bin/tasks`.
```bash
curl -sSL https://raw.githubusercontent.com/tim-projects/tasks/main/install.sh | sudo bash -s -- -g
```

## 🛠️ Getting Started

To enable autonomous task management in your project, add the following directive to your `AGENTS.md` file:

> **Directive**: "Manage project tasks using the `tasks` command. Run `tasks -h` to discover the interface and operational protocol."

The agent will then autonomously:
1. Initialize the system (`tasks init`)
2. Discover or create tasks (`tasks list` / `tasks create`)
3. Manage work-in-progress and promotions through the Git-native state machine

## The Problem

AI agents working on code need to know what exists, track progress, meet quality gates, handle blockers, and report results reliably. Without structure, they improvise, skip steps, lose track, and can't communicate status.

## The Solution

`tasks` gives you a deterministic state machine with quality gates. Agents follow the lifecycle, meeting criteria at each step before advancing - no shortcuts, no surprises.

### The State Machine

```
BACKLOG → READY → PROGRESSING → TESTING → REVIEW → STAGING → DONE → ARCHIVED
                                          ↓        ↑
                                     (regression check needed)
                                          ↓
                                     (back to fix if fails)
```

Each transition has rules:
- Can't move to PROGRESSING without complete story/tech/criteria/plan
- Can't move to TESTING without passing your own verification
- Can't move to REVIEW without tests passing and branch pushed
- **Can't move to STAGING without passing regression check (Rc)** — review diff at `.tasks/review/<id>/diff.patch`, if regressions found move task back to PROGRESSING/TESTING to fix
- Can't move to DONE without being merged to main
- Can't move to ARCHIVED without merged to main (or REJECTED)

## Why It's Different

| Instead of... | tasks gives you... |
|--------------|-------------------|
| Scattered notes & PR comments | Everything in one place, git-backed |
| Manual status updates | State machine with enforced gates |
| Lost context when switching tasks | Full audit trail, every change logged |
| Wondering "what's ready to ship?" | Clear pipeline: testing → staging → done |
| No parallel agent coordination | Atomic IDs, branch-per-task, blockers |
| Disconnected tooling | Integrated: lint, test, typecheck, format - all in one command |
| Fragile project state | Self-healing: auto-restore from remote |

## Commands Overview

### Task Management

```bash
tasks init                          # Initialize task system
tasks list                          # List all tasks with Id, Priority, Summary
tasks create "Task title"           # Create new task (requires 10+ char title)
tasks create "Issue title" --type issue --repro "Steps to reproduce"
tasks show <id>                     # Show full task details
tasks show <id> story               # Show only story section
tasks show <id> progress            # Show active progress notes
tasks current                       # Show active task
tasks checkpoint                    # Sync commits/notes to task record
```

### State Transitions

```bash
tasks move <id> PROGRESSING         # Start working (creates branch)
tasks move <id> TESTING             # Move to testing
tasks move <id> REVIEW              # Move to review
tasks move <id> STAGING             # Move to staging
tasks move <id> DONE                # Move to done (requires merged to main)
tasks move <id> ARCHIVED -y         # Archive (pushes branch, deletes local)

# Multi-step moves - chain multiple states
tasks move <id> READY,PROGRESSING,TESTING  # Backlog to Testing in one command
```

### Dependencies & Links

```bash
tasks link <id> <blocker-id>        # Block task until blocker resolved
tasks unlink <id> <blocker-id>      # Remove blocker relationship
```

### Modification

```bash
tasks modify <id> --story "..."     # Update story
tasks modify <id> --plan "1. Step"  # Update implementation plan
tasks modify <id> --priority 1      # Change priority
tasks modify <id> --regression-check # Mark regression check as passed (enables STAGING)
tasks undo <id>                     # Undo last operation on task
```

### Cleanup & Maintenance

```bash
tasks cleanup --dry-run             # Preview what would be cleaned
tasks cleanup                       # Clean merged branches, push to remote, delete local
tasks reconcile                     # Scan for tasks with merged branches (dry-run)
tasks reconcile --all               # Clean up merged branches and archive tasks
tasks doctor                        # Diagnose task data and git state
```

### Development Tools

```bash
check lint                      # Run linter
check test                      # Run tests
check typecheck                 # Run type checker
check format                    # Run formatter
check all                       # Run all checks
check lint --fix               # Auto-fix lint errors
```

### Validation & Tools

```bash
tasks run lint                      # Run linter (config: repo.lint)
tasks run test                      # Run tests (config: repo.test)
tasks run typecheck                 # Run type checker (config: repo.type_check)
tasks run format                    # Run formatter (config: repo.format)
tasks run all                       # Run all checks

tasks config list                   # Show current configuration
tasks config detect                 # Auto-detect project tools
tasks config set repo.test pytest   # Set test tool
```

### Repository Integration

```bash
repo merge <src> to <target>  # Merge with compliance checks
repo promote <id>            # Promote through pipeline: testing → staging → main
repo sync                    # Sync: testing → staging → main
repo status                  # Show current branch and pending changes
repo branch list             # List all branches
```

## Task File Structure

Tasks are stored as markdown files with YAML frontmatter:

```yaml
---
Id: 42
Ti: Fix login bug
St: PROGRESSING
Ty: issue
Cr: 2024-01-15
Up: 2024-01-16
Pr: 1
Lb: [bug, login, security]
---
## Story
As a user I cannot log in with special characters in password...

## Technical
The password validation regex doesn't handle Unicode...

## Criteria
- [ ] User can log in with any valid password
- [ ] Invalid passwords show clear error message

## Plan
1. Update password validation regex
2. Add tests for Unicode passwords
3. Update error messages

## Progress
- Found the issue in auth.py line 42
- Created fix, running tests
```

## Workflow Example

```bash
# Agent initializes on first run
tasks init

# Agent creates work with full specification
tasks create "Add user login" \
  --story "As a user I want to log in..." \
  --tech "Use OAuth2 with GitHub provider..." \
  --criteria "User can log in with GitHub" \
  --plan "1. Register OAuth app" "2. Implement OAuth flow" "3. Add session management"

# Agent starts working (creates branch automatically)
tasks move 1 PROGRESSING

# Agent writes progress notes and checkpoints
# ... work happens ...
tasks checkpoint

# Agent verifies and moves to testing
tasks run test
tasks move 1 TESTING

# Agent moves to review (auto-generates diff, requires regression check)
tasks move 1 REVIEW

# Agent reviews .tasks/review/1/diff.patch for regressions
# If regressions found, task moves back to PROGRESSING/TESTING to fix:
tasks move 1 PROGRESSING  # Fix issues

# Once clean, agent marks regression check passed
tasks modify 1 --regression-check

# Now can promote to staging
tasks move 1 STAGING

# Once PR merged to main, archive
tasks move 1 ARCHIVED -y
```

## Regression Check

When a task enters REVIEW, the system automatically generates a unified diff patch at `.tasks/review/<task_id>/diff.patch`. This diff includes:
- All commits on the task branch that are not in `main`
- Any unstaged working tree changes

**Agent workflow:**
1. On `REVIEW` entry, read the diff file
2. Inspect for potential regressions, breaking changes, or unwanted side effects
3. If regressions found → move task back to `PROGRESSING` or `TESTING` for fixes
4. If diff is clean → run `tasks modify <id> --regression-check` to mark as passed
5. STAGING promotion is blocked until `--regression-check` is confirmed

This gate ensures code with regressions never reaches STAGING.

## Why This Over Alternatives?

- **No external services** - Everything in your repo
- **No setup** - Single Python file, zero deps
- **Git-native** - Leverages existing infrastructure
- **Enforced quality** - Can't bypass gates
- **Agent-optimized** - JSON output, clear protocols, deterministic behavior
- **Full project lifecycle** - From backlog to done with proper gates
- **Self-healing** - Auto-restore branches, circular dependency prevention
- **Comprehensive audit** - Activity logging, undo, checkpoint

## Configuration

Tasks auto-detects your project's tools. Configure manually:

```bash
tasks config set repo.lint ruff
tasks config set repo.test pytest
tasks config set repo.type_check pyright
tasks config set repo.format ruff
```

## Documentation

- [TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md) - Common issues and solutions
- [AGENTS.md](AGENTS.md) - Agent directives and protocols# test
