# Global JSON flag matrix

`hammer` treats `-j` and `--json` as a wrapper-level output directive. The flag may
appear before the tool, between the tool and command, after the command, or after
command arguments. The wrapper removes it from the command-specific argument list
and passes one canonical `--json` to the selected tool.

## Tools and commands

| Tool | Commands |
| --- | --- |
| `tasks` | `init`, `init-hooks`, `save`, `restore`, `list`, `current`, `show`, `review`, `checkpoint`, `link`, `unlink`, `unarchive`, `create`, `audit`, `modify`, `move`, `delete`, `mount`, `reconcile`, `cleanup`, `config`, `upgrade`, `check`, `undo`, `verify`, `doctor` |
| `check` | `lint`, `test`, `typecheck`, `format`, `debug`, `all` |
| `repo` | `merge`, `promote`, `demote`, `sync`, `commit`, `git`, `status`, `check-merged`, `check-merged-testing`, `branch` (`list`, `create`, `delete`, `exists`) |
| `guard` | `check`, `scan`, `refresh`, `rebuild`, `hooks` |

The same commands are available through auto-detected aliases, for example
`hammer list` and `hammer scan`, with the same JSON flag placement rules.

## Flag permutations

For every command in the table, these forms are equivalent:

```text
hammer -j <tool> <command> [args]
hammer <tool> -j <command> [args]
hammer <tool> <command> -j [args]
hammer <tool> <command> [args] -j
```

The corresponding long form `--json` is accepted in the same positions. Help
flags override the directive: `hammer -j <tool> <command> -h` and the other
help positions print plain-text help and do not emit JSON.

Command-specific flags remain command-specific. The global directive does not
change the meaning of flags such as `--dev`, `--quiet`, `--yes`, `--fix`, or
`--all`.
