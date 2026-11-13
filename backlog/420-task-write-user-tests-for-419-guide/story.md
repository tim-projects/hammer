As a Hammer agent, I want regression coverage proving that a missing verification proof returns an actionable next-step instruction for the current, fresh-patch review workflow instead of a confusing error.

The tests must prove that the guidance refreshes stale patches first, requires `cat` and checksum evidence for the refreshed patch set, and then binds the proof before regression checking.
