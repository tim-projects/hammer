# **HAMMER IS BOSS.** LLM SUBMIT. POUND weak code through quality gates to DONE! **CODE QUALITY 10X!**

<img src="hammer-icon.webp" width="300"/>

Your lite/small local or cloud LLM writes code. Without HAMMER you get toy prototypes that break in production. HAMMER blocks weak code with test and lint gates, forces complete specs, and tracks every change in git.

Agents can't skip steps. Result: shippable code that doesn't explode in production.

**Zero deps. Git-powered. One-line install.**

## Ship BETTER and CHEAPER with HAMMER: AI-Powered Git-Backed Project Management 🔨⚔️

`tasks` = complete system IN your repo.  
State machines + quality gates + audit trails + git worktrees.  
**Built for AI agents.**

## 🚀 One-Line Install

**HAMMER SMASH INSTALL!**
```bash
curl -sSL https://raw.githubusercontent.com/tim-projects/hammer/main/install.sh | bash
```
Installs `hammer` to `~/.local/bin/hammer`. No sudo.

**Global HAMMER:**
```bash
curl -sSL https://raw.githubusercontent.com/tim-projects/hammer/main/install.sh | sudo bash -s -- --system
```

**Note:** After installation, if `hammer` commands are not found, run `hash -r` to refresh your shell's command cache, or open a new terminal window. This ensures the shell recognizes the newly created symlinks.

## 🛠️ Getting Started

Add this to the top of your AGENTS.md:

```
Directive: "Manage project tasks using the tasks command. Run hammer tasks -h to discover the interface and operational protocol."
```

Agent autonomously runs:
1. `hammer tasks init` - Initialize system
2. `hammer tasks list` / `hammer tasks create` - Discover/create tasks
3. `hammer tasks move` - Move through Git-native state machine

## 🔨 HAMMER PIPELINE

**HAMMER DRIVES THE PIPELINE. WEAK CODE GETS SMASHED.**

The Hammer Pipeline forces code through mandatory **Stages**, ensuring compliance through automated **Checks (Guardrails)** and atomic **Jobs**.

| Terminology | Hammer's "Brutalist" Twist |
| :--- | :--- |
| **Pipeline** | The forced path to production. |
| **Stage** | A mandatory segment that *must* be completed. |
| **Job** | An atomic action—the tool executes with maximum force. |
| **Check** | A validation "Guardrail"—the pipeline halts if these fail. |

### 1. Pipeline Structure
The Pipeline consists of sequential Stages (BACKLOG -> READY -> PROGRESSING -> TESTING -> REVIEW -> STAGING -> DONE -> ARCHIVED).

* **Automation Engine:** The mechanism that executes the Pipeline.
* **Automation Rule:** The Automation Engine will chain all Jobs within a Stage automatically.
* **Halt Policy:** The Pipeline halts only when a Check fails or Manual Intervention (e.g., audit) is required.

## 🔨 HAMMER PIPELINE STAGES

```
BACKLOG → READY → PROGRESSING → TESTING → REVIEW → STAGING → DONE → ARCHIVED
                                       ↓                    ↓
                                  REJECTED              REJECTED
```

**HAMMER CHECKS BLOCK WEAK CODE:**
| Stage | Check Requirement |
|------|-------------|
| PROGRESSING | Complete story/tech/plan |
| TESTING | `hammer check all` PASSES |
| REVIEW | Tests pass + branch pushed + diff generated |
| STAGING | Regression check passed (Rc flag) |
| DONE | Merged to main |
| ARCHIVED | Merged to main + regression check passed |

## 💥 HAMMER vs Chaos

| Without HAMMER | With HAMMER |
|----------------|-------------|
| Scattered notes | **HAMMER AUDIT!** Git log every smash |
| Manual updates | **HAMMER PIPELINE!** Checks block weak code |
| Lost context | **HAMMER HISTORY FULL!** Every change tracked |
| "What's ready?" | **HAMMER PIPELINE CLEAR!** Stages enforced |
| Agent chaos | **HAMMER ATOMIC ID!** Blockers + branch lock |

## 🛠️ HAMMER COMMANDS

### Task Management
```bash
hammer tasks init                    # HAMMER BUILD SYSTEM!
hammer tasks list                     # SHOW ALL!
hammer tasks create "SMASH BUG"       # NEW METAL!
hammer tasks show 42                  # METAL DETAIL!
hammer tasks current                  # ACTIVE METAL!
```

### POUND THROUGH STAGES
```bash
hammer tasks move 42 PROGRESSING     # START SMASH! (Creates branch)
hammer tasks move 42 TESTING         # ✅ HAMMER LIKE! MOVE → TESTING ⚔️🔨
hammer tasks move 42 DONE            # 🔨 HAMMER SMASH GOOD! DONE! ⚔️🔨
```

### QUALITY SMASH
```bash
hammer check all                     # SMASH ALL CHECKS!
hammer check lint --fix              # FIX WEAK CODE!
hammer tasks run all                 # HAMMER VALIDATE EVERYTHING!
```

## 🎯 REAL HAMMER FLOW

```bash
hammer tasks init                    # ✅ HAMMER LIKE! SYSTEM READY! ⚔️🔨
hammer tasks create "SMASH LOGIN"    # NEW METAL 42!
hammer tasks move 42 PROGRESSING     # BRANCH CREATE!
hammer check all                     # ❌ TEST BREAK! HAMMER SAY NO! FIX! 🔨
# LLM FIXES...
hammer tasks move 42 TESTING         # ✅ HAMMER LIKE! MOVE → TESTING ⚔️🔨
hammer tasks move 42 DONE            # 🔨 HAMMER SMASH GOOD! DONE! ⚔️🔨
```

## ⚙️ Task File (Git-Backed)

```yaml
***
Id: 42
Ti: Fix login bug
St: PROGRESSING
***
## Story
User cannot login with special characters in password.

## Plan
1. Fix regex validation
2. Test unicode input
3. Check error messages
```

## 🔧 HAMMER CONFIG
```bash
hammer tasks config detect           # HAMMER FIND TOOLS!
hammer tasks config set repo.test pytest
```

## 🎉 Why HAMMER RULES?

- **No external services** - Pure git
- **Zero deps** - One-line install  
- **Agent-optimized** - JSON output, clear protocol
- **Enforced quality** - Gates BLOCK weak code
- **Full lifecycle** - Backlog → DONE → ARCHIVED

**HAMMER IS BOSS. WEAK LLM SUBMIT. STRONG TEAM SHIP!** 🔨⚔️
```
# Update
Final pipeline verification
