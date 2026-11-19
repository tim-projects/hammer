---
---

Implemented fail-loud addCleanup for test-owned temporary stores, dev repo clones, fixture roots, and remotes. Added transient ENOTEMPTY retry for detached Git auto-maintenance races and regression tests for zero temp growth plus loud cleanup. Verified clean-space suite: 360 passed, 1 skipped, zero net /tmp/hammer_* growth. Verified 92%-full /tmp suite: same 360 passed, 1 skipped, zero net growth.