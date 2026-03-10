# Tasks AI: The Agent-Optimized Task Manager

`tasks` is a Git-integrated task management system designed specifically for **Autonomous AI Agents**. It stores the "Single Source of Truth" directly within your repository using a dedicated Git worktree, making state and history immediately accessible to any agent with shell access.

## 🚀 One-Line Install

```bash
curl -sSL https://raw.githubusercontent.com/tim-projects/tasks-ai/main/install.sh | sudo bash
```

## 🛠️ Getting Started

To enable autonomous task management in your project, simply add the following directive to your `AGENTS.md` file:

> **Directive**: "Manage project tasks using the `tasks` command. Run `tasks --help` to discover the interface and follow the protocol defined in `TASKS_AI_AGENT_GUIDE.md`."

The agent will then autonomously:
1. Initialize the system (`tasks init`).
2. Discover or create tasks (`tasks list` / `tasks create`).
3. Manage work-in-progress and promotions through the Git-native state machine.

## 🤖 Why Agents Prefer This

- **JSON Interface**: Global `--json` flag for stable machine parsing.
- **Context Dense**: Short metadata keys (`Ti`, `St`, `Cr`) minimize token usage.
- **Git-Native**: Commits and technical notes are automatically embedded into the task records.
- **State Enforced**: Mandatory gates for Acceptance Criteria and Reproduction Steps ensure high-quality output.

---
*For technical implementation details, refer to [TASKS_AI_AGENT_GUIDE.md](./TASKS_AI_AGENT_GUIDE.md).*
