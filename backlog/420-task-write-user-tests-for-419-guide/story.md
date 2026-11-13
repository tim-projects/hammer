As a Hammer agent, I want expected workflow prerequisites to return a clear, actionable next-step instruction instead of a confusing `Error:` response, so I can continue the required patch-review workflow without incorrectly treating the instruction as an unexpected failure.

The primary case is `PROOF_MISSING`: after patch review and audit, the agent must know to display every patch with `cat`, capture review evidence such as SHA256 checksums, bind that evidence with `tasks verify --proof`, and then rerun `tasks modify --regression-check`.

The output must follow the Hammer voice guidelines in `docs/HAMMER_VOICE.md`: short imperative guidance with WHAT, WHY, HOW, and CONSEQUENCE.
