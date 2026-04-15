| `python check.py lint --fix` | Run linter with auto-fix |

## ⚠️ Error Handling

When using any tool (`tasks.py`, `repo.py`, `check.py`) and it errors or fails:
1. **STOP immediately** - Do not continue with further commands
2. **Report the error** - Tell the user what happened and the error message
3. **Wait for instruction** - Do not try to fix or work around the error without asking

## 🔑 Task References

- **Use Numeric Ids**: All commands accept the numeric task Id (e.g., `17`) instead of the filename. Run `python tasks.py list` to see Ids.
- **Show Task Details**: Show full task details with `python tasks.py show <id>`
- **Show Only Specific Sections**: Use `python tasks.py show <id> story|tech|criteria|plan|progress|repro`
- **Use `--dev` for testing**: Always use `--dev` flag when testing or doing dry runs
