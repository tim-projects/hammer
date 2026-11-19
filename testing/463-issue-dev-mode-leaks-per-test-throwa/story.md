As a hammer developer or agent running the test suite (or any `--dev` command), I need dev
mode's throwaway state to be bounded, because today every test leaves directories in /tmp
forever. After a few full-suite runs /tmp fills (observed: 1790 leftover dirs, tmpfs at 100%,
16K free), and once it is full a full-suite run collapses into environmental failures — 173
failed / 180 passed with `OSError: [Errno 28] No space left on device` — which masks the real
state of the code (the same run on a cleared /tmp gives 4 failed / 353 passed).
