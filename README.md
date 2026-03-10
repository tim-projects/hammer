# Tasks AI: The Agent-Optimized Task Manager

`tasks-ai` is a Git-integrated task management system designed specifically for **Autonomous AI Agents**. It stores the "Single Source of Truth" directly within your repository using a dedicated Git worktree, making state and history immediately accessible to any agent with shell access.

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

## 🤖 Why Agents Prefer This

- **Zero Dependencies**: Standard library Python only. No `pip install` required.
- **JSON Interface**: Global `-j` flag for stable machine parsing.
- **Context Dense**: Short metadata keys (`Ti`, `St`, `Cr`) minimize token usage.
- **Git-Native**: Commits and technical notes are automatically embedded into the task records.
- **State Enforced**: Mandatory gates for Acceptance Criteria and Reproduction Steps ensure high-quality output.

---
*For technical details, run `tasks-ai -h`.*
