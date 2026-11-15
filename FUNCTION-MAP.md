# Codebase Function Map (`tasks_ai/`)

## 1. Core CLI Infrastructure (`cli.py`)
- **Initialization & Lifecycle**
    - `__init__`: Initializes the CLI context, logging, and configuration.
    - `init`: Sets up the task environment, including hooks.
    - `upgrade`: Handles self-upgrade logic.
- **Task Management**
    - `create`, `modify`, `delete`, `show`, `list`: CRUD operations for tasks.
    - `move`: Handles task state transitions, including pipeline gates.
    - `find_task`: Utility to locate a task by ID.
    - `checkpoint`, `save`, `restore`: Handles task state persistence and backup.
- **Git & Pipeline Integration**
    - `_run_git`: Wrapper for all `git` commands.
    - `_validate_pipeline_gate`: Enforces rules defined in `GEMINI.md` (audit, Rc flag, etc.).
    - `_git_merge_transition`: Atomic Git branch management for pipeline moves.
    - `_auto_archive`: Automated maintenance of archived tasks.
- **Validation & Health**
    - `doctor`: Comprehensive suite of diagnostic checks for the repo structure and health.
    - `audit`, `verify`: Cryptographic verification of criteria.
    - `_check_audit_integrity`: Integrity check for task artifacts.

## 2. Data Persistence (`file_manager.py`)
- `load`, `dump`: Handles serialization and deserialization of tasks.
- `_atomic_write`: Ensures file system operations on task files are atomic.

## 3. Configuration (`constants.py`, `models.py`)
- `load_config`, `save_config`: Manages project-wide and user-local configurations.
- `Task` (Model): Representation of a task's internal data structure.

## 4. Validation Layer (`validation.py`)
- `run_lint`, `run_tests`: Automated quality assurance tools triggered by the gatekeeper.
