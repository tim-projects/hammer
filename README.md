# Tasks AI: Git-Backed Project Management for AI Agents

`tasks` is a comprehensive project management system built on Git. It provides a structured workflow for AI agents to manage work from conception to completion, with quality gates at every stage, full audit trails, and reliable state management.

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

AI agents working on code need to:
- Know what tasks exist and their priority
- Understand what state each task is in
- Track their progress as they work
- Know when work is ready for review
- Handle blockers and dependencies
- Report results back reliably
- Maintain audit trails of all decisions and changes

Without a structured system, agents improvise, skip steps, lose track of what's done, and can't communicate their status reliably.

## The Solution

`tasks` provides a deterministic state machine with quality gates. Agents must follow the lifecycle, meeting criteria at each step before advancing.

### The State Machine

```
BACKLOG → READY → PROGRESSING → TESTING → REVIEW → STAGING → LIVE → ARCHIVED
                                              ↓                    ↓
                                         REJECTED              REJECTED
```

Each transition has rules:
- Can't move to PROGRESSING without complete story/tech/criteria/plan
- Can't move to TESTING without passing your own verification
- Can't move to REVIEW without tests passing and branch pushed
- Can't move to STAGING without passing review checks
- Can't move to LIVE without being merged to main
- Can't move to ARCHIVED without merged to main (or REJECTED)

## Key Features

| Feature | Benefit |
|---------|---------|
| **Atomic Task IDs** | Race-condition free ID generation for parallel agent operations |
| **Quality Gates** | Tasks can't advance without meeting requirements |
| **Branch Per Task** | Each task gets its own branch, automatically managed |
| **Dependency Management** | Block tasks until blockers are resolved |
| **Circular Dependency Prevention** | Automatically detects and prevents circular blocker relationships |
| **Activity Logging** | Full audit trail of all task operations |
| **Undo Capability** | Revert the last operation on a task |
| **Self-Healing** | Auto-restore branches from remote when resuming archived tasks |
| **Health Checks** | `tasks doctor` diagnoses data integrity and git state |
| **Integrated Validation** | Run lint/test/typecheck/format via `tasks run` |
| **Config Detection** | Auto-detect project tools (ruff, pytest, pyright, etc.) |
| **Full Audit Trail** | Every state change is a Git commit |
| **JSON Output** | Reliable parsing for agent consumption |
| **Zero Dependencies** | Works with Python standard library only |

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
tasks move <id> LIVE                # Move to live (requires merged to main)
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
tasks modify <id> --priority 1     # Change priority
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
python repo.py merge <src> to <target>  # Merge with compliance checks
python repo.py promote <id>            # Promote through pipeline: testing → staging → main
python repo.py sync                    # Sync: testing → staging → main
python repo.py status                  # Show current branch and pending changes
python repo.py branch list             # List all branches
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

# Agent moves to review (requires tests passing)
tasks move 1 REVIEW

# Once PR reviewed and merged to main, archive
tasks move 1 ARCHIVED -y
```

## Why This Over Alternatives?

- **No external services** - Everything in your repo
- **No setup** - Single Python file, zero deps
- **Git-native** - Leverages existing infrastructure
- **Enforced quality** - Can't bypass gates
- **Agent-optimized** - JSON output, clear protocols, deterministic behavior
- **Full project lifecycle** - From backlog to live with proper gates
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
- [AGENTS.md](AGENTS.md) - Agent directives and protocols