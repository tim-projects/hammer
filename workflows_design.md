# Workflow Design for Task 202

## Goal
Support type-based pipeline workflows, allowing different step sequences and gates for different task types (e.g., 'task' (code), 'docs', 'issue').

## Configuration Schema (config.yaml)
```yaml
workflows:
  default:
    steps: [BACKLOG, READY, PROGRESSING, TESTING, REVIEW, STAGING, DONE, ARCHIVED]
    gates:
      TESTING: [incomplete_checkboxes]
      STAGING: [regression_check, audit_integrity]
      DONE: [merge_check]
  docs:
    steps: [BACKLOG, READY, PROGRESSING, REVIEW, STAGING, DONE, ARCHIVED]
    gates:
      STAGING: [audit_integrity]
      DONE: [merge_check]
```

## Implementation Plan
1.  **Config Loader**: Update `tasks_ai/constants.py` or create a new config loader to parse `workflows` from `config.yaml`.
2.  **Pipeline Service**: Refactor `PipelineService` to lookup the workflow based on the task type (from metadata or filename).
3.  **Command Refactoring**: Update `tasks_ai/commands/move.py` to use type-specific allowed transitions from the resolved workflow.
