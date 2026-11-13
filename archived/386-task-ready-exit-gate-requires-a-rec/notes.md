
- Progress: ResearchGateHook registered on READY exit; --research flag on modify stores research.md + Rr attestation.
- Findings: file payloads reuse resolve_content (task 382) with no extra code; gate requires BOTH Rr and >=10 chars of findings so a flag flip alone cannot pass.
- Debt: Rr is self-attested (no atime/md5 evidence like --reviewed has for patches); an online-search pass cannot be evidenced technically. Upgrade to atime-checked reading of named files if false passes show up.