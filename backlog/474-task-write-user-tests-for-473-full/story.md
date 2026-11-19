As a maintainer I need the full pytest suite to produce the same result regardless of
execution order or /tmp state, because today three tests fail only in full-suite context:
their failures are environmental/order artifacts that mask real failures (the same class as
the ENOSPC masking that task 463's sweep now removes).
