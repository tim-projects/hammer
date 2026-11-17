As a maintainer I need tests that prove task 463's fix: the dev-mode throwaway repos stop
accumulating in /tmp, cleanup failures become loud instead of silently ignored, and cleanup
survives setUp failures — so the ENOSPC masking of real test failures cannot regress.
