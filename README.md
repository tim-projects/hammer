# Tasks AI: Task Management for AI Agents

`tasks-ai` gives AI agents a structured way to manage their work. It lives in your Git repo and provides a reliable framework for agents to track, progress, and complete tasks without requiring human intervention at every step.

## 🚀 One-Line Install

### Local (No Sudo)
Installs to `~/.local/bin/tasks-ai`.
```bash
curl -sSL https://raw.githubusercontent.com/tim-projects/tasks-ai/main/install.sh | bash
```

### System-Wide (Global)
Installs to `/usr/local/bin/tasks-ai`.
```bash
curl -sSL https://raw.githubusercontent.com/tim-projects/tasks-ai/main/install.sh | sudo bash -s -- -g
```

## 🛠️ Getting Started

To enable autonomous task management in your project, simply add the following directive to your `AGENTS.md` file:

> **Directive**: "Manage project tasks using the `tasks-ai` command. Run `tasks-ai -h` to discover the interface and operational protocol."

The agent will then autonomously:
1. Initialize the system (`tasks-ai init`).
2. Discover or create tasks (`tasks-ai list` / `tasks-ai create`).
3. Manage work-in-progress and promotions through the Git-native state machine.

## The Problem

AI agents working on code need to:
- Know what tasks exist and their priority
- Understand what state each task is in
- Track their progress as they work
- Know when work is ready for review
- Handle blockers and dependencies
- Report results back reliably

Without a structured system, agents improvise. They skip steps, lose track of what's done, and can't communicate their status reliably.

## The Solution

`tasks-ai` provides a deterministic state machine with quality gates. Agents must follow the lifecycle, meeting criteria at each step before advancing.

### The State Machine

```
BACKLOG → READY → PROGRESSING → TESTING → REVIEW → STAGING → ARCHIVED
                                    ↓                    ↓
                               BLOCKED              REJECTED
```

Each transition has rules:
- Can't move to PROGRESSING without complete story/tech/criteria/plan
- Can't move to TESTING without passing your own verification
- Can't move to REVIEW without being on a branch
- Can't move to ARCHIVED without code merged to main (or moved to REJECTED)

## Key Features

| Feature | Benefit |
|---------|---------|
| **Atomic Task IDs** | Race-condition free ID generation for parallel agent operations |
| **Quality Gates** | Tasks can't advance without meeting requirements |
| **Branch Per Task** | Each task gets its own branch, automatically managed |
| **Auto-Archive** | When code merges to main, task auto-archives with branch cleanup |
| **Full Audit Trail** | Every state change is a Git commit |
| **Progress Tracking** | Agents write notes to task files as they work |
| **JSON Output** | Reliable parsing for agent consumption |
| **Zero Dependencies** | Works with Python standard library only |

## How It Improves Workflow

1. **Reliable Execution** - Agents can't skip steps or advance prematurely
2. **Traceability** - Every action creates a commit, full history in Git
3. **Blocker Handling** - Clear protocol for when work can't proceed
4. **Parallel Safety** - File locking ensures multiple agents don't conflict
5. **Self-Documenting** - Task files contain story, tech, criteria, plan, and progress

## Quick Start

```bash
# Add to AGENTS.md so agents discover the tool:
# "Manage project tasks using the tasks-ai command. Run tasks-ai -h to discover the interface."

# Agent initializes on first run
tasks-ai init

# Agent creates work
tasks-ai create "Add user login" \
  --story "..." --tech "..." --criteria "..." --plan "..."

# Agent starts working (creates branch automatically)
tasks-ai move 1 PROGRESSING

# Agent progresses through states
tasks-ai move 1 TESTING
tasks-ai move 1 REVIEW

# When code merges to main, agent archives
tasks-ai move 1 ARCHIVED -y  # pushes branch, deletes local, archives

# Or use cleanup to scan and clean all merged branches
tasks-ai cleanup --dry-run   # preview what would be cleaned
tasks-ai cleanup             # clean merged branches and archive tasks
```

## Why This Over alternatives?

- **No external services** - Everything in your repo
- **No setup** - Single Python file, zero deps
- **Git-native** - Leverages existing infrastructure
- **Enforced quality** - Can't bypass gates
- **Agent-optimized** - JSON output, clear protocols, deterministic behavior