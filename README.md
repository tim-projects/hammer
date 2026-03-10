# Tasks: The Agent-Optimized Task Manager

`tasks` is a high-density, Git-integrated task management system designed specifically for **Autonomous AI Agents** and high-velocity developers.

Unlike traditional project management tools, `tasks` stores the "Single Source of Truth" directly within your repository using a dedicated Git worktree. This ensures that task state, technical findings, and branch commits are always perfectly synchronized with your code—accessible to any AI agent that can run a shell.

## 🤖 Why Agents Love It

- **JSON First**: Every command supports a `--json` flag for unbroken, machine-parseable data streams.
- **Context Efficient**: Metadata keys are minimized (e.g., `Ti` for Title, `St` for State) to save token space while remaining human-readable via CLI expansion.
- **Self-Documenting**: The tool enforces "Gates" (Requirements, Acceptance Criteria, Reproduction Steps) that guide agents to provide high-quality work.
- **Git-Native**: It automatically embeds branch commits and progress findings into the task record.

## 🚀 Installation

Install the tool system-wide to enable the `tasks` command in any directory:

```bash
git clone https://github.com/tim-projects/tasks-cli.git
cd tasks-cli
chmod +x install.sh
sudo ./install.sh
```

## 🛠️ Getting Started

1. **Initialize** your project:
   ```bash
   tasks init
   ```
   *This creates a hidden `.tasks` worktree and a `tasks/` directory in your `.gitignore`.*

2. **Create** your first task:
   ```bash
   tasks create "Implement OAuth Flow" --type task
   ```

3. **List** active work:
   ```bash
   tasks list
   ```

## 🤖 The "AGENTS.md" Workflow

The most powerful way to use this tool is by combining it with a task-handoff file like `AGENTS.md`.

1. **Install** the `tasks` tool.
2. **Create** an `AGENTS.md` file in your project root.
3. **Add** high-level directives to `AGENTS.md` (e.g., "Fix the login bug", "Implement the new dashboard").
4. **The Bot Does the Rest**: Your AI agent (like Gemini CLI) will:
   - Detect the `AGENTS.md` file.
   - Use `tasks create` to formalize the request.
   - Use `tasks move ... PROGRESSING` to start work.
   - Perform the code changes and `tasks checkpoint` to sync progress.
   - Move the task through `TESTING`, `REVIEW`, and `LIVE`.

## 📖 Command Reference

For detailed agent implementation details, see [TASKS_CLI_AGENT_GUIDE.md](./TASKS_CLI_AGENT_GUIDE.md).

| Command | Description |
| :--- | :--- |
| `tasks init` | Bootstrap the tasks system in a repo. |
| `tasks list` | View active tasks by priority. |
| `tasks current` | See details of the active task. |
| `tasks create` | Add a new Task or Issue. |
| `tasks move` | Transition a task (e.g., to `TESTING`). |
| `tasks link` | Block one task with another. |
| `tasks checkpoint`| Sync current commits and notes. |

---
*Built for the next generation of autonomous engineering.*
