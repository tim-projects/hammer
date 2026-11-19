**Corrected evidence (2026-11-09, main a5b971e8, direct name-diff experiments):**
- `pytest tests/test_init_backup.py` (2 passed): added dirs = **none**. `pytest tests/test_backlog_to_rejected.py`
  (HammerTestBase, 1 passed): added = **none**. Same for `tests/test_lazy_task_creation.py`.
  So the earlier "+2 per green run" reading was a measurement artifact — completed runs do NOT leak.
- All 388 current `/tmp/hammer_*` dirs predate today: they are orphans of interrupted runs, older
  code, or manual `--dev` sessions. Nothing ever reclaims them → /tmp only grows (observed
  1790 dirs, tmpfs 100%, 16K free) → once full, every suite run dies with ENOSPC and masks real
  failures (173 failed/180 passed vs the true 4 failed/353 passed on a cleared /tmp).
- Cleanup exists per test: `tests/hammer_test_base.py:30-34` `cleanup_dev_store` → `cleanup_path`
  (retries ENOTEMPTY, raises on persistent failure); base `tearDown` (146-149) rmtrees three dirs
  but with `ignore_errors=True` on the dev repo — inconsistent with the non-base path and silent.
- `tearDown` (not addCleanup): a setUp failure in the base path leaks that test's dirs.

**Two real defects remain:** (1) no reclamation of stale harness dirs — unbounded /tmp growth
across crashed runs and manual sessions; (2) inconsistent, silent cleanup in HammerTestBase
(ignore_errors + tearDown-not-addCleanup).

**Fix:** `context.py` dev bootstrap sweeps stale `/tmp/hammer_*` dirs (harness prefixes only,
under tempfile.gettempdir(), mtime older than a TTL, never the live repo/store) on the cold path
(when a new dev repo clone is created); `hammer_test_base` cleanup made strict + addCleanup.
