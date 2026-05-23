# Pipeline Governance & Development Protocol

## Source of Truth
- **Branch**: `main`
- **Pipeline Flow**: `PROGRESSING` -> `TESTING` -> `REVIEW` -> `STAGING` -> `DONE`

## Branch Management
- All work must be performed on a dedicated task branch named: `<id>-<task-slug>`.
- Feature branches MUST be merged into `main` using `./hammer repo merge`. Manual Git merges are prohibited.
- **Post-Merge**: Once a branch is merged into `main`, the task must be finalized using `./hammer tasks reconcile --all`.

## Pipeline Gates
- **Pre-Merge Enforcement**: `.git/hooks/pre-merge` prevents direct merges to `main`.
- **Cryptographic Audit**: `hammer tasks audit <id>` generates a SHA256 hash of the patch, stored in `.tasks/review/<id>.audit`. Promotion is blocked if missing.
- **Verification Gate**: `hammer tasks verify <id> --proof "..."` generates a cryptographic hash of criteria and proof, stored in `.tasks/review/<id>.audit_hash`. Promotion to `STAGING` is blocked if criteria/proof have been tampered with post-verification.
- **Validation Gate**: Automated linting and testing are mandatory for transitions out of `TESTING` or `PROGRESSING`.

## Communication Protocol
- All communications regarding task progress must explicitly state:
    - Current pipeline state (e.g., PROGRESSING, REVIEW, STAGING, DONE).
    - Presence or absence of validation errors (lint/test).
    - Status of cryptographic audit hashes (if applicable).
- Avoid vague, subjective, or self-congratulatory statements.
- Never state "all work is complete" unless the task has reached terminal state (DONE/ARCHIVED).
